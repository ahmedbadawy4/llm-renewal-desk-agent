# Renewal Desk Agent

Production-grade LLM decision-support agent for SaaS vendor renewals. It ingests contracts, invoices, and usage exports, runs hybrid retrieval + tool-gated reasoning, and produces a renewal brief with citations, risk flags, negotiation plan, and draft outreach. The repo is structured so anyone can clone it, run the API, hit `/renewal-brief`, open dashboards, and execute evals in under 10 minutes.

## Features
- **RAG + tools**: Hybrid search (pgvector + full-text) routes questions to contracts, invoices, or usage tables, while the agent accesses a tightly controlled tool layer (`get_contract_text`, `get_spend_summary`, etc.).
- **Structured outcomes**: Every response conforms to strict Pydantic schemas (renewal terms, pricing, negotiation plan, draft email) and every field must cite evidence `(doc_id, page, span)` or fall back to `unknown`.
- **Guardrails first**: Tool gateway with allowlist + RBAC + schema validation, retrieval sanitization against prompt injection, citation validator, PII redaction toggle, and hard budgets on tool calls, tokens, and wall clock time.
- **Observability built in**: OpenTelemetry traces cover ingest → retrieval → agent → validators. Grafana dashboards track latency, token spend, tool-call counts, citation coverage, and "unknown" rate. Structured logs capture prompt/config versions for audits.
- **Cost + latency controls**: Deterministic cache keyed by `(vendor_id, doc_hashes, prompt_version)`, routing small models for extraction and large models only for synthesis, and strict top-k retrieval per source.
- **Evaluation + CI/CD**: Golden cases with regression harness, prompt-injection suite, secret scanning, lint/type/test, container builds, and eval smoke tests enforced in CI.

## Quickstart
1. **Install dependencies**
   ```bash
   pipx install poetry  # optional
   make install
   ```
2. **Launch local stack** (FastAPI app + Postgres + MinIO + Grafana + OpenTelemetry collector):
   ```bash
   make docker-up
   ```
3. **Load samples** (copies `examples/*` into `.data/vendor_123` + manifest)
   ```bash
   make ingest-sample
   ```
4. **Call the API**
   ```bash
   make run-api  # or uvicorn src.app.main:app
   ./examples/curl/renewal_brief.sh vendor_123
   ```
5. **Open Grafana**
   - http://localhost:3000 → `Renewal Desk` dashboard for latency/tokens/tool metrics.
   - Prometheus scrapes `http://localhost:8000/metrics`; `curl localhost:8000/metrics` to inspect raw counters/histograms.
6. **Run evaluations**
   ```bash
   make eval
   ```
7. **Shut everything down**
   ```bash
   make docker-down
   ```

## Architecture
- `src/app` holds the FastAPI service, agent runner, tool gateway, RAG components, and storage adapters.
- `docs/architecture.md` explains the C4-ish view (ingestion, knowledge layer, agent API, observability) and where budgets + validation trigger.
- `docs/data-flow.md` walks through ingest → parse → store → retrieval routing → agent planning → validation.
- Infra pieces (`infra/docker-compose.yml`, Grafana provisioning, Terraform stubs) keep the stack reproducible locally and easy to map to AWS.
- `/debug/trace/{request_id}` (coming soon) reconstructs retrieval hits, tool calls, budgets, and validator outcomes for any response.
- `docs/local-development.md` describes running the stack on Minikube, including building/pushing images locally.

## Safety & Guardrails
- Retrieved text treated as hostile; sanitization strips instructions before prompts.
- Tool gateway enforces RBAC + schema validation + default deny.
- Schema validators enforce "no claim without evidence"; missing citations force `unknown` with a recorded search trail.
- Configurable PII redaction before LLM calls; logs capture metadata, not raw sensitive content.
- Prompt + retrieval policy versions are immutable artifacts tracked alongside code.
- Automated adversarial suites (prompt injection, tool misuse, data exfil) run via `make eval` and in CI.

## Evaluation
- `eval/golden/cases.jsonl` + `expected.jsonl`: canonical cases covering notice windows, pricing, usage deltas, and risk flags.
- `eval/injection_suite.jsonl`: hostile payloads injected into documents or tool outputs; validator must block or flag.
- `eval/harness.py`: loads golden cases, runs the API (real or mocked), checks field accuracy, citation coverage, unknown rate, and injection resilience.
- CI runs `python eval/harness.py --smoke` plus lint/type/tests; per-branch eval numbers stored for regression tracking.

## Roadmap
- [ ] Implement actual document parsing (pdfminer/pymupdf) + table extraction.
- [ ] Build pgvector migrations + hybrid retrieval queries.
- [ ] Finish agent loop with multi-model routing and `/debug/trace/{request_id}` endpoint.
- [ ] Expand evaluator with cost/latency budgets + tolerance bands.
- [ ] Add Terraform modules for AWS ECS + RDS + OpenSearch deployment.
- [ ] Ship a thin React or Next.js UI + Slack slash command.

This repo is intentionally opinionated: it optimizes for demonstrable operability (guardrails, evals, dashboards, IaC) over feature sprawl. Clone it, run the scripts, and start filling in the TODOs with real integrations.
