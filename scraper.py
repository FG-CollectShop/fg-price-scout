import json
import logging
import re
from typing import Optional

import curl_cffi.requests as requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def scrape_tcgplayer_price(product_id: int) -> Optional[int]:
    """Return market price in cents for a TCGPlayer product ID, or None if unavailable."""
    url = f"https://www.tcgplayer.com/product/{product_id}"
    try:
        resp = requests.get(url, impersonate="chrome120", headers=_HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error("fetch failed product_id=%d: %s", product_id, e)
        return None

    text = resp.text

    # Strategy 1: JSON-LD structured data
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', text, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            price = _extract_offer_price(data)
            if price is not None:
                logger.info("json-ld hit product_id=%d price=%.2f", product_id, price)
                return int(price * 100)
        except (json.JSONDecodeError, ValueError):
            continue
    logger.debug("json-ld miss product_id=%d", product_id)

    # Strategy 2: marketPrice anywhere in page text
    m = re.search(r'"marketPrice"\s*:\s*([\d.]+)', text)
    if m:
        try:
            price = float(m.group(1))
            logger.info("regex hit product_id=%d price=%.2f", product_id, price)
            return int(price * 100)
        except ValueError:
            pass
    logger.debug("regex miss product_id=%d", product_id)

    # Strategy 3: Next.js __NEXT_DATA__ blob
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            price = _walk_market_price(data)
            if price is not None:
                logger.info("next-data hit product_id=%d price=%.2f", product_id, price)
                return int(price * 100)
        except (json.JSONDecodeError, ValueError):
            pass
    logger.debug("next-data miss product_id=%d", product_id)

    logger.warning("no price found product_id=%d", product_id)
    return None


def _extract_offer_price(data) -> Optional[float]:
    if not isinstance(data, dict):
        return None
    offers = data.get("offers")
    if isinstance(offers, dict):
        p = offers.get("price")
        if p is not None:
            return float(p)
    if isinstance(offers, list) and offers:
        p = offers[0].get("price") if isinstance(offers[0], dict) else None
        if p is not None:
            return float(p)
    return None


def _walk_market_price(data, depth: int = 0) -> Optional[float]:
    if depth > 10:
        return None
    if isinstance(data, dict):
        v = data.get("marketPrice")
        if v is not None:
            try:
                return float(v)
            except (ValueError, TypeError):
                pass
        for val in data.values():
            result = _walk_market_price(val, depth + 1)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data[:20]:
            result = _walk_market_price(item, depth + 1)
            if result is not None:
                return result
    return None
