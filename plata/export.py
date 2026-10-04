"""Genera el JSON que consume la web (GitHub Pages o `main.py web`) a partir del estado.

Aquí se aplica el analizador: solo se exportan los anuncios activos que son onzas bullion de
plata, con su precio por onza y su sobreprecio sobre el spot.
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import config, state as st
from .analyzer import analyze, evaluate

DESCRIPTION_CHARS = 220


def _days_since(iso: str | None, now: datetime) -> int | None:
    return (now - datetime.fromisoformat(iso)).days if iso else None


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
        desc = rec["description"] or ""
        items.append({
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
            "is_new": bool(run) and rec["first_seen"] == run["started_at"],
            "days_listed": _days_since(rec.get("created_at"), now),
            "coin_type": a.coin_type,
            "confidence": a.confidence,
            **m,
            "notes": "; ".join(m["notes"]) or None,
        })

    by_day = {r["started_at"][:10]: r["spot_eur_oz"] for r in state["runs"] if r["status"] == "ok" and r.get("spot_eur_oz")}
    spot_history = [{"date": day, "eur_oz": v} for day, v in by_day.items()]  # un punto por día (el último)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "last_run": run,
        "failed_run": failed,
        "spot_history": spot_history[-60:],
        "stats": {
            "active": len(active),
            "targets": len(items),
            "replicas": excluded["réplicas"],
            "excluded": excluded["otros"],
            "coin_types": dict(types.most_common()),
        },
        "config": {"suspicious_premium_pct": config.SUSPICIOUS_PREMIUM_PCT, "min_price": config.MIN_PRICE},
        "items": items,
    }


def export(out: Path) -> dict:
    data = build(st.load())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return data
