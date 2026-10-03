"""Análisis del texto de un anuncio: réplicas, peso y ley de la plata.

Todo son heurísticas sobre título + descripción. El objetivo es estimar los gramos de
plata fina para poder comparar el precio con el valor de fundición (spot).
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


# --------------------------------------------------------------------------- réplicas

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
    (r"\b(color|aspecto|tipo|acabado)\s+plata\b", "color plata"),
    (r"\bno\s+(es|son)\s+de\s+plata\b", "no es de plata"),
    (r"\bsin\s+plata\b", "sin plata"),
    (r"\b(alpaca|cuproniquel|niquel|laton|zamak|cobre|bronce|inox|acero|titanio|titanium)\b", "metal no plata"),
]

# Anuncios que no son monedas: se excluyen aunque mencionen "onza de plata".
ACCESSORY_PATTERN = re.compile(
    r"\b(capsulas?|tubos?|estuches?|cajas?|album(es)?|monsterbox|expositor(es)?|soportes?|"
    r"marcos?\s+para|lupas?|catalogos?|libros?|clasificador(es)?|carpetas?|bandejas?|"
    r"petaca|fiaschetta|llaveros?|colgantes?|pendientes?|anillos?|pulseras?|collar(es)?|"
    r"billetes?|loteria|decimos?|carnets?|tarjetas?|sellos?|discos?|vinilos?|postal(es)?|cromos?)\b"
)

# Muchos vendedores añaden palabras clave para salir en más búsquedas. Se eliminan.
SEO_SPAM = re.compile(
    r"(\btags?\b|\bpalabras(\s+clave)?\s*:|\bpalabras\s+clave\b|\betiquetas?\s*:|\bkeywords?\b|"
    r"\bno\s+leer\b|\bbusquedas?\s*:|\bsimilares?\s*:).*$"
)
HASHTAGS = re.compile(r"#\w+")

PER_UNIT = re.compile(
    r"\b(precio\s+(por\s+)?(unidad|moneda|onza|ud)|por\s+unidad|la\s+unidad|cada\s+una|c/u|/\s*ud\b|"
    r"\d+\s*(€|e|euros?)\s*(la|por|/)\s*(unidad|ud|moneda|onza)|(€|euros?)\s*/?\s*cada\b|/\s*cada\b|"
    r"hay\s+mas\s+unidades|salen\s+por|una\s+unidad\s*:)"
)

# "no es réplica", "no es una copia", "nada de copias"... → no cuenta como réplica
NEGATION = re.compile(r"(\bno\s+(es|son)\s+(una?s?\s+)?|\bnada\s+de\s+|\bsin\s+|\bni\s+)$")

WANTED_PATTERN = re.compile(r"^\s*(compro|busco|cambio|intercambio)\b")
# Compradores que publican como si vendieran: "Si tienes monedas de plata te las compro".
WANTED_DESC_PATTERN = re.compile(
    r"\b(te\s+las?\s+(puedo\s+)?compr[oa]r?|las?\s+compro|compro\s+(monedas|plata|onzas|lotes|duros)|"
    r"busco\s+(monedas|plata|onzas|duros)|comprador\s+serio|pago\s+(al\s+)?contado\s+por)\b"
)


def detect_replica(text: str) -> Optional[str]:
    """Devuelve el motivo si el texto (normalizado) indica réplica / no plata."""
    for pattern, reason in REPLICA_PATTERNS:
        for m in re.finditer(pattern, text):
            before = text[max(0, m.start() - 20) : m.start()]
            if reason not in ("no es de plata", "sin plata") and NEGATION.search(before):
                continue
            return reason
    return None


# --------------------------------------------------------------------------- peso y ley

NUM = r"(\d+(?:[.,]\d+)?)"

# "ley 0,625", "plata 0.500", "aleación: plata 0.835"... (cualquier ley explícita)
GENERIC_PURITY = re.compile(r"\b(ley|plata|aleacion|ag)\b[^\d]{0,15}0[.,](\d{3})\b")
# "pureza 64% de plata", "plata al 50%"
PERCENT_PURITY = re.compile(r"\b(\d{2}(?:[.,]\d)?)\s*%\s*(de\s+)?(plata|ag)\b|\bplata\s+(al\s+)?(\d{2}(?:[.,]\d)?)\s*%")

PURITY_PATTERNS = [
    (r"\b0?[.,]?9999\b", 0.9999),
    (r"\b(?:0[.,])?999\b|\bplata\s+(fina|pura)\b|\bfine\s+silver\b", 0.999),
    (r"\b(?:0[.,])?958\b|\bbritannia\s+silver\b", 0.958),
    (r"\b(?:0[.,])?925\b|\bsterling\b|\bley\s+925\b", 0.925),
    (r"\b(?:0[.,])?903\b", 0.903),
    (r"\b0[.,]900\b|\b(ley|plata)\s+(de\s+)?900\b|\b900\s*(milesimas|‰|/1000)", 0.900),
    (r"\b(?:0[.,])?835\b", 0.835),
    (r"\b0[.,]800\b|\b(ley|plata)\s+(de\s+)?800\b|\b800\s*(milesimas|‰|/1000)", 0.800),
    (r"\b(?:0[.,])?720\b", 0.720),
]


@dataclass
class CoinSpec:
    name: str
    weight_g: float
    purity: float
    pattern: str


# Monedas habituales en Wallapop cuyo peso/ley se conoce aunque el anuncio no lo diga.
KNOWN_COINS = [
    CoinSpec("Cincuentín", 168.75, 0.925, r"\bcincuentin"),
    CoinSpec("2000 pesetas", 18.0, 0.925, r"\b2\.?000\s*(pts|ptas|pesetas)\b"),
    CoinSpec("12 euros", 18.0, 0.925, r"(monedas?\s+de\s+12\s*(euros?|€|eur)\b|\b12\s*(euros?|€|eur)\s+(de\s+)?(plata|espana|fnmt)\b)"),
    CoinSpec("30 euros", 18.0, 0.925, r"(monedas?\s+de\s+30\s*(euros?|€|eur)\b|\b30\s*(euros?|€|eur)\s+(de\s+)?(plata|espana|fnmt)\b)"),
    CoinSpec("10 euros FNMT", 27.0, 0.925, r"(monedas?\s+de\s+10\s*(euros?|€|eur)\b|\b10\s*(euros?|€|eur)\s+(de\s+)?(plata|espana|fnmt)\b)"),
    CoinSpec("100 pesetas 1966", 19.0, 0.800, r"\b100\s*(pts|ptas|pesetas)\b.{0,40}\b1966\b|\b1966\b.{0,40}\b100\s*(pts|ptas|pesetas)\b"),
    CoinSpec("Duro (5 pesetas)", 25.0, 0.900, r"\b(duros?|5\s*(pts|ptas|pesetas))\b.{0,40}\b18[6-9]\d\b|\b18[6-9]\d\b.{0,40}\b(duros?|5\s*(pts|ptas|pesetas))\b|\bduros?\s+(de\s+)?plata\b"),
    CoinSpec("2 pesetas", 10.0, 0.835, r"\b2\s*(pts|ptas|pesetas)\b.{0,40}\b(18[6-9]\d|190\d)\b"),
    CoinSpec("1 peseta", 5.0, 0.835, r"\b1\s*(pta|peseta)\b.{0,40}\b(18[6-9]\d|190\d)\b"),
    CoinSpec("8 reales", 27.0, 0.903, r"\b8\s*reales\b"),
    CoinSpec("Thaler María Teresa", 28.07, 0.833, r"\b(thaler|taler|tálero|talero)\b.{0,30}\bmaria\s+teresa\b|\bmaria\s+teresa\b.{0,30}\b(thaler|taler|talero)\b"),
    CoinSpec("Panda", 30.0, 0.999, r"\bpanda\b.{0,30}\b(plata|oz|onza|30\s*g)|\b(plata|onza)\b.{0,30}\bpanda\b"),
    # EE. UU. (plata 900 hasta 1964)
    CoinSpec("Dólar Morgan/Peace", 26.73, 0.900, r"\b(morgan|peace)\s+(silver\s+)?dollar\b|\bdolar\s+(morgan|peace)\b"),
    CoinSpec("Half dollar", 12.5, 0.900, r"\b(half\s+dollar|medio\s+dolar)\b.{0,40}\b(19[0-5]\d|196[0-4])\b"),
    CoinSpec("Quarter", 6.25, 0.900, r"\bquarter\b.{0,40}\b(19[0-5]\d|196[0-4])\b"),
    CoinSpec("Dime", 2.5, 0.900, r"\bdime\b.{0,40}\b(19[0-5]\d|196[0-4])\b"),
]

# Bullion que salvo indicación contraria es de 1 onza de plata 999. Solo se busca en el título.
# Los nombres "fuertes" bastan; los ambiguos ("libertad", "britannia"...) aparecen también en
# monedas pequeñas antiguas, así que exigen que el título diga onza/oz.
BULLION_STRONG = r"maple\s*leaf|filarmonica|philharmoniker|krugerrand|silver\s+eagle|american\s+eagle|kookaburra|arca\s+de\s+noe|noah'?s\s+ark"
BULLION_WEAK = r"britannia|libertad|koala|kangaroo|canguro|lunar|buffalo|bufalo"
BULLION_1OZ = re.compile(rf"\b({BULLION_STRONG}|{BULLION_WEAK})\b")
OUNCE_WORD = re.compile(r"\b(onzas?|oz|bullion|inversion)\b")
SMALL_COIN = re.compile(r"\b(centavos?|centimos?|cents?|dimes?|penny|peniques?|pence|shillings?|chelin(es)?|reis|florin)\b")


def _bullion_in_title(title: str) -> Optional[str]:
    if SMALL_COIN.search(title):
        return None
    m = re.search(rf"\b({BULLION_STRONG})\b", title)
    if m:
        return m.group(1)
    m = re.search(rf"\b({BULLION_WEAK})\b", title)
    if m and OUNCE_WORD.search(title):
        return m.group(1)
    return None

WEIGHT_G = re.compile(NUM + r"\s*(g|gr|grs|gramos?|gms|grams?)\b")
WEIGHT_KG = re.compile(NUM + r"\s*(kg|kilos?)\b|\b(un|1)\s+kilo\b")
WEIGHT_OZ = re.compile(r"(\d+(?:[.,]\d+)?|1/2|1/4|1/10|media|un|una)\s*(oz|onzas?)\b")
FRACTIONS = {"1/2": 0.5, "media": 0.5, "1/4": 0.25, "1/10": 0.1, "un": 1, "una": 1}

TOTAL_HINT = re.compile(r"\b(total|en\s+total|peso\s+total|todas?\s+juntas?)\b")
QUANTITY_PATTERNS = [
    re.compile(r"\blote\s+(?:de\s+)?(\d{1,3})\b"),
    re.compile(r"\b(\d{1,3})\s+(?:monedas|onzas|duros)\b"),
    re.compile(r"\b(\d{1,3})\s*x\s+(?:moneda|onza)"),
]
WORD_NUMBERS = {"dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
QUANTITY_WORDS = re.compile(r"\b(" + "|".join(WORD_NUMBERS) + r")\s+(?:monedas|onzas|duros)\b")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


@dataclass
class Analysis:
    is_replica: bool = False
    replica_reason: Optional[str] = None
    is_wanted: bool = False             # anuncio de compra, no de venta
    is_accessory: bool = False          # cápsulas, tubos, estuches...
    weight_g: Optional[float] = None    # peso bruto de UNA moneda (o total si weight_is_total)
    purity: Optional[float] = None
    quantity: int = 1
    fine_grams: Optional[float] = None  # plata fina total del anuncio
    source: Optional[str] = None        # de dónde sale la estimación
    confidence: str = "ninguna"         # alta | media | baja | ninguna
    notes: list = field(default_factory=list)


def _find_weight(text: str) -> tuple[Optional[float], bool]:
    """Primer peso plausible del texto. Devuelve (gramos, es_peso_total)."""
    best = None
    for m in WEIGHT_KG.finditer(text):
        grams = 1000.0 if m.group(1) is None else _num(m.group(1)) * 1000
        best = (m.start(), grams)
        break
    for m in WEIGHT_OZ.finditer(text):
        raw = m.group(1)
        oz = FRACTIONS.get(raw) or _num(raw)
        if 0 < oz <= 100 and (best is None or m.start() < best[0]):
            best = (m.start(), oz * TROY_OUNCE_G)
        break
    for m in WEIGHT_G.finditer(text):
        grams = _num(m.group(1))
        if 1 <= grams <= 5000:
            if best is None or m.start() < best[0]:
                best = (m.start(), grams)
            break
    if best is None:
        return None, False
    pos, grams = best
    is_total = bool(TOTAL_HINT.search(text[max(0, pos - 25) : pos + 30]))
    return grams, is_total


def _find_purity(text: str) -> Optional[float]:
    m = PERCENT_PURITY.search(text)
    if m:
        pct = _num(m.group(1) or m.group(5))
        if 30 <= pct <= 99.99:
            return pct / 100
    m = GENERIC_PURITY.search(text)
    if m and 300 <= int(m.group(2)) <= 999:
        return int(m.group(2)) / 1000
    for pattern, value in PURITY_PATTERNS:
        if re.search(pattern, text):
            return value
    return None


def is_accessory(title: str) -> bool:
    """El título habla de un accesorio ("Lote 10 cápsulas") y no de una moneda "con estuche"."""
    for m in ACCESSORY_PATTERN.finditer(title):
        before = title[max(0, m.start() - 15) : m.start()]
        if not re.search(r"\b(con|en|y|incluye|mas|\+)\s+(su\s+|sus\s+|el\s+|la\s+)?$", before):
            return True
    return False


def _find_quantity(title: str, desc: str) -> int:
    """Unidades del lote. En la descripción solo vale "lote de N": otros números
    ("tirada de 100 piezas", "pedidos >= 20 monedas") dan demasiados falsos positivos."""
    for pattern in QUANTITY_PATTERNS:
        m = pattern.search(title)
        if m and 2 <= int(m.group(1)) <= 200:
            return int(m.group(1))
    m = QUANTITY_WORDS.search(title)
    if m:
        return WORD_NUMBERS[m.group(1)]
    m = QUANTITY_PATTERNS[0].search(desc)
    if m and 2 <= int(m.group(1)) <= 200:
        return int(m.group(1))
    return 1


def analyze(title: str, description: str) -> Analysis:
    t = normalize(title)
    d = HASHTAGS.sub(" ", SEO_SPAM.sub(" ", normalize(description)))
    full = f"{t} . {d}"
    a = Analysis()

    a.is_wanted = bool(WANTED_PATTERN.search(t) or WANTED_DESC_PATTERN.search(d))
    a.is_accessory = is_accessory(t)
    reason = detect_replica(full)
    if not reason and re.search(r"\boro\b", t) and "plata" not in t:
        reason = "es de oro"
    if reason:
        a.is_replica, a.replica_reason = True, reason

    purity = _find_purity(full)
    per_unit = bool(PER_UNIT.search(full))
    quantity = 1 if per_unit else _find_quantity(t, d)
    if per_unit:
        a.notes.append("precio por unidad")
    silver_in_title = bool(re.search(r"\b(plata|silver|ag)\b", t) or BULLION_1OZ.search(t))

    # 1) Peso explícito (primero el título, que suele ser más fiable)
    weight, is_total = _find_weight(t)
    if weight is None:
        weight, is_total = _find_weight(d)
    if weight is not None and (purity is not None or silver_in_title):
        a.weight_g = weight
        a.source = "peso indicado"
        if purity is None:
            # Las onzas y kilos de inversión son 999; en el resto asumimos la ley más común,
            # pero es una suposición arriesgada (hay monedas de plata de ley 0,100).
            looks_bullion = bool(WEIGHT_OZ.search(t) or WEIGHT_KG.search(t) or _bullion_in_title(t))
            purity = 0.999 if looks_bullion else 0.900
            a.notes.append(f"ley no indicada, se asume {purity:.3f}")
            a.confidence = "media" if looks_bullion else "baja"
        else:
            a.confidence = "alta"
        if is_total:
            quantity = 1
            a.notes.append("peso total del lote")
    elif weight is None:
        # 2) Moneda conocida. Se busca en el título; en la descripción (solo el arranque, más
        #    abajo suele haber listas de otras monedas del vendedor) únicamente si el título dice
        #    que es de plata y no es un lote: los lotes variados mencionan muchas monedas.
        generic_silver_title = quantity == 1 and re.search(r"\bplata\b", t)
        scope = f"{t} . {d[:250]}" if generic_silver_title else t
        for coin in KNOWN_COINS:
            if re.search(coin.pattern, scope):
                a.weight_g, purity = coin.weight_g, coin.purity
                a.source = coin.name
                a.confidence = "media"
                break
        else:
            # 3) Bullion de 1 onza
            name = _bullion_in_title(t)
            if name:
                a.weight_g = TROY_OUNCE_G
                purity = purity or 0.999
                a.source = f"bullion 1 oz ({name})"
                a.confidence = "media"

    if a.weight_g is None:
        return a

    a.purity = purity
    a.quantity = quantity
    a.fine_grams = round(a.weight_g * purity * quantity, 2)
    if quantity > 1:
        a.notes.append(f"lote de {quantity}")
        a.confidence = {"alta": "media", "media": "baja"}.get(a.confidence, a.confidence)
    return a
