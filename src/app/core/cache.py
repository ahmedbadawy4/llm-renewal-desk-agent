from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CacheEntry:
    def __init__(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self.key = key
        self.value = value
        self.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class ResponseCache:
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()

    def _generate_key(self, *args: Any, **kwargs: Any) -> str:
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                return entry.value
            if entry:
                del self._cache[key]
            return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds or self.default_ttl
        with self._lock:
            if len(self._cache) >= self.max_size:
                self._evict_expired()
                if len(self._cache) >= self.max_size:
                    self._evict_oldest()

            self._cache[key] = CacheEntry(key, value, ttl)

    def _evict_expired(self) -> None:
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]

    def _evict_oldest(self) -> None:
        if not self._cache:
            return
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].expires_at)
        del self._cache[oldest_key]

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def cache_key(self, *args: Any, **kwargs: Any) -> str:
        return self._generate_key(*args, **kwargs)


_global_cache: Optional[ResponseCache] = None


def get_cache() -> ResponseCache:
    global _global_cache
    if _global_cache is None:
        _global_cache = ResponseCache()
    return _global_cache
