from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from . import metrics


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
