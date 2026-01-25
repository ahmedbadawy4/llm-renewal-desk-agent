from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from . import metrics
from .rate_limit import get_rate_limiter


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        method = request.method
        timer = metrics.RequestTimer(path=path, method=method)
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            status_code = getattr(response, "status_code", 500)
            metrics.REQUEST_COUNTER.labels(path=path, method=method, status=str(status_code)).inc()
            timer.observe()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.rate_limiter = get_rate_limiter(max_requests, window_seconds)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        identifier = f"{client_ip}:{request.url.path}"

        if not self.rate_limiter.is_allowed(identifier):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        return await call_next(request)
