"""Servidor local de la web. Sirve la misma página estática que GitHub Pages, pero genera
`data.json` al vuelo desde SQLite, así siempre muestra el último batch local.

Uso:  python main.py web    →  http://127.0.0.1:5000
"""
from flask import Flask, jsonify, send_from_directory

from . import config, db, export

SITE_DIR = config.BASE_DIR / "site"

app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(SITE_DIR, "index.html")


@app.route("/data.json")
def data():
    with db.connect() as conn:
        return jsonify(export.build(conn))


@app.route("/item/<item_id>/historial")
def history(item_id):
    with db.connect() as conn:
        rows = conn.execute("SELECT price, seen_at FROM price_history WHERE item_id = ? ORDER BY seen_at", (item_id,))
        return jsonify([dict(r) for r in rows])
