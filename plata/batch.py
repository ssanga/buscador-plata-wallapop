"""Proceso nocturno: descarga anuncios, los analiza y los guarda en SQLite.

Uso:
    python main.py batch                 # ejecución completa
    python main.py batch --reanalyze     # recalcula el análisis sin descargar nada
    python main.py batch --max-pages 3   # prueba rápida
"""
import argparse
import logging
import sys
from datetime import datetime, timezone

from . import config, db
from .analyzer import analyze
from .spot import get_spot
from .wallapop import WallapopClient, item_url

log = logging.getLogger("plata.batch")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ms_to_iso(ms) -> str | None:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="seconds") if ms else None


def fetch_all(max_pages: int) -> dict[str, dict]:
    client = WallapopClient()
    items: dict[str, dict] = {}
    for kw in config.KEYWORDS:
        n = 0
        for it in client.search(kw, max_pages=max_pages):
            entry = items.setdefault(it["id"], {"raw": it, "keywords": set()})
            entry["keywords"].add(kw)
            n += 1
        log.info("%-22s %5d anuncios (acumulado único: %d)", kw, n, len(items))
    return items


def apply_analysis(row: dict, spot_eur_g: float) -> dict:
    a = analyze(row["title"], row["description"])
    melt = round(a.fine_grams * spot_eur_g, 2) if a.fine_grams else None
    return {
        "is_replica": int(a.is_replica),
        "replica_reason": a.replica_reason,
        "is_wanted": int(a.is_wanted),
        "is_accessory": int(a.is_accessory),
        "weight_g": a.weight_g,
        "purity": a.purity,
        "quantity": a.quantity,
        "fine_grams": a.fine_grams,
        "estimate_source": a.source,
        "confidence": a.confidence,
        "notes": "; ".join(a.notes) or None,
        "melt_value_eur": melt,
        "eur_per_fine_g": round(row["price"] / a.fine_grams, 3) if a.fine_grams else None,
        "premium_pct": round((row["price"] / melt - 1) * 100, 1) if melt else None,
    }


def save(conn, items: dict[str, dict], spot_eur_g: float, ts: str) -> int:
    new = 0
    for item_id, entry in items.items():
        it = entry["raw"]
        price = float(it.get("price", {}).get("amount") or 0)
        images = it.get("images") or []
        loc = it.get("location") or {}
        row = {
            "id": item_id,
            "title": it.get("title", ""),
            "description": it.get("description", ""),
            "price": price,
            "currency": it.get("price", {}).get("currency", "EUR"),
            "url": item_url(it),
            "image": images[0]["urls"].get("medium") if images else None,
            "city": loc.get("city"),
            "region": loc.get("region2") or loc.get("region"),
            "shippable": int(bool((it.get("shipping") or {}).get("user_allows_shipping"))),
            "reserved": int(bool((it.get("reserved") or {}).get("flag"))),
            "created_at": ms_to_iso(it.get("created_at")),
            "modified_at": ms_to_iso(it.get("modified_at")),
            "matched_keywords": ", ".join(sorted(entry["keywords"])),
            "last_seen": ts,
        }
        row.update(apply_analysis(row, spot_eur_g))

        prev = conn.execute("SELECT price, prev_price FROM items WHERE id = ?", (item_id,)).fetchone()
        if prev is None:
            new += 1
            row["first_seen"] = ts
            cols = ", ".join(row)
            conn.execute(f"INSERT INTO items ({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
        else:
            # Si el precio no ha cambiado se conserva el anterior, para que la bajada siga visible.
            row["prev_price"] = prev["price"] if prev["price"] != price else prev["prev_price"]
            sets = ", ".join(f"{k} = ?" for k in row if k != "id")
            values = [v for k, v in row.items() if k != "id"]
            conn.execute(f"UPDATE items SET {sets}, active = 1 WHERE id = ?", values + [item_id])

        last = conn.execute(
            "SELECT price FROM price_history WHERE item_id = ? ORDER BY seen_at DESC LIMIT 1", (item_id,)
        ).fetchone()
        if last is None or last["price"] != price:
            conn.execute("INSERT INTO price_history VALUES (?, ?, ?)", (item_id, price, ts))

    # Lo que no ha aparecido hoy se considera vendido / retirado.
    conn.execute("UPDATE items SET active = 0 WHERE last_seen <> ?", (ts,))
    return new


def reanalyze(conn, spot_eur_g: float) -> None:
    rows = conn.execute("SELECT id, title, description, price FROM items").fetchall()
    for r in rows:
        values = apply_analysis(dict(r), spot_eur_g)
        sets = ", ".join(f"{k} = ?" for k in values)
        conn.execute(f"UPDATE items SET {sets} WHERE id = ?", list(values.values()) + [r["id"]])
    log.info("Reanalizados %d anuncios", len(rows))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reanalyze", action="store_true", help="recalcula el análisis sin descargar")
    parser.add_argument("--max-pages", type=int, default=config.MAX_PAGES_PER_KEYWORD)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    started = now()
    with db.connect() as conn:
        spot = get_spot()
        log.info("Spot plata: %.2f USD/oz → %.3f €/g", spot["usd_oz"], spot["eur_g"])

        if args.reanalyze:
            reanalyze(conn, spot["eur_g"])
            return 0

        run_id = conn.execute(
            "INSERT INTO runs (started_at, status, spot_usd_oz, usd_eur, spot_eur_g) VALUES (?, 'running', ?, ?, ?)",
            (started, spot["usd_oz"], spot["usd_eur"], spot["eur_g"]),
        ).lastrowid
        conn.commit()
        try:
            items = fetch_all(args.max_pages)
            if not items:
                raise RuntimeError("La búsqueda no devolvió ningún anuncio (¿cambió la API?)")
            new = save(conn, items, spot["eur_g"], started)
            conn.execute(
                "UPDATE runs SET finished_at = ?, status = 'ok', items_seen = ?, items_new = ? WHERE id = ?",
                (now(), len(items), new, run_id),
            )
            log.info("Terminado: %d anuncios únicos, %d nuevos", len(items), new)
        except Exception as e:
            conn.rollback()
            conn.execute("UPDATE runs SET finished_at = ?, status = 'error', error = ? WHERE id = ?", (now(), str(e), run_id))
            log.exception("El proceso ha fallado")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
