# app/core/cache.py
"""Tiny thread-safe in-memory TTL cache.

Good enough for a single-instance backend (e.g. Render free tier). If you
later scale to multiple workers/instances, swap this for Redis/Upstash - the
public API (get/set/invalidate) can stay the same.
"""

import threading
import time
from typing import Any, Optional


class TTLCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            self._store[key] = (value, time.time() + (ttl if ttl is not None else self.ttl))

    def invalidate(self, key: Optional[str] = None) -> None:
        with self._lock:
            if key is None:
                self._store.clear()
            else:
                self._store.pop(key, None)


# Product catalog changes rarely; cache each category for 60 seconds.
product_cache = TTLCache(ttl_seconds=60)
