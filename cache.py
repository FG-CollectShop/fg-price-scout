import sqlite3
import threading
from typing import Optional


class PriceCache:
    def __init__(self, db_path: str):
        self._path = db_path
        self._lock = threading.Lock()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _init(self):
        with self._lock, self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_cache (
                    product_id    INTEGER PRIMARY KEY,
                    market_price_cents INTEGER NOT NULL,
                    fetched_at    INTEGER NOT NULL
                )
            """)

    def get(self, product_id: int) -> Optional[dict]:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT market_price_cents, fetched_at FROM price_cache WHERE product_id = ?",
                (product_id,),
            ).fetchone()
        if row:
            return {"product_id": product_id, "market_price_cents": row[0], "fetched_at": row[1]}
        return None

    def set(self, product_id: int, market_price_cents: int, fetched_at: int):
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO price_cache (product_id, market_price_cents, fetched_at) VALUES (?, ?, ?)",
                (product_id, market_price_cents, fetched_at),
            )
