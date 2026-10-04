import pytest

from plata.analyzer import analyze


# --------------------------------------------------------------------------- monedas que interesan


@pytest.mark.parametrize(
    "title, desc, coin, confidence",
    [
        ("Onza de plata Maple Leaf 2023", "Plata 9999, 1 oz", "Maple Leaf", "alta"),
        ("Filarmónica de Viena plata", "Moneda de 1 onza", "Filarmónica", "alta"),
        ("Krugerrand", "Moneda de plata de inversión", "Krugerrand", "media"),
        ("Silver Eagle 2021 1oz", "", "Silver Eagle", "alta"),
        ("Onza plata Britannia 2023", "", "Britannia", "media"),
        ("Libertad México 1 oz plata", "", "Libertad", "media"),
        ("Panda China plata 2024", "30 gramos de plata 999", "Panda", "media"),
        ("Kookaburra 2019 1 oz", "", "Kookaburra", "alta"),
        ("Onza de plata Arca de Noé", "", "Arca de Noé", "alta"),
        ("Onza troy de plata 999", "Moneda conmemorativa", "Onza genérica", "media"),
    ],
)
def test_identifica_onzas(title, desc, coin, confidence):
    a = analyze(title, desc)
    assert a.is_target, a.excluded
    assert a.coin_type == coin
    assert a.confidence == confidence


def test_panda_pesa_30_gramos():
    assert analyze("Panda plata 2023", "").fine_oz == pytest.approx(0.964, abs=0.001)


def test_lote_multiplica_onzas():
    a = analyze("Lote 10 Maple Leaf plata 1 oz", "")
    assert a.quantity == 10
    assert a.fine_oz == pytest.approx(10, abs=0.01)
    assert a.confidence == "media"


def test_tubo_de_25():
    assert analyze("Tubo de 25 Filarmónicas plata", "").quantity == 25


def test_n_onzas_es_lote():
    assert analyze("5 onzas de plata Britannia", "").quantity == 5


def test_precio_por_unidad_no_multiplica():
    a = analyze("Lote 100 Monedas Britannia 1oz Plata 999", "Precio por unidad, hay más unidades")
    assert a.quantity == 1


def test_tirada_no_es_lote():
    assert analyze("Maple Leaf plata 2024", "Peso: 31,1 g. Tirada: 100 piezas").quantity == 1


# --------------------------------------------------------------------------- descartes


@pytest.mark.parametrize(
    "title, desc",
    [
        ("Moneda 2000 pesetas plata 1995", ""),
        ("Duro de plata 1898", ""),
        ("12 euros plata 2004", "Moneda de plata de 18 gramos"),
        ("100 pesetas 1966 Franco", ""),
        ("5 francos plata 1960", ""),
        ("Moneda Mercury Dime 1944 plata", "Libertad alada"),
        ("Dólar Morgan 1921", ""),
        ("Moneda antigua de plata", "Bonita moneda"),
    ],
)
def test_descarta_lo_que_no_es_onza_bullion(title, desc):
    assert not analyze(title, desc).is_target


@pytest.mark.parametrize(
    "title",
    ["Media onza plata Britannia", "Maple Leaf 1/4 oz plata", "Kilo de plata Kookaburra", "Panda 5 oz plata"],
)
def test_descarta_fracciones_y_multiplos(title):
    a = analyze(title, "")
    assert a.excluded and a.excluded.startswith("no es de 1 oz")


def test_descarta_por_peso_en_gramos():
    a = analyze("Onza de plata conmemorativa", "Peso 15,5 g, plata 999")
    assert not a.is_target


def test_ley_baja_no_es_bullion():
    assert not analyze("Onza plata 925 conmemorativa", "").is_target


@pytest.mark.parametrize(
    "title, desc, reason",
    [
        ("Onza plata Maple Leaf", "Réplica de la moneda canadiense", "réplica"),
        ("Onza plata Krugerrand", "Moneda bañada en plata, ideal regalo", "bañada"),
        ("Silver eagle", "Silver plated coin", "plated"),
        ("Moneda onza", "Color plata, no es de plata", "color plata"),
        ("Barra Cobre puro 10oz Maple Leaf", "Material: Cobre .999", "metal no plata"),
        ("Krugerrand 1 oz", "Krugerrand de oro", "es de oro"),
    ],
)
def test_detecta_replicas(title, desc, reason):
    a = analyze(title, desc)
    assert a.is_replica
    assert a.excluded == reason


@pytest.mark.parametrize(
    "title, desc",
    [
        ("Onza de plata Britannia 2023", "Original, no es réplica. Plata 999."),
        ("Maple Leaf plata 2020", "Moneda original, nada de copias"),
    ],
)
def test_negacion_no_es_replica(title, desc):
    assert analyze(title, desc).is_target


@pytest.mark.parametrize(
    "title",
    ["Lote 10 Cápsulas Acrílicas para monedas de 1 oz plata", "Tubos para onzas de plata 40mm", "Monsterbox Bullmint vacía"],
)
def test_accesorios(title):
    assert analyze(title, "").excluded == "accesorio / no es moneda"


def test_moneda_con_capsula_no_es_accesorio():
    assert analyze("Maple Leaf plata 1 oz con cápsula", "").is_target


@pytest.mark.parametrize(
    "title, desc",
    [
        ("Compro onzas de plata", "Pago al contado"),
        ("Onza plata Maple", "Si tienes monedas de plata te las puedo comprar"),
    ],
)
def test_compradores(title, desc):
    assert analyze(title, desc).excluded == "anuncio de compra"


def test_ignora_spam_de_palabras_clave():
    a = analyze("Lote 28 monedas Suecia", "Monedas variadas. palabras: maple, panda, onza plata")
    assert not a.is_target


@pytest.mark.parametrize(
    "title",
    ["Moneda 1 Penny 1930 Britannia", "Polonia 10000 Zlotys 1990 libertad", "La Plata de Britannia, libro"],
)
def test_nombres_ambiguos(title):
    assert not analyze(title, "").is_target


def test_lote_baratisimo_es_precio_por_unidad():
    from plata.analyzer import evaluate

    a = analyze("Oferta! Tubo 25 Uds Plata 0.999 Maple", "")
    assert a.quantity == 25
    m = evaluate(a, 76.0, 54.0)
    assert m["quantity"] == 1
    assert m["premium_pct"] == pytest.approx(40.8, abs=0.5)


def test_lote_de_euros_no_es_cantidad():
    assert analyze("Filarmónica 2015 onza plata 999", "La vendo junto con un lote de 300€").quantity == 1


@pytest.mark.parametrize(
    "title",
    [
        "Toronto Maple Leafs Celebration Box",
        "Moneda plata balancín o gorro de la libertad 25cts",
        "Moneda Plata 1906 Ellis Island Estatua Libertad",
        "Moneda Plata 1915 II Reich Águila Imperial",
        "Moneda Plata Half Dollar Walking Liberty 1942",
        "Moneda 1/4 Britannia plata 2014",
    ],
)
def test_falsos_positivos_reales(title):
    assert not analyze(title, "").is_target


def test_krugerrand_sin_mencionar_plata_no_cuenta():
    # Sin "plata" en ningún sitio, un Krugerrand suele ser de oro.
    assert not analyze("Krugerrand", "Moneda de inversión").is_target


def test_dorada_no_es_bullion():
    assert analyze("Krugerrand 1oz Argento 2020", "Moneta Krugerrand da 1 oncia d'argento placcato oro").is_replica


def test_soldadura_no_es_moneda():
    assert not analyze("Soldadura Plata Shipman Brothers 1 oz Filadelfia", "").is_target
