from __future__ import annotations

from fastapi import FastAPI, Response

from .api.routes import router
from .core import config, metrics
from .core.logging import configure_logging
from .core.middleware import MetricsMiddleware
from .core.tracing import configure_tracing

configure_logging()
configure_tracing()

settings = config.Settings()

app = FastAPI(
    title="Renewal Desk Agent",
    version="0.1.0",
    description="Decision-support agent for SaaS renewals (RAG + guardrails)",
)
app.add_middleware(MetricsMiddleware)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "commit": settings.commit_sha}


@app.get("/metrics", include_in_schema=False)
def metrics_endpoint() -> Response:
    payload, content_type = metrics.metrics_response()
    return Response(content=payload, media_type=content_type)


def include_routes(application: FastAPI) -> None:
    application.include_router(router)


def create_app() -> FastAPI:
    include_routes(app)
    return app


include_routes(app)
