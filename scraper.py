import logging
from typing import Optional

import curl_cffi.requests as requests

logger = logging.getLogger(__name__)

# TCGPlayer exposes two unauthenticated JSON endpoints their own storefront JS
# uses. Both return market prices; we prefer /pricepoints (smaller payload,
# per-printing breakdown) and fall back to /details (has a top-level marketPrice).
_PRICEPOINTS_URL = "https://mpapi.tcgplayer.com/v2/product/{id}/pricepoints"
_DETAILS_URL = "https://mp-search-api.tcgplayer.com/v2/product/{id}/details"

_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.tcgplayer.com",
    "Referer": "https://www.tcgplayer.com/",
}


def scrape_tcgplayer_price(product_id: int) -> Optional[int]:
    """Return market price in cents for a TCGPlayer product ID, or None if unavailable."""
    price = _from_pricepoints(product_id)
    if price is not None:
        return price
    return _from_details(product_id)


def _from_pricepoints(product_id: int) -> Optional[int]:
    url = _PRICEPOINTS_URL.format(id=product_id)
    try:
        resp = requests.get(url, impersonate="chrome120", headers=_HEADERS, timeout=15)
    except Exception as e:
        logger.error("pricepoints fetch failed id=%d: %s", product_id, e)
        return None
    if resp.status_code != 200:
        logger.debug("pricepoints HTTP %d id=%d", resp.status_code, product_id)
        return None
    try:
        rows = resp.json()
    except ValueError:
        logger.warning("pricepoints non-json id=%d", product_id)
        return None
    if not isinstance(rows, list):
        return None
    # Prefer "Normal", then any row with a non-null marketPrice.
    normal = next((r for r in rows if r.get("printingType") == "Normal" and r.get("marketPrice")), None)
    chosen = normal or next((r for r in rows if r.get("marketPrice")), None)
    if not chosen:
        logger.debug("pricepoints no market price id=%d rows=%r", product_id, rows)
        return None
    price = chosen.get("marketPrice")
    logger.info("pricepoints hit id=%d printing=%s price=%.2f", product_id, chosen.get("printingType"), price)
    return int(round(float(price) * 100))


def _from_details(product_id: int) -> Optional[int]:
    url = _DETAILS_URL.format(id=product_id)
    try:
        resp = requests.get(url, impersonate="chrome120", headers=_HEADERS, timeout=15)
    except Exception as e:
        logger.error("details fetch failed id=%d: %s", product_id, e)
        return None
    if resp.status_code != 200:
        logger.debug("details HTTP %d id=%d", resp.status_code, product_id)
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    price = data.get("marketPrice")
    if not price:
        logger.warning("details no market price id=%d", product_id)
        return None
    logger.info("details hit id=%d price=%.2f", product_id, price)
    return int(round(float(price) * 100))


def scrape_tcgplayer_product(product_id: int) -> Optional[dict]:
    """Fetch full product metadata (name, set, price, product line) from TCGPlayer.

    Used by the admin form to auto-fill purchase details when the user enters
    a TCGPlayer product ID. Distinct from scrape_tcgplayer_price which only
    returns cents (kept lean for the hourly pricesync cron).
    """
    url = _DETAILS_URL.format(id=product_id)
    try:
        resp = requests.get(url, impersonate="chrome120", headers=_HEADERS, timeout=15)
    except Exception as e:
        logger.error("product fetch failed id=%d: %s", product_id, e)
        return None
    if resp.status_code != 200:
        logger.debug("product HTTP %d id=%d", resp.status_code, product_id)
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    name = data.get("productName")
    if not name:
        logger.warning("product no name id=%d", product_id)
        return None
    price = data.get("marketPrice")
    return {
        "product_id":         product_id,
        "name":               name,
        "set_name":           data.get("setName"),
        "product_line":       data.get("productLineName"),
        "market_price_cents": int(round(float(price) * 100)) if price else None,
    }
