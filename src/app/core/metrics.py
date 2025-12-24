from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUEST_COUNTER = Counter(
    "api_requests_total",
    "Count of HTTP requests",
    labelnames=("path", "method", "status"),
)
REQUEST_LATENCY = Histogram(
    "api_request_latency_seconds",
    "Latency for HTTP requests",
    labelnames=("path", "method"),
)
AGENT_REQUESTS = Counter(
    "agent_requests_total",
    "Renewal brief generations",
    labelnames=("status",),
)
AGENT_TOKENS = Counter(
    "agent_tokens_total",
    "Approximate token usage",
    labelnames=("direction",),
)
LLM_TOKENS = Counter(
    "llm_tokens_total",
    "LLM token usage",
    labelnames=("direction",),
)
LLM_ERRORS = Counter(
    "llm_errors_total",
    "LLM errors",
    labelnames=("reason",),
)
VALIDATION_FAILURES = Counter(
    "validation_failures_total",
    "Schema/citation validation failures",
    labelnames=("stage",),
)
CITATION_COVERAGE = Gauge(
    "citation_coverage_ratio",
    "Share of brief sections with citations",
)
LLM_LATENCY = Histogram(
    "llm_request_latency_seconds",
    "Latency for LLM requests",
    labelnames=("provider",),
)


def record_agent_completion(status: str) -> None:
    AGENT_REQUESTS.labels(status=status).inc()


def record_token_usage(direction: str, amount: float) -> None:
    if amount <= 0:
        return
    AGENT_TOKENS.labels(direction=direction).inc(amount)


def record_llm_token_usage(direction: str, amount: float) -> None:
    if amount <= 0:
        return
    LLM_TOKENS.labels(direction=direction).inc(amount)


def record_llm_error(reason: str) -> None:
    LLM_ERRORS.labels(reason=reason).inc()


def record_validation_failure(stage: str) -> None:
    VALIDATION_FAILURES.labels(stage=stage).inc()


def record_citation_coverage(ratio: float) -> None:
    CITATION_COVERAGE.set(ratio)


def metrics_response() -> tuple[bytes, str]:
    payload = generate_latest()
    return payload, CONTENT_TYPE_LATEST


class RequestTimer:
    def __init__(self, path: str, method: str) -> None:
        self.path = path
        self.method = method
        self.start = time.perf_counter()

    def observe(self) -> None:
        duration = time.perf_counter() - self.start
        REQUEST_LATENCY.labels(path=self.path, method=self.method).observe(duration)


class LLMRequestTimer:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.start = time.perf_counter()

    def observe(self) -> None:
        duration = time.perf_counter() - self.start
        LLM_LATENCY.labels(provider=self.provider).observe(duration)
