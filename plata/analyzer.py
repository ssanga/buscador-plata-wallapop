"""Análisis del texto de un anuncio: ¿es una moneda bullion de plata de 1 onza?

Todo son heurísticas sobre título + descripción. Para cada anuncio se decide:
- si hay que descartarlo (réplica, accesorio, comprador, moneda que no es bullion, fracción
  o múltiplo de onza...),
- qué moneda es (Maple Leaf, Filarmónica, Panda...),
- cuántas onzas incluye (lotes) para calcular el precio por onza.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

TROY_OUNCE_G = 31.1034768


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower())


# --------------------------------------------------------------------------- descartes

REPLICA_PATTERNS = [
    (r"\breplicas?\b", "réplica"),
    (r"\bcopias?\b", "copia"),
    (r"\breproduccion(es)?\b", "reproducción"),
    (r"\bimitacion(es)?\b", "imitación"),
    (r"\bfals[oa]s?\b", "falsa"),
    (r"\bfake\b", "fake"),
    (r"\bfantasia\b", "fantasía"),
    (r"\bbanad[oa]s?\b", "bañada"),
    (r"\bbano\s+(de|en)\s+plata\b", "baño de plata"),
    (r"\bchapad[oa]s?\b", "chapada"),
    (r"\bplatead[oa]s?\b", "plateada"),
    (r"\bsilver[\s-]?plated\b|\bplated\b", "plated"),
    (r"\b(chapad[oa]|banad[oa])\s+(en|de)\s+oro\b|\bdorad[oa]s?\b|\bgilded\b|\bplaccat[oa]\b|\bgold\s+gilded\b", "dorada"),
    (r"\b(color|aspecto|tipo|acabado)\s+plata\b", "color plata"),
    (r"\bno\s+(es|son)\s+de\s+plata\b", "no es de plata"),
    (r"\bsin\s+plata\b", "sin plata"),
    (r"\b(alpaca|cuproniquel|niquel|laton|zamak|cobre|bronce|inox|acero|titanio|titanium)\b", "metal no plata"),
]

# "no es réplica", "no es una copia", "nada de copias"... → no cuenta como réplica
NEGATION = re.compile(r"(\bno\s+(es|son)\s+(una?s?\s+)?|\bnada\s+de\s+|\bsin\s+|\bni\s+)$")

# Anuncios que no son monedas: se excluyen aunque mencionen "onza de plata".
ACCESSORY_PATTERN = re.compile(
    r"\b(capsulas?|tubos?|estuches?|cajas?|album(es)?|monsterbox|expositor(es)?|soportes?|"
    r"marcos?\s+para|lupas?|catalogos?|libros?|clasificador(es)?|carpetas?|bandejas?|"
    r"petaca|fiaschetta|llaveros?|colgantes?|pendientes?|anillos?|pulseras?|collar(es)?|"
    r"billetes?|loteria|decimos?|carnets?|tarjetas?|sellos?|discos?|vinilos?|postal(es)?|cromos?|"
    r"lingotes?|barras?|soldadura|hilo|grano|granalla)\b"
)

WANTED_PATTERN = re.compile(r"^\s*(compro|busco|cambio|intercambio)\b")
# Compradores que publican como si vendieran: "Si tienes monedas de plata te las compro".
WANTED_DESC_PATTERN = re.compile(
    r"\b(te\s+las?\s+(puedo\s+)?compr[oa]r?|las?\s+compro|compro\s+(monedas|plata|onzas|lotes|duros)|"
    r"busco\s+(monedas|plata|onzas|duros)|comprador\s+serio|pago\s+(al\s+)?contado\s+por)\b"
)

# Monedas que no son bullion de inversión: no interesan aunque sean de plata.
NOT_BULLION = re.compile(
    r"\b(pesetas?|ptas?|pts|duros?|reales|escudos|francos?|paquitos?|maravedis|centimos?|centavos?|"
    r"cents?|dimes?|quarters?|penny|peniques?|pence|shillings?|chelin(es)?|reis|florin(es)?|"
    r"marcos?|liras?|dracmas?|rublos?|thaler|talero|morgan|cincuentin|cts|half|medio\s+dolar|mezzo)\b"
)

# Muchos vendedores añaden palabras clave para salir en más búsquedas. Se eliminan.
SEO_SPAM = re.compile(
    r"(\btags?\b|\bpalabras(\s+clave)?\s*:|\bpalabras\s+clave\b|\betiquetas?\s*:|\bkeywords?\b|"
    r"\bno\s+leer\b|\bbusquedas?\s*:|\bsimilares?\s*:).*$"
)
HASHTAGS = re.compile(r"#\w+")


def detect_replica(text: str) -> Optional[str]:
    """Devuelve el motivo si el texto (normalizado) indica réplica / no plata."""
    for pattern, reason in REPLICA_PATTERNS:
        for m in re.finditer(pattern, text):
            before = text[max(0, m.start() - 20) : m.start()]
            if reason not in ("no es de plata", "sin plata") and NEGATION.search(before):
                continue
            return reason
    return None


def is_accessory(title: str) -> bool:
    """El título habla de un accesorio ("Lote 10 cápsulas") y no de una moneda "con estuche"."""
    for m in ACCESSORY_PATTERN.finditer(title):
        before = title[max(0, m.start() - 15) : m.start()]
        after = title[m.end() : m.end() + 10]
        if re.search(r"\b(con|en|y|incluye|mas|\+)\s+(su\s+|sus\s+|el\s+|la\s+)?$", before):
            continue  # "moneda con estuche"
        if m.group(1).startswith("tubo") and re.match(r"\s+(de\s+|con\s+)?\d", after):
            continue  # "tubo de 25 maples" es un lote de monedas
        return True
    return False


# --------------------------------------------------------------------------- tipo de moneda


@dataclass(frozen=True)
class CoinType:
    name: str
    pattern: str
    fine_oz: float = 0.999   # onzas de plata fina por moneda
    # Qué hace falta además del nombre para aceptarla:
    #   "plata"  → "plata/oz/onza/999/silver" en el título o en la descripción (nombres inequívocos)
    #   "titulo" → "plata/oz/onza" en el título (Panda: muchos anuncios no dicen "oz", pesa 30 g)
    #   "onza"   → "onza/oz" en el título (nombres ambiguos: Libertad, Britannia, Águila...)
    needs: str = "plata"


# Orden importante: el primero que encaja gana ("american eagle" antes que "eagle").
COIN_TYPES = [
    CoinType("Maple Leaf", r"maple(\s*leaf)?|hoja\s+de\s+arce", 0.9999),
    CoinType("Filarmónica", r"filarmonica|philharmoniker|philharmonic|filarmonic"),
    CoinType("Krugerrand", r"krugerrand|kruggerand|krugerand"),
    CoinType("Kookaburra", r"kookaburra"),
    CoinType("Arca de Noé", r"arca\s+de\s+noe|noah'?s?\s+ark"),
    CoinType("Elefante de Somalia", r"elefante\s+(de\s+)?somalia|somalia\s+elefante|somali(an)?\s+elephant"),
    CoinType("Silver Eagle", r"silver\s+eagle|american\s+eagle|aguila\s+americana"),
    CoinType("Panda", r"panda", 30 * 0.999 / TROY_OUNCE_G, "titulo"),  # 30 g desde 2016
    CoinType("Britannia", r"britannia", 0.999, "onza"),
    CoinType("Libertad", r"libertad", 0.999, "onza"),
    CoinType("Koala", r"koala", 0.999, "onza"),
    CoinType("Canguro", r"canguro|kangaroo|nugget", 0.9999, "onza"),
    CoinType("Lunar", r"lunar|ano\s+del\s+\w+|year\s+of\s+the|dragon", 0.999, "onza"),
    CoinType("Buffalo", r"buffalo|bufalo", 0.999, "onza"),
    CoinType("Eagle", r"eagle|aguila", 0.999, "onza"),
]
SILVER_HINT = re.compile(r"\b(onzas?|oz|plata|silver|ag|999|9999)\b")
TITLE_SILVER = re.compile(r"\b(onzas?|oz|plata|silver)\b")
OUNCE_WORD = re.compile(r"\b(onzas?|oz)\b|\d\s*oz\b")
GENERIC_OUNCE = re.compile(r"\b(1|una|un)\s*(oz|onza)\b|\bonza\s+(troy\s+)?(de\s+)?plata\b|\bplata\s+(1\s*)?(oz|onza)\b")
# Cosas que comparten nombre con una moneda: equipos, canciones, ropa...
NAME_CLASH = re.compile(r"\b(leafs|toronto|hockey|rag|partitura|sudadera|camiseta|muneco|figura|directorio|peluche)\b")


def coin_type(title: str, full: str) -> Optional[CoinType]:
    if NAME_CLASH.search(title):
        return None
    need = {"plata": SILVER_HINT.search(full), "titulo": TITLE_SILVER.search(title), "onza": OUNCE_WORD.search(title)}
    for ct in COIN_TYPES:
        if re.search(rf"\b({ct.pattern})s?\b", title) and need[ct.needs]:
            return ct
    return None


# --------------------------------------------------------------------------- peso, ley y cantidad

NUM = r"(\d+(?:[.,]\d+)?)"
WEIGHT_G = re.compile(NUM + r"\s*(g|gr|grs|gramos?|gms|grams?)\b")
WEIGHT_KG = re.compile(r"\b(kg|kilos?)\b|\d\s*kg\b")
FRACTION_OZ = re.compile(
    r"(\b1/2|\b1/4|\b1/10|\b1/20|\bmedia|\b0[.,]5|\b0[.,]25|\b0[.,]1)\s*(oz|onza)|\b1/(2|4|10|20)\b|\bcuarto\s+de\s+onza"
)
# "5 oz", "10 oz", "2oz" (singular/abreviado = una moneda de varias onzas)
MULTI_OZ_COIN = re.compile(r"\b([2-9]|[1-9]\d)\s*(oz|onza)\b(?!s)")
LOW_PURITY = re.compile(r"\b(?:ley\s+)?0?[.,]?(925|900|835|800|720|500)\b|\bsterling\b")

TOTAL_HINT = re.compile(r"\b(total|en\s+total|peso\s+total|todas?\s+juntas?)\b")
PER_UNIT = re.compile(
    r"\b(precio\s+(por\s+)?(unidad|moneda|onza|ud)|por\s+unidad|la\s+unidad|cada\s+una|c/u|/\s*ud\b|"
    r"\d+\s*(€|e|euros?)\s*(la|por|/)\s*(unidad|ud|moneda|onza)|(€|euros?)\s*/?\s*cada\b|/\s*cada\b|"
    r"hay\s+mas\s+unidades|salen\s+por|una\s+unidad\s*:|se\s+venden?\s+(por\s+)?separad)"
)
QUANTITY_PATTERNS = [
    re.compile(r"\blote\s+(?:de\s+)?(\d{1,3})\b(?!\s*(?:€|e\b|eur|euros?))"),  # no "lote de 300 €"
    re.compile(r"\b(\d{1,3})\s+(?:monedas|onzas|maples?|filarmonicas?|krugerrands?|britannias?|pandas?|eagles?)\b"),
    re.compile(r"\b(\d{1,3})\s*x\s*(?:1\s*oz|moneda|onza)"),
    re.compile(r"\btubo\s+(?:de\s+)?(\d{1,3})\b"),
]
WORD_NUMBERS = {"dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
QUANTITY_WORDS = re.compile(r"\b(" + "|".join(WORD_NUMBERS) + r")\s+(?:monedas|onzas)\b")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _find_quantity(title: str, desc: str) -> int:
    """Unidades del lote. En la descripción solo vale "lote de N": otros números
    ("tirada de 100 piezas", "pedidos >= 20 monedas") dan demasiados falsos positivos."""
    for pattern in QUANTITY_PATTERNS:
        m = pattern.search(title)
        if m and 2 <= int(m.group(1)) <= 500:
            return int(m.group(1))
    m = QUANTITY_WORDS.search(title)
    if m:
        return WORD_NUMBERS[m.group(1)]
    m = QUANTITY_PATTERNS[0].search(desc)
    if m and 2 <= int(m.group(1)) <= 500:
        return int(m.group(1))
    return 1


def _not_one_ounce(title: str, desc: str) -> Optional[str]:
    """Motivo si el anuncio es de una fracción o un múltiplo de onza (no de monedas de 1 oz)."""
    if FRACTION_OZ.search(title):
        return "fracción de onza"
    if WEIGHT_KG.search(title):
        return "kilo"
    m = MULTI_OZ_COIN.search(title)
    if m:
        return f"moneda de {m.group(1)} oz"
    # Un peso en gramos que no es de una onza (ni de un Panda de 30 g), si no habla de total.
    for text in (title, desc[:300]):
        for m in WEIGHT_G.finditer(text):
            grams = _num(m.group(1))
            context = text[max(0, m.start() - 25) : m.end() + 25]
            if 1 <= grams < 28.5 and not TOTAL_HINT.search(context):
                return f"{grams:g} g"
            if 33 < grams < 200 and not TOTAL_HINT.search(context) and "lote" not in title:
                return f"{grams:g} g"
    return None


# --------------------------------------------------------------------------- análisis


@dataclass
class Analysis:
    excluded: Optional[str] = None      # motivo de descarte; None = es una onza que interesa
    is_replica: bool = False
    coin_type: Optional[str] = None     # "Maple Leaf", "Filarmónica", ..., "Onza genérica"
    quantity: int = 1
    fine_oz: Optional[float] = None     # onzas de plata fina de todo el anuncio
    confidence: str = "ninguna"         # alta | media | baja | ninguna
    notes: list = field(default_factory=list)

    @property
    def is_target(self) -> bool:
        return self.excluded is None and self.fine_oz is not None


def analyze(title: str, description: str) -> Analysis:
    t = normalize(title)
    d = HASHTAGS.sub(" ", SEO_SPAM.sub(" ", normalize(description)))
    full = f"{t} . {d}"
    a = Analysis()

    # 1) Descartes
    reason = detect_replica(full)
    if not reason and (
        (re.search(r"\boro\b", t) and "plata" not in t) or (re.search(r"\bde\s+oro\b", d) and "plata" not in full)
    ):
        reason = "es de oro"
    if reason:
        a.is_replica = True
        a.excluded = reason
        return a
    if WANTED_PATTERN.search(t) or WANTED_DESC_PATTERN.search(d):
        a.excluded = "anuncio de compra"
        return a
    if is_accessory(t):
        a.excluded = "accesorio / no es moneda"
        return a
    m = NOT_BULLION.search(t)
    if m:
        a.excluded = f"no es bullion ({m.group(1)})"
        return a
    not_oz = _not_one_ounce(t, d)
    if not_oz:
        a.excluded = f"no es de 1 oz ({not_oz})"
        return a
    if LOW_PURITY.search(t):
        a.excluded = "ley inferior a 999"
        return a

    # 2) Tipo de moneda
    ct = coin_type(t, full)
    if ct:
        a.coin_type, per_coin = ct.name, ct.fine_oz
    elif GENERIC_OUNCE.search(t):
        a.coin_type, per_coin = "Onza genérica", 0.999
    else:
        a.excluded = "no parece una onza de plata"
        return a

    # 3) Confianza: el nombre o "onza" en el título, más pistas que lo confirmen.
    confirms = bool(re.search(r"\b(1\s*oz|1\s*onza|onza|31[.,]1|999|9999|plata\s+(pura|fina))\b", full))
    if ct and ct.needs == "plata":
        a.confidence = "alta" if confirms else "media"
    else:
        a.confidence = "media" if confirms else "baja"

    # 4) Cantidad (lotes / tubos)
    per_unit = bool(PER_UNIT.search(full))
    a.quantity = 1 if per_unit else _find_quantity(t, d)
    if per_unit:
        a.notes.append("precio por unidad")
    if a.quantity > 1:
        a.notes.append(f"lote de {a.quantity}")
        a.confidence = {"alta": "media", "media": "baja"}.get(a.confidence, a.confidence)

    a.fine_oz = round(per_coin * a.quantity, 4)
    return a


# --------------------------------------------------------------------------- precio

# Si un lote sale por debajo de este % del valor de la plata, casi seguro que el precio es por
# unidad ("Tubo de 25 Maple... 76 €"): se recalcula como una sola moneda.
LOT_PER_UNIT_PREMIUM_PCT = -35.0


def evaluate(a: Analysis, price: float, spot_eur_oz: float) -> dict:
    """Métricas de precio de un anuncio que es objetivo (a.is_target)."""
    quantity, fine_oz, notes = a.quantity, a.fine_oz, list(a.notes)
    if quantity > 1 and price / (fine_oz * spot_eur_oz) - 1 < LOT_PER_UNIT_PREMIUM_PCT / 100:
        fine_oz = round(fine_oz / quantity, 4)
        quantity = 1
        notes = [n for n in notes if not n.startswith("lote")] + ["precio probablemente por unidad"]
    melt = fine_oz * spot_eur_oz
    return {
        "quantity": quantity,
        "fine_oz": fine_oz,
        "price_per_coin": round(price / quantity, 2),
        "melt_value_eur": round(melt, 2),
        "premium_pct": round((price / melt - 1) * 100, 1),
        "notes": notes,
    }
