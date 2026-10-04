"""Cliente mínimo de la API pública de búsqueda de Wallapop."""
import logging
import time
from typing import Iterator

import requests

from . import config

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.wallapop.com/api/v3/search"
COLLECTIBLES_CATEGORY = 18000  # "Coleccionismo y arte": evita libros, joyas, ropa...
HEADERS = {
    "Accept": "application/json",
    "X-DeviceOS": "0",
    "Origin": "https://es.wallapop.com",
    "Referer": "https://es.wallapop.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
}


class WallapopClient:
    def __init__(self, delay: float = config.REQUEST_DELAY_S):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay

    def _get(self, params: dict) -> dict:
        for attempt in range(5):
            try:
                r = self.session.get(SEARCH_URL, params=params, timeout=30)
            except requests.RequestException as e:
                wait = 5 * (attempt + 1)
                log.warning("Error de red (%s); reintento en %ss", e, wait)
                time.sleep(wait)
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                wait = 10 * (attempt + 1)
                log.warning("HTTP %s; reintento en %ss", r.status_code, wait)
                time.sleep(wait)
                continue
            r.raise_for_status()
        raise RuntimeError("Wallapop no responde tras varios reintentos")

    def search(
        self,
        keywords: str,
        min_price: float = config.MIN_PRICE,
        max_price: float = config.MAX_PRICE,
        max_pages: int = config.MAX_PAGES_PER_KEYWORD,
    ) -> Iterator[dict]:
        """Itera los anuncios de una búsqueda ordenada por precio ascendente.

        Por tramos: cada `config.BAND_PAGES` páginas se relanza la búsqueda desde el último precio
        visto, para no depender de cuánto deje paginar Wallapop con un mismo token. Los anuncios
        repetidos en el solape los deduplica quien llama.
        """
        band_min = min_price
        pages = 0
        while pages < max_pages:
            params = {
                "source": "search_box",
                "keywords": keywords,
                "order_by": "price_low_to_high",
                "latitude": config.LATITUDE,
                "longitude": config.LONGITUDE,
                "category_id": COLLECTIBLES_CATEGORY,
                "min_sale_price": band_min,
                "max_sale_price": max_price,
            }
            band_pages, last_price = 0, band_min
            while True:
                data = self._get(params)
                pages += 1
                band_pages += 1
                items = data.get("data", {}).get("section", {}).get("payload", {}).get("items", [])
                yield from items
                if items:
                    last_price = float(items[-1].get("price", {}).get("amount") or last_price)
                next_page = data.get("meta", {}).get("next_page")
                if not items or not next_page:
                    return
                if pages >= max_pages:
                    log.info("'%s': alcanzado el límite de %s páginas (hasta %.0f €)", keywords, max_pages, last_price)
                    return
                time.sleep(self.delay)
                # Nuevo tramo, salvo que todo el tramo sea del mismo precio (no avanzaría).
                if band_pages >= config.BAND_PAGES and last_price > band_min:
                    band_min = last_price
                    break
                # El token de paginación ya lleva codificados todos los filtros.
                params = {"next_page": next_page}


def item_url(item: dict) -> str:
    return f"https://es.wallapop.com/item/{item.get('web_slug') or item['id']}"
