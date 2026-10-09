"""Genera el JSON que consume la web (GitHub Pages o `main.py web`) a partir del estado.

Aquí se aplica el analizador: solo se exportan los anuncios activos que son onzas bullion de
plata, con su precio por onza y su sobreprecio sobre el spot.
"""
import json
from collections import Counter, defaultdict
from statistics import median
from datetime import datetime, timezone
from pathlib import Path

from . import config, state as st
from .analyzer import analyze, evaluate

DESCRIPTION_CHARS = 220
GENERIC_TYPE = "Onza genérica"  # mezcla bullion y colección: no tiene precio de referencia
MIN_REF_SAMPLES = 5  # anuncios mínimos de un tipo para que su mediana sirva de referencia


def _days_since(iso: str | None, now: datetime) -> int | None:
    return (now - datetime.fromisoformat(iso)).days if iso else None


def reference_prices(items: list[dict]) -> dict[str, float]:
    """Mediana de €/onza por tipo de moneda, sin las sospechosas ni las de confianza baja.

    "Onza genérica" no tiene referencia. Los tipos con menos de MIN_REF_SAMPLES anuncios no tienen referencia.
    """
    by_type = defaultdict(list)
    for it in items:
        if it["coin_type"] != GENERIC_TYPE and it["premium_pct"] >= config.SUSPICIOUS_PREMIUM_PCT and it["confidence"] != "baja":
            by_type[it["coin_type"]].append(it["price_per_coin"])
    return {t: round(median(v), 2) for t, v in by_type.items() if len(v) >= MIN_REF_SAMPLES}


def _item(rec: dict, a, m: dict, now: datetime) -> dict:
    desc = rec["description"] or ""
    return {
        "id": rec["id"],
        "title": rec["title"],
        "description": desc[:DESCRIPTION_CHARS] + ("…" if len(desc) > DESCRIPTION_CHARS else ""),
        "url": rec["url"],
        "image": rec["image"],
        "city": rec["city"],
        "shippable": rec["shippable"],
        "reserved": rec["reserved"],
        "price": rec["price"],
        "prev_price": rec.get("prev_price"),
        "days_listed": _days_since(rec.get("created_at"), now),
        "coin_type": a.coin_type,
        "confidence": a.confidence,
        **m,
        "notes": "; ".join(m["notes"]) or None,
    }


def build(state: dict) -> dict:
    run = st.last_ok_run(state)
    last = state["runs"][-1] if state["runs"] else None
    failed = last if last and last["status"] == "error" else None
    spot = run["spot_eur_oz"] if run else None
    now = datetime.now(timezone.utc)

    items, excluded, types = [], Counter(), Counter()
    active = [r for r in state["items"].values() if r.get("active")]
    for rec in active:
        a = analyze(rec["title"], rec["description"])
        if not a.is_target:
            excluded["réplicas" if a.is_replica else "otros"] += 1
            continue
        if not spot:
            continue
        m = evaluate(a, rec["price"], spot)
        types[a.coin_type] += 1
        items.append({**_item(rec, a, m, now), "is_new": bool(run) and rec["first_seen"] == run["started_at"]})

    refs = reference_prices(items)  # solo con los anuncios activos

    # Anuncios que ya no aparecen: vendidos o retirados. Su último precio es la mejor pista del
    # precio real de venta. No cuentan en medianas ni estadísticas.
    sold = 0
    if run and spot:
        for rec in state["items"].values():
            if rec.get("active") or rec["last_seen"] >= run["started_at"]:
                continue
            a = analyze(rec["title"], rec["description"])
            if not a.is_target:
                continue
            items.append({**_item(rec, a, evaluate(a, rec["price"], spot), now),
                          "sold": True, "gone_days": _days_since(rec["last_seen"], now)})
            sold += 1

    for it in items:
        ref = refs.get(it["coin_type"])
        it["vs_median_pct"] = round((it["price_per_coin"] / ref - 1) * 100, 1) if ref else None

    by_day = {r["started_at"][:10]: r["spot_eur_oz"] for r in state["runs"] if r["status"] == "ok" and r.get("spot_eur_oz")}
    spot_history = [{"date": day, "eur_oz": v} for day, v in by_day.items()]  # un punto por día (el último)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "last_run": run,
        "failed_run": failed,
        "spot_history": spot_history[-60:],
        "stats": {
            "active": len(active),
            "targets": len(items) - sold,
            "sold": sold,
            "replicas": excluded["réplicas"],
            "excluded": excluded["otros"],
            "coin_types": dict(types.most_common()),
            "coin_medians": refs,
        },
        "config": {"suspicious_premium_pct": config.SUSPICIOUS_PREMIUM_PCT, "min_price": config.MIN_PRICE},
        "items": items,
    }


def export(out: Path) -> dict:
    data = build(st.load())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data
