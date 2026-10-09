from plata.export import GENERIC_TYPE, MIN_REF_SAMPLES, reference_prices


def _it(coin, ppc, premium=0.0, conf="alta"):
    return {"coin_type": coin, "price_per_coin": ppc, "premium_pct": premium, "confidence": conf}


def test_mediana_por_tipo():
    items = [_it("Maple Leaf", p) for p in (30, 32, 34, 36, 100)]
    assert reference_prices(items) == {"Maple Leaf": 34}


def test_ignora_sospechosas_y_confianza_baja():
    items = [_it("Panda", p) for p in (30, 32, 34, 36, 38)]
    items += [_it("Panda", 5, premium=-80), _it("Panda", 500, conf="baja")]
    assert reference_prices(items) == {"Panda": 34}


def test_sin_muestras_suficientes_no_hay_referencia():
    items = [_it("Eagle", 30) for _ in range(MIN_REF_SAMPLES - 1)]
    assert reference_prices(items) == {}


def test_onza_generica_no_tiene_referencia():
    items = [_it(GENERIC_TYPE, 30 + i) for i in range(MIN_REF_SAMPLES * 2)]
    assert reference_prices(items) == {}


def _rec(i, title, active, last_seen):
    return {"id": str(i), "title": title, "description": "", "url": "https://es.wallapop.com/item/x", "image": None,
            "city": "Madrid", "shippable": True, "reserved": False, "price": 40.0, "prev_price": None,
            "created_at": "2026-10-01T00:00:00+00:00", "first_seen": "2026-10-01T02:00:00+00:00",
            "last_seen": last_seen, "active": active}


def test_vendidas_salen_aparte_y_no_cuentan_como_objetivo():
    from plata.export import build
    t0, t1 = "2026-10-05T02:00:00+00:00", "2026-10-06T02:00:00+00:00"
    run = {"started_at": t1, "finished_at": t1, "status": "ok", "spot_eur_oz": 30.0}
    state = {"runs": [run], "items": {
        "1": _rec(1, "Moneda 1 onza plata Maple Leaf 999", True, t1),
        "2": _rec(2, "Moneda 1 onza plata Maple Leaf 999", False, t0),
        "3": _rec(3, "Réplica de moneda de plata", False, t0),
    }}
    data = build(state)
    assert [(i["id"], bool(i.get("sold"))) for i in data["items"]] == [("1", False), ("2", True)]
    assert data["stats"]["targets"] == 1 and data["stats"]["sold"] == 1
    assert next(i for i in data["items"] if i["id"] == "2")["gone_days"] >= 0
