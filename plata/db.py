"""Persistencia en SQLite: anuncios, histórico de precios y ejecuciones."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id               TEXT PRIMARY KEY,
    title            TEXT,
    description      TEXT,
    price            REAL,
    prev_price       REAL,
    currency         TEXT,
    url              TEXT,
    image            TEXT,
    city             TEXT,
    region           TEXT,
    shippable        INTEGER,
    reserved         INTEGER,
    created_at       TEXT,
    modified_at      TEXT,
    first_seen       TEXT,
    last_seen        TEXT,
    active           INTEGER DEFAULT 1,
    dismissed        INTEGER DEFAULT 0,
    matched_keywords TEXT,
    -- análisis
    is_replica       INTEGER,
    replica_reason   TEXT,
    is_wanted        INTEGER,
    is_accessory     INTEGER,
    weight_g         REAL,
    purity           REAL,
    quantity         INTEGER,
    fine_grams       REAL,
    estimate_source  TEXT,
    confidence       TEXT,
    notes            TEXT,
    melt_value_eur   REAL,
    eur_per_fine_g   REAL,
    premium_pct      REAL
);
CREATE INDEX IF NOT EXISTS ix_items_active ON items(active, dismissed, is_replica);

CREATE TABLE IF NOT EXISTS price_history (
    item_id  TEXT,
    price    REAL,
    seen_at  TEXT,
    PRIMARY KEY (item_id, seen_at)
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT,
    finished_at  TEXT,
    status       TEXT,
    items_seen   INTEGER,
    items_new    INTEGER,
    spot_usd_oz  REAL,
    usd_eur      REAL,
    spot_eur_g   REAL,
    error        TEXT
);
"""


@contextmanager
def connect(path: Path = config.DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()
