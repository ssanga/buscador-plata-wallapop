"""Web de consulta. Lee SQLite en cada petición, así siempre muestra el último batch.

Uso:  python main.py web    →  http://127.0.0.1:5000
"""
from flask import Flask, jsonify, redirect, render_template, request, url_for

from . import config, db

app = Flask(__name__)

VIEWS = {
    "oportunidades": "Mejor €/g de plata",
    "baratas": "Más baratas",
    "nuevos": "Nuevos hoy",
    "bajadas": "Bajadas de precio",
    "sospechosos": "Demasiado buenos",
    "descartados": "Descartados",
}
CONFIDENCE_LEVELS = {"alta": ("alta",), "media": ("alta", "media"), "baja": ("alta", "media", "baja")}


def get_filters(args) -> dict:
    return {
        "view": args.get("view", "oportunidades") if args.get("view") in VIEWS else "oportunidades",
        "max_price": args.get("max_price", type=float),
        "min_conf": args.get("min_conf", "media") if args.get("min_conf") in CONFIDENCE_LEVELS else "media",
        "shipping": args.get("shipping") == "1",
        "limit": min(args.get("limit", config.TOP_N, type=int), 200),
    }


def query_ranking(conn, f: dict) -> list[dict]:
    where = ["active = 1", "is_wanted = 0", "COALESCE(is_accessory, 0) = 0"]
    params: list = []
    view = f["view"]

    where.append("dismissed = 1" if view == "descartados" else "dismissed = 0")
    if view != "descartados":
        where.append("is_replica = 0")
    if f["max_price"]:
        where.append("price <= ?")
        params.append(f["max_price"])
    if f["shipping"]:
        where.append("shippable = 1")

    if view in ("oportunidades", "sospechosos"):
        levels = CONFIDENCE_LEVELS[f["min_conf"]]
        where.append(f"fine_grams IS NOT NULL AND confidence IN ({','.join('?' * len(levels))})")
        params += levels
        op = "<" if view == "sospechosos" else ">="
        where.append(f"premium_pct {op} ?")
        params.append(config.SUSPICIOUS_PREMIUM_PCT)
        order = "premium_pct ASC"
    elif view == "nuevos":
        where.append("first_seen = (SELECT MAX(started_at) FROM runs WHERE status = 'ok')")
        order = "COALESCE(premium_pct, 999) ASC, price ASC"
    elif view == "bajadas":
        where.append("prev_price IS NOT NULL AND prev_price > price")
        order = "(price - prev_price) / prev_price ASC"
    else:
        order = "price ASC"

    sql = f"SELECT * FROM items WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ?"
    return [dict(r) for r in conn.execute(sql, params + [f["limit"]])]


def last_run(conn):
    row = conn.execute("SELECT * FROM runs WHERE status = 'ok' ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


@app.route("/")
def index():
    f = get_filters(request.args)
    with db.connect() as conn:
        items = query_ranking(conn, f)
        run = last_run(conn)
        failed = conn.execute(
            "SELECT * FROM runs WHERE status = 'error' AND id > COALESCE((SELECT MAX(id) FROM runs WHERE status='ok'), 0) "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        stats = conn.execute(
            "SELECT COUNT(*) total, SUM(is_replica) replicas, SUM(fine_grams IS NOT NULL) estimados "
            "FROM items WHERE active = 1"
        ).fetchone()
    return render_template(
        "index.html", items=items, f=f, views=VIEWS, run=run, failed=failed, stats=stats, config=config
    )


@app.post("/item/<item_id>/descartar")
def dismiss(item_id):
    with db.connect() as conn:
        conn.execute("UPDATE items SET dismissed = 1 WHERE id = ?", (item_id,))
    return redirect(request.referrer or url_for("index"))


@app.post("/item/<item_id>/restaurar")
def restore(item_id):
    with db.connect() as conn:
        conn.execute("UPDATE items SET dismissed = 0 WHERE id = ?", (item_id,))
    return redirect(request.referrer or url_for("index"))


@app.route("/api/ranking")
def api_ranking():
    f = get_filters(request.args)
    with db.connect() as conn:
        return jsonify({"filters": f, "last_run": last_run(conn), "items": query_ranking(conn, f)})


@app.route("/item/<item_id>/historial")
def history(item_id):
    with db.connect() as conn:
        rows = conn.execute("SELECT price, seen_at FROM price_history WHERE item_id = ? ORDER BY seen_at", (item_id,))
        return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
