"""Proceso nocturno: descarga los anuncios y actualiza el estado (data/estado.json).

Uso:
    python main.py batch                 # ejecución completa
    python main.py batch --max-pages 3   # prueba rápida
"""
import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from . import config, state as st
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
        log.info("%-24s %5d anuncios (acumulado único: %d)", kw, n, len(items))
    return items


def to_record(raw: dict) -> dict:
    images = raw.get("images") or []
    loc = raw.get("location") or {}
    return {
        "id": raw["id"],
        "title": raw.get("title", ""),
        "description": raw.get("description", ""),
        "price": float((raw.get("price") or {}).get("amount") or 0),
        "url": item_url(raw),
        "image": images[0]["urls"].get("medium") if images else None,
        "city": loc.get("city"),
        "region": loc.get("region2") or loc.get("region"),
        "shippable": bool((raw.get("shipping") or {}).get("user_allows_shipping")),
        "reserved": bool((raw.get("reserved") or {}).get("flag")),
        "created_at": ms_to_iso(raw.get("created_at")),
        "modified_at": ms_to_iso(raw.get("modified_at")),
    }


def merge(state: dict, fetched: dict[str, dict], ts: str) -> int:
    """Incorpora lo descargado al estado. Devuelve cuántos anuncios son nuevos."""
    items = state["items"]
    new = 0
    for item_id, entry in fetched.items():
        rec = to_record(entry["raw"])
        rec["keywords"] = sorted(entry["keywords"])
        old = items.get(item_id)
        if old is None:
            new += 1
            rec.update(first_seen=ts, prev_price=None, history=[[ts, rec["price"]]])
        else:
            history = old.get("history", [])
            changed = old["price"] != rec["price"]
            if changed:
                history.append([ts, rec["price"]])
            # Si el precio no ha cambiado se conserva el anterior, para que la bajada siga visible.
            rec.update(
                first_seen=old["first_seen"],
                prev_price=old["price"] if changed else old.get("prev_price"),
                history=history,
            )
        rec.update(last_seen=ts, active=True)
        items[item_id] = rec

    # Lo que no ha aparecido hoy se da por vendido o retirado; pasado un tiempo, se olvida.
    forget_before = (datetime.fromisoformat(ts) - timedelta(days=config.FORGET_AFTER_DAYS)).isoformat()
    for item_id in list(items):
        rec = items[item_id]
        if rec["last_seen"] != ts:
            rec["active"] = False
            if rec["last_seen"] < forget_before:
                del items[item_id]
    return new


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max-pages", type=int, default=config.MAX_PAGES_PER_KEYWORD)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    state = st.load()
    run = {"started_at": now(), "status": "running"}
    try:
        spot = get_spot()
        run.update(spot_usd_oz=spot["usd_oz"], usd_eur=spot["usd_eur"], spot_eur_oz=spot["eur_oz"])
        log.info("Spot plata: %.2f USD/oz → %.2f €/oz", spot["usd_oz"], spot["eur_oz"])

        fetched = fetch_all(args.max_pages)
        if not fetched:
            raise RuntimeError("La búsqueda no devolvió ningún anuncio (¿cambió la API?)")
        new = merge(state, fetched, run["started_at"])
        run.update(status="ok", items_seen=len(fetched), items_new=new)
        log.info("Terminado: %d anuncios únicos, %d nuevos, %d en el estado", len(fetched), new, len(state["items"]))
    except Exception as e:
        run.update(status="error", error=str(e))
        log.exception("El proceso ha fallado")
    run["finished_at"] = now()
    state["runs"] = (state["runs"] + [run])[-config.RUNS_TO_KEEP :]
    st.save(state)
    return 0 if run["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
