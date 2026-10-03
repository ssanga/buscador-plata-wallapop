import pytest

from plata.analyzer import analyze


@pytest.mark.parametrize(
    "title, desc, reason",
    [
        ("Moneda 8 reales", "Réplica de moneda antigua", "réplica"),
        ("Onza plata", "Moneda bañada en plata, ideal regalo", "bañada"),
        ("Duro 1898", "Copia en metal plateado", "copia"),
        ("Silver eagle", "Silver plated coin", "plated"),
        ("Moneda", "Color plata, no es de plata", "color plata"),
        ("Moneda oro 1/10 oz", "Krugerrand de oro", "es de oro"),
    ],
)
def test_detecta_replicas(title, desc, reason):
    a = analyze(title, desc)
    assert a.is_replica
    assert a.replica_reason == reason


@pytest.mark.parametrize(
    "title, desc",
    [
        ("Onza de plata Britannia 2023", "Original, no es réplica. Plata 999."),
        ("Duro 1885", "Moneda original de plata, nada de copias"),
        ("12 euros plata 2003", "Moneda de 12 euros de plata"),
    ],
)
def test_negacion_no_es_replica(title, desc):
    assert not analyze(title, desc).is_replica


def test_anuncio_de_compra():
    assert analyze("Compro monedas de plata", "Pago al contado").is_wanted


@pytest.mark.parametrize(
    "title, desc, fine, confidence",
    [
        ("Onza de plata Maple Leaf", "Plata 999 de 1 oz", 31.07, "alta"),
        ("Moneda plata 925", "Pesa 27 gramos", 24.98, "alta"),
        ("Moneda de plata", "27 gr, ley 0,925", 24.98, "alta"),
        ("Medio kilo plata", "Lingote moneda 0,5 kg plata 999", 499.5, "alta"),
        ("Moneda 2000 pesetas 1995", "En su cápsula", 16.65, "media"),
        ("12 euros plata 2004", "Sin circular", 16.65, "media"),
        ("Duro de plata 1898", "Alfonso XIII", 22.5, "media"),
        ("100 pesetas 1966", "Franco, estrellas 19*66", 15.2, "media"),
        ("Krugerrand", "Moneda de inversión", 31.07, "media"),
        ("Lote 10 monedas de 12 euros", "Todas sin circular", 166.5, "baja"),
        ("Lote de monedas plata", "Peso total 100 gramos plata 925", 92.5, "alta"),
        ("1/2 onza plata", "Plata pura", 15.54, "alta"),
    ],
)
def test_estimacion_plata_fina(title, desc, fine, confidence):
    a = analyze(title, desc)
    assert a.fine_grams == pytest.approx(fine, abs=0.05)
    assert a.confidence == confidence


def test_sin_datos_no_estima():
    a = analyze("Moneda antigua de plata", "Bonita moneda, mírala en fotos")
    assert a.fine_grams is None
    assert a.confidence == "ninguna"


def test_precio_no_se_confunde_con_moneda_de_10_euros():
    a = analyze("Moneda plata", "La vendo por 10 euros, negociable")
    assert a.source != "10 euros FNMT"


@pytest.mark.parametrize(
    "title",
    ["Lote 10 Cápsulas Acrílicas para Monedas 40mm", "Tubos para monedas 1 oz plata", "Monsterbox Bullmint vacía"],
)
def test_accesorios(title):
    assert analyze(title, "").is_accessory


def test_moneda_con_estuche_no_es_accesorio():
    assert not analyze("Moneda 12 euros plata con estuche", "").is_accessory


def test_precio_por_unidad_no_multiplica_lote():
    a = analyze("Lote 100 Monedas Britannia 1oz Plata 999", "Precio por unidad, hay más unidades")
    assert a.quantity == 1
    assert a.fine_grams == pytest.approx(31.07, abs=0.05)


def test_ignora_spam_de_palabras_clave():
    a = analyze("Lote 28 monedas Suecia", "Monedas variadas. palabras: maple, panda, onza plata")
    assert a.fine_grams is None


def test_peso_sin_plata_en_titulo_no_asume_ley():
    assert analyze("1 Kilo de Pesetas Antiguas", "Lote de 1 kilogramos de monedas").fine_grams is None


def test_ley_no_estandar():
    a = analyze("Moneda de plata 5 marcos 1966", "Aleación: Plata 0.625 - Peso: 11,2 gr.")
    assert a.purity == 0.625
    assert a.fine_grams == pytest.approx(7.0, abs=0.05)


def test_cobre_no_es_plata():
    assert analyze("Barra Cobre puro 10oz Maple Leaf", "Material: Cobre .999").is_replica


def test_spam_tags_no_leer():
    a = analyze("100 Reis Brasil 1889", "Buen estado. Tags(no leer) antiguedades doblon plata cincuentin")
    assert a.fine_grams is None


def test_tirada_no_es_lote():
    a = analyze("Moneda Plata 999 Maple Leaf 2024", "Peso: 31,1 g. Tirada: 100 piezas")
    assert a.quantity == 1


def test_ley_en_porcentaje_y_precio_cada():
    a = analyze("Monedas 10 Schillings Austria - Plata", "Peso individual de 7,5g. Pureza 64% de Plata. 12€/cada")
    assert a.purity == 0.64
    assert a.quantity == 1


@pytest.mark.parametrize(
    "title, desc",
    [
        ("Moneda Mercury Dime 1944 plata", "Con el perfil de la Libertad alada"),
        ("Moneda 1 Penny 1930", "Presenta la figura de Britannia sentada"),
        ("Polonia 10000 Zlotys 1990", "Polonia hacia la libertad"),
        ("Moneda 2 euros Holanda 2011", "Erasmo 10€ 2012 TYE 4,2€"),
    ],
)
def test_nombres_bullion_ambiguos_no_estiman_onza(title, desc):
    a = analyze(title, desc)
    assert a.source is None or not a.source.startswith(("bullion", "10 euros"))


def test_britannia_onza_si():
    assert analyze("Onza plata Britannia 2023", "").fine_grams == pytest.approx(31.07, abs=0.05)


def test_dolar_morgan():
    assert analyze("Dólar Morgan 1921", "").fine_grams == pytest.approx(24.06, abs=0.05)


@pytest.mark.parametrize(
    "title, desc",
    [
        ("vendo o cambio mis discos", "Cambio por monedas de 2000 pesetas de plata"),
        ("Monedas Ecus y pesetas", "Tengo 2000 pesetas de plata y ecus"),
    ],
)
def test_moneda_solo_en_descripcion_de_titulo_no_plata(title, desc):
    assert analyze(title, desc).fine_grams is None


@pytest.mark.parametrize("title", ["Billete 100 pesetas Banco de España 1966", "Lotería Nacional 1966 - Décimos"])
def test_no_monedas(title):
    assert analyze(title, "").is_accessory


def test_titulo_generico_usa_descripcion():
    a = analyze("Moneda plata", "vendo moneda 2000 pesetas 1997 de plata, sin circular")
    assert a.source == "2000 pesetas"


def test_ley_desconocida_confianza_baja():
    a = analyze("Moneda Un Peso Mexicano Plata 1958", "Peso 16 gramos")
    assert a.confidence == "baja"


def test_comprador_disfrazado():
    a = analyze("Moneda Alfonso XII 1881 Plata", "Si tienes monedas de plata te las puedo comprar. Busco monedas de 2000 pesetas")
    assert a.is_wanted
