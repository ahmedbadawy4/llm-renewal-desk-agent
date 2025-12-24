# Architecture

This repo models a production-ready "Contract Renewal Desk" agent with four primary services and shared infrastructure.

## 1. Ingestion Service
- Pulls documents from manual uploads or connectors (Drive/SharePoint/Jira/etc.).
- Converts PDF -> text (page-segmented), extracts structured fields (dates, pricing tables), and stores raw blobs + parsed text in object storage (MinIO/S3) plus metadata in Postgres.
- Emits events (`doc_ingested`) so downstream components can update embeddings or caches.

## 2. Knowledge Layer
- **Object store** (`storage/object_store.py`): raw PDFs, CSVs, SOC2 reports; encrypted and referenced via signed URLs.
- **Relational store** (`storage/postgres.py`): vendor metadata, invoices, usage summaries, extracted facts, eval scores.
- **Vector index** (`storage/vector_store.py`): pgvector schema with separate collections per source (contracts, invoices, notes) and hybrid indexes combining embeddings with BM25.
- Embedding pipeline runs asynchronously (Celery/worker) to avoid blocking ingestion.

## 3. Agent API Service
- FastAPI app exposes `POST /ingest`, `POST /renewal-brief`, and future `/debug/trace/{request_id}` endpoints.
- Agent runner orchestrates: plan -> retrieval routing -> tool calls (contract/invoice/usage) -> reasoning LLM -> validator.
- Tool gateway enforces RBAC and schema validation before delegating to lower-level services.
- Outputs conform to `agent.schemas` with citation metadata `(doc_id, page, span)` per field.

## 4. Observability + Ops
- OpenTelemetry instrumentation wraps HTTP handlers, tool calls, retrieval, and validators; traces shipped via OTLP to collector -> Grafana Tempo/Loki or OTEL exporter.
- Structured JSON logs (logging config) capture prompt version, retrieval config hash, tool-call count, token usage, and outcomes (`success`, `unknown`, `blocked`).
- Prometheus scrapes `/metrics` (FastAPI endpoint exposing `prometheus_client` counters/histograms) and feeds Grafana panels for latency, token spend, and request mix.
- `/debug/trace/{request_id}` reconstructs a detailed timeline for on-call debugging (planned for milestone 4).

## Security & Budget Enforcement Points
| Layer | Guardrail |
| --- | --- |
| Ingestion | Virus scanning hooks, file type allowlist, metadata validation |
| Retrieval | Sanitization removes injected instructions; router enforces per-source limits |
| Tools | Gateway enforces RBAC + schemas + rate limits + token/time budgets |
| Agent | Pydantic schema validation, citation enforcement, `unknown` fallback |
| Observability | Audit logs store doc IDs + tool names (no raw PII), budget breaches raise alerts |

## Deployment Mapping (AWS-ish)
- **App/API** -> ECS Fargate or EKS (via Terraform modules)
- **Object storage** -> S3 (MinIO locally)
- **DB** -> RDS Postgres with pgvector extension
- **Search** -> OpenSearch Serverless or Postgres full-text
- **Queue** -> SQS for ingestion + embedding workers
- **Observability** -> OTel Collector -> CloudWatch Metrics/Logs + managed Grafana

Refer to `docs/data-flow.md` for the step-by-step lifecycle of a renewal request and to `docs/threat-model.md` for adversarial considerations baked into the design.
