"""Configuración central. Todo se puede sobreescribir con variables de entorno."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("PLATA_DB", BASE_DIR / "data" / "plata.db"))

# Búsquedas que se lanzan en Wallapop. Se deduplican por id de anuncio.
KEYWORDS = [
    "moneda plata",
    "monedas plata",
    "onza plata",
    "duro plata",
    "5 pesetas plata",
    "2000 pesetas plata",
    "12 euros plata",
    "30 euros plata",
    "10 euros plata",
    "100 pesetas 1966",
    "8 reales plata",
    "maple leaf plata",
    "britannia plata",
    "filarmonica plata",
    "krugerrand plata",
    "libertad plata",
    "silver eagle",
    "kookaburra plata",
    "thaler maria teresa",
]

MIN_PRICE = float(os.environ.get("PLATA_MIN_PRICE", 3))      # filtra "precio a convenir" (0 €, 1 €...)
MAX_PRICE = float(os.environ.get("PLATA_MAX_PRICE", 400))    # techo de búsqueda
MAX_PAGES_PER_KEYWORD = int(os.environ.get("PLATA_MAX_PAGES", 120))  # ~40 anuncios por página
REQUEST_DELAY_S = float(os.environ.get("PLATA_DELAY", 1.0))  # cortesía con el servidor

# Coordenadas de referencia (la búsqueda es nacional; solo afecta a la distancia mostrada).
LATITUDE = float(os.environ.get("PLATA_LAT", 40.4168))
LONGITUDE = float(os.environ.get("PLATA_LON", -3.7038))

# Por debajo de este % sobre el valor de fundición, el anuncio es "demasiado bueno para ser
# verdad": casi siempre es un precio por unidad en un lote, una réplica no declarada o un error
# al leer el peso. Vender un 12 € a su valor facial (~-55 %) sí es una oportunidad real típica.
SUSPICIOUS_PREMIUM_PCT = float(os.environ.get("PLATA_SUSPICIOUS", -70))

TOP_N = 20
