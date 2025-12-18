# Data Flow

This document traces a renewal request from ingestion to response and highlights validation/budget gates at each step.

## 1. Ingestion
1. `POST /ingest` receives contract PDF + invoices CSV + optional usage CSV.
2. Files land in object storage bucket under `/vendor_id/{doc_hash}` with metadata recorded in Postgres.
3. Parsing job (Celery worker) extracts:
   - Page-level text with offsets + page map
   - Table data (pricing schedules, invoice rows)
   - Deterministic fields (term start/end, notice window, currency) using regex/pyparsing
4. Extracted facts persisted in structured tables; raw + normalized text hashed for caching.
5. Embedding job pushes chunks into pgvector collections (`contracts`, `invoices`, `usage`).

## 2. Request processing (`POST /renewal-brief`)
1. FastAPI endpoint authenticates caller, loads vendor context, and enforces per-tenant budget counters.
2. Agent runner creates a plan with subgoals: terms, spend trend, usage delta, risk flags, negotiation levers, draft email.
3. For each subgoal, router selects retrieval strategy:
   - Terms → contract chunk search (hybrid)
   - Spend → invoices table aggregation (deterministic) + embeddings for missing context
   - Usage delta → usage CSV summary
   - Risk flags → heuristics + targeted search queries
4. Router issues tool calls (via gateway) to fetch normalized data or text snippets. Gateway validates payloads, RBAC, and increments budget metrics.
5. Retrieved snippets sanitized (quoted, instructions stripped) before being passed to the reasoning LLM.
6. Reasoning LLM (larger model) receives: system policy, plan context, tool outputs, and must respond with `RenewalBrief` schema.
7. Validator checks schema compliance, ensures each field has citation(s), runs citation-to-source verification, ensures costs within budget.
8. If validation fails, agent retries with correction prompt (up to configured max) or responds with `unknown` plus diagnostic info.

## 3. Post-processing + Observability
1. Successful responses stored with request metadata (vendor_id, prompt_version, retrieval config hash, tokens, tool counts, citations).
2. Logs/traces flushed via OpenTelemetry to collector → Grafana Tempo/Loki.
3. Metrics exported (Prometheus format) for latency, unknown rate, citation coverage, token spend, cache hits.
4. `/debug/trace/{request_id}` uses stored artifacts to reconstruct the above steps for debugging.

## Batch mode (precompute renewals)
- Nightly job scans vendors with renewals in next 60 days, runs `renewal-brief` in batch, stores results + costs, and alerts owners for review.

Each stage exposes hooks for eval harnesses: ingestion correctness tests, retrieval accuracy benchmarks, and agent schema/citation validation.
