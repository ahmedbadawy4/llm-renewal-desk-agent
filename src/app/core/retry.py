from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from threading import Lock
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._lock = Lock()
        self._failures: deque[datetime] = deque(maxlen=failure_threshold)
        self._state = "closed"
        self._half_open_calls = 0
        self._opened_at: datetime | None = None

    def call(self, func: Callable[[], T]) -> T:
        with self._lock:
            if self._state == "open":
                if self._opened_at and (datetime.now() - self._opened_at).total_seconds() > self.recovery_timeout:
                    self._state = "half_open"
                    self._half_open_calls = 0
                    logger.info("Circuit breaker entering half-open state")
                else:
                    raise RuntimeError("Circuit breaker is open")

            if self._state == "half_open":
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = "open"
                    self._opened_at = datetime.now()
                    raise RuntimeError("Circuit breaker opened after half-open attempts")

        try:
            result = func()
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise e

    def _record_success(self) -> None:
        with self._lock:
            if self._state == "half_open":
                self._state = "closed"
                self._failures.clear()
                self._half_open_calls = 0
                logger.info("Circuit breaker closed after successful call")
            else:
                self._failures.clear()

    def _record_failure(self) -> None:
        with self._lock:
            now = datetime.now()
            self._failures.append(now)

            recent_failures = [f for f in self._failures if (now - f).total_seconds() < 60]

            if len(recent_failures) >= self.failure_threshold:
                self._state = "open"
                self._opened_at = now
                logger.warning(f"Circuit breaker opened after {len(recent_failures)} failures")


class RateLimiter:
    def __init__(self, max_calls: int, time_window: float) -> None:
        self.max_calls = max_calls
        self.time_window = time_window
        self._lock = Lock()
        self._calls: deque[datetime] = deque()

    def acquire(self) -> None:
        with self._lock:
            now = datetime.now()
            self._calls = deque([c for c in self._calls if (now - c).total_seconds() < self.time_window])

            if len(self._calls) >= self.max_calls:
                oldest_call = self._calls[0]
                wait_time = self.time_window - (now - oldest_call).total_seconds()
                if wait_time > 0:
                    time.sleep(wait_time)
                    now = datetime.now()
                    self._calls = deque([c for c in self._calls if (now - c).total_seconds() < self.time_window])

            self._calls.append(now)


def retry_with_backoff(
    config: RetryConfig | None = None,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    cfg = config or RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(cfg.max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < cfg.max_attempts - 1:
                        delay = min(
                            cfg.initial_delay * (cfg.exponential_base**attempt),
                            cfg.max_delay,
                        )
                        if cfg.jitter:
                            import random

                            delay = delay * (0.5 + random.random() * 0.5)

                        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {cfg.max_attempts} attempts failed")
                        raise

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry state")

        return wrapper

    return decorator


def with_circuit_breaker(
    breaker: CircuitBreaker | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    cb = breaker or CircuitBreaker()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return cb.call(lambda: func(*args, **kwargs))

        return wrapper

    return decorator


def with_rate_limit(
    limiter: RateLimiter | None = None,
    max_calls: int = 10,
    time_window: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    rl = limiter or RateLimiter(max_calls, time_window)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            rl.acquire()
            return func(*args, **kwargs)

        return wrapper

    return decorator
