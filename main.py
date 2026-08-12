import logging
import os
import time

from fastapi import FastAPI, HTTPException

from cache import PriceCache
from scraper import scrape_tcgplayer_price

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="fg-price-scout", description="TCGPlayer market price scraper with cache")

CACHE_DB = os.getenv("CACHE_DB", "prices.db")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", str(7 * 24 * 3600)))  # 7 days

cache = PriceCache(CACHE_DB)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/price/{product_id}")
def get_price(product_id: int):
    cached = cache.get(product_id)
    if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL:
        return {**cached, "cached": True}

    price_cents = scrape_tcgplayer_price(product_id)
    if price_cents is None:
        raise HTTPException(status_code=404, detail=f"No price found for product {product_id}")

    fetched_at = int(time.time())
    cache.set(product_id, price_cents, fetched_at)
    return {
        "product_id": product_id,
        "market_price_cents": price_cents,
        "fetched_at": fetched_at,
        "cached": False,
    }
