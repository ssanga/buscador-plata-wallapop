"""Precio spot de la plata en EUR por gramo (fuentes gratuitas sin API key)."""
import logging

import requests

log = logging.getLogger(__name__)

TROY_OUNCE_G = 31.1034768


def get_spot() -> dict:
    """Devuelve {'usd_oz', 'usd_eur', 'eur_g'}. Lanza excepción si no hay datos."""
    usd_oz = _silver_usd_oz()
    usd_eur = _usd_to_eur()
    return {"usd_oz": usd_oz, "usd_eur": usd_eur, "eur_g": usd_oz * usd_eur / TROY_OUNCE_G}


def _silver_usd_oz() -> float:
    try:
        r = requests.get("https://api.gold-api.com/price/XAG", timeout=20)
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception as e:  # noqa: BLE001 - probamos la fuente alternativa
        log.warning("gold-api.com falló (%s); probando Yahoo Finance", e)
    r = requests.get(
        "https://query1.finance.yahoo.com/v8/finance/chart/SI=F?range=1d&interval=1d",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20,
    )
    r.raise_for_status()
    return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])


def _usd_to_eur() -> float:
    r = requests.get("https://api.frankfurter.dev/v1/latest?from=USD&to=EUR", timeout=20)
    r.raise_for_status()
    return float(r.json()["rates"]["EUR"])
