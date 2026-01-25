from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._requests: Dict[str, list[datetime]] = defaultdict(list)

    def is_allowed(self, identifier: str) -> bool:
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)

            requests = self._requests[identifier]
            requests = [r for r in requests if r > cutoff]
            self._requests[identifier] = requests

            if len(requests) >= self.max_requests:
                return False

            requests.append(now)
            return True

    def reset(self, identifier: str) -> None:
        with self._lock:
            self._requests.pop(identifier, None)


_global_rate_limiter: RateLimiter | None = None


def get_rate_limiter(max_requests: int = 100, window_seconds: int = 60) -> RateLimiter:
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(max_requests, window_seconds)
    return _global_rate_limiter
