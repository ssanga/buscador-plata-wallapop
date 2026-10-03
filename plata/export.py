"""Exporta a JSON lo que necesita la web estática (GitHub Pages o `main.py web`).

No se exporta toda la BD (serían decenas de MB): solo los anuncios activos que pueden interesar
(con plata estimada a un precio razonable y, de los que no tienen estimación, los más baratos,
los nuevos y las bajadas), sin réplicas, accesorios ni compradores.
"""
import json
from pathlib import Path

from . import config, db

FIELDS = (
    "id, title, description, price, prev_price, url, image, city, region, shippable, reserved, "
    "first_seen, fine_grams, purity, quantity, estimate_source, confidence, notes, "
    "melt_value_eur, eur_per_fine_g, premium_pct"
)
MAX_PER_GROUP = 300      # anuncios sin estimación: más baratos / nuevos / bajadas
MAX_PREMIUM_PCT = 150    # pagar más de 2,5 veces el valor de la plata no es una oportunidad
DESCRIPTION_CHARS = 200


def build(conn) -> dict:
    run = conn.execute("SELECT * FROM runs WHERE status = 'ok' ORDER BY id DESC LIMIT 1").fetchone()
    failed = conn.execute(
        "SELECT started_at, error FROM runs WHERE status = 'error' "
        "AND id > COALESCE((SELECT MAX(id) FROM runs WHERE status = 'ok'), 0) ORDER BY id DESC LIMIT 1"
    ).fetchone()
    stats = conn.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(is_replica), 0) AS replicas, "
        "COALESCE(SUM(fine_grams IS NOT NULL AND is_replica = 0), 0) AS estimated "
        "FROM items WHERE active = 1"
    ).fetchone()

    base = "active = 1 AND is_wanted = 0 AND COALESCE(is_accessory, 0) = 0 AND is_replica = 0"
    last_start = run["started_at"] if run else ""
    no_estimate = f"{base} AND fine_grams IS NULL"
    rows = conn.execute(
        f"""
        SELECT {FIELDS} FROM items
        WHERE {base} AND (
            (fine_grams IS NOT NULL AND premium_pct <= :max_premium)
            OR id IN (SELECT id FROM items WHERE {no_estimate} ORDER BY price LIMIT :n)
            OR id IN (SELECT id FROM items WHERE {no_estimate} AND first_seen = :last ORDER BY price LIMIT :n)
            OR id IN (SELECT id FROM items WHERE {base} AND prev_price > price
                      ORDER BY (price - prev_price) / prev_price LIMIT :n)
        )
        """,
        {"last": last_start, "n": MAX_PER_GROUP, "max_premium": MAX_PREMIUM_PCT},
    ).fetchall()

    items = []
    for r in rows:
        it = dict(r)
        desc = it["description"] or ""
        it["description"] = desc[:DESCRIPTION_CHARS] + ("…" if len(desc) > DESCRIPTION_CHARS else "")
        it["is_new"] = it.pop("first_seen") == last_start
        items.append(it)

    return {
        "last_run": dict(run) if run else None,
        "failed_run": dict(failed) if failed else None,
        "stats": dict(stats),
        "config": {
            "min_price": config.MIN_PRICE,
            "suspicious_premium_pct": config.SUSPICIOUS_PREMIUM_PCT,
            "top_n": config.TOP_N,
        },
        "items": items,
    }


def export(out: Path) -> dict:
    with db.connect() as conn:
        data = build(conn)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data
