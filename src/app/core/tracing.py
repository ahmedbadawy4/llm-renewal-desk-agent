from __future__ import annotations

import logging

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:  # pragma: no cover - optional dep for scaffolding
    trace = None

logger = logging.getLogger(__name__)


def configure_tracing(service_name: str = "renewal-desk-api") -> None:
    if trace is None:
        logger.info("OpenTelemetry not installed; skipping tracing setup")
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    processor = BatchSpanProcessor(OTLPSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    logger.info("Tracing configured for service=%s", service_name)


__all__ = ["configure_tracing"]
