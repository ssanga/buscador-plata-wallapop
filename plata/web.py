"""Servidor local de la web. Sirve la misma página estática que GitHub Pages, pero genera
`data.json` al vuelo desde data/estado.json, así siempre muestra el último batch local.

Uso:  python main.py web    →  http://127.0.0.1:5000
"""
from flask import Flask, jsonify, send_from_directory

from . import config, export, state

SITE_DIR = config.BASE_DIR / "site"

app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(SITE_DIR, "index.html")


@app.route("/data.json")
def data():
    return jsonify(export.build(state.load()))
