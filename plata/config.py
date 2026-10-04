"""Configuración central. Todo se puede sobreescribir con variables de entorno."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = Path(os.environ.get("PLATA_STATE", BASE_DIR / "data" / "estado.json"))

# Búsquedas que se lanzan en Wallapop (se deduplican por id de anuncio). Solo onzas bullion.
# Wallapop busca por palabras sueltas: "libertad onza plata" devolvía 9.000 anuncios (casi todos
# ya vistos con "onza plata") y costaba 4 minutos. Mejor pocas búsquedas y concretas; las genéricas
# ("onza plata", "1 oz plata") ya recogen Lunar, Buffalo, etc.
KEYWORDS = [
    "onza plata",
    "1 oz plata",
    "maple leaf plata",
    "filarmonica plata",
    "krugerrand plata",
    "panda plata",
    "silver eagle",
    "american eagle plata",
    "britannia plata",
    "kookaburra plata",
    "koala plata",
    "canguro plata",
    "libertad plata",
    "arca de noe plata",
    "elefante somalia plata",
]

# Una onza de plata vale ~50-60 €: por debajo de 15 € son réplicas o "precio a convenir".
# El techo deja entrar lotes y tubos de varias onzas.
MIN_PRICE = float(os.environ.get("PLATA_MIN_PRICE", 15))
MAX_PRICE = float(os.environ.get("PLATA_MAX_PRICE", 2000))
MAX_PAGES_PER_KEYWORD = int(os.environ.get("PLATA_MAX_PAGES", 300))  # ~40 anuncios por página
BAND_PAGES = 50                                              # ver WallapopClient.search
REQUEST_DELAY_S = float(os.environ.get("PLATA_DELAY", 1.0))  # cortesía con el servidor

# Coordenadas de referencia (la búsqueda es nacional; solo afecta a la distancia mostrada).
LATITUDE = float(os.environ.get("PLATA_LAT", 40.4168))
LONGITUDE = float(os.environ.get("PLATA_LON", -3.7038))

# Una onza bullion casi nunca se vende muy por debajo del spot. Más de un 30 % por debajo suele
# ser réplica no declarada, precio por unidad mal leído o un error: va a "Demasiado buenas".
SUSPICIOUS_PREMIUM_PCT = float(os.environ.get("PLATA_SUSPICIOUS", -30))

# Anuncios que llevan este tiempo sin aparecer se borran del estado (vendidos o retirados).
FORGET_AFTER_DAYS = 30
RUNS_TO_KEEP = 90
