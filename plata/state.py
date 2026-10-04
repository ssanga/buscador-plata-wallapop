"""Estado persistente entre ejecuciones en un único fichero JSON (data/estado.json).

{
  "version": 1,
  "runs":  [ {started_at, finished_at, status, items_seen, items_new, spot_usd_oz, usd_eur, spot_eur_oz, error}, ... ],
  "items": { "<id>": {datos del anuncio..., first_seen, last_seen, active, prev_price, keywords, history: [[ts, precio], ...]} }
}

Solo guarda datos crudos y seguimiento (nuevo, bajadas, vendidos). El análisis se calcula al
exportar, así que mejorar el analizador no obliga a reprocesar nada.
"""
import json
import os
from pathlib import Path

from . import config

VERSION = 1


def empty() -> dict:
    return {"version": VERSION, "runs": [], "items": {}}


def load(path: Path = config.STATE_PATH) -> dict:
    if not path.exists():
        return empty()
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("runs", [])
    state.setdefault("items", {})
    return state


def save(state: dict, path: Path = config.STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)  # escritura atómica: nunca queda un estado a medias


def last_ok_run(state: dict) -> dict | None:
    return next((r for r in reversed(state["runs"]) if r["status"] == "ok"), None)
