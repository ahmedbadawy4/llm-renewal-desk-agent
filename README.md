# Renewal Desk Agent

[![CI](https://github.com/ahmedbadawy4/llm-renewal-desk-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmedbadawy4/llm-renewal-desk-agent/actions/workflows/ci.yml)

A prototype LLM agent for SaaS vendor renewals. It reads a vendor contract (PDF), invoices (CSV) and a usage export (CSV) and returns a structured renewal brief: renewal terms, pricing, usage, risk flags, a negotiation plan and a draft email. Every section carries citations, and a section without a citation is blanked instead of being passed on.

The repository is a reference build. It shows how to put guardrails, observability, packaging and delivery around an LLM call. It is not a finished product, and the [Design limits](#design-limits) section lists what is simplified.

## What it does

1. **Ingest.** `POST /ingest` stores the files per vendor, encrypts the text and CSV files at rest and queues a background job per file. The job parses the PDF with PyMuPDF, then chunks and embeds the text into pgvector.
2. **Extract.** Regular expressions pull the deterministic facts out of the contract text: term dates, notice window, price, uplift percentage, licensed seats, liability cap. Invoices and usage are summarised with plain Python.
3. **Check the input.** A weighted, pattern-based classifier scans the contract text for prompt injection. A hit stops the request before any model call and answers with an error.
4. **Synthesise.** Ollama receives the extracted facts and the evidence and must answer in JSON that matches the `RenewalBriefSynthesis` schema. A daily budget check runs first.
5. **Validate.** Pydantic enforces the schema (`extra="forbid"`). Every populated section needs a citation. A section without one is blanked (fail closed) and the citation coverage is recorded.
6. **Fall back.** If the model is unreachable, over budget or returns invalid JSON, the brief is built from the extracted facts alone.

## What is in the repository

| Area | What exists |
| --- | --- |
| API | FastAPI app with ingestion, brief generation, batch, job status, health, metrics and debug trace endpoints |
| Agent | Runner, Pydantic schemas, citation validators, injection classifier, prompt template |
| LLM access | Ollama client and a model router with retry and backoff (3 attempts) and a circuit breaker per provider (opens after 5 failures, retries after 60 s) |
| Retrieval | PDF parsing, chunking, sentence-transformers embeddings, pgvector store, hybrid search (vector similarity plus PostgreSQL full-text rank) |
| Storage | Local filesystem object store with a per-vendor manifest, PostgreSQL for vectors, jobs and debug traces, five Alembic migrations |
| Observability | Prometheus metrics, OpenTelemetry traces through a collector, two Grafana dashboards, Prometheus alert rules |
| Packaging | Dockerfile, Docker Compose stack, Helm chart for a local Kubernetes cluster |
| Delivery | GitHub Actions for lint, types, tests, eval smoke, chart and Terraform checks and image build; a manual deploy workflow for ECS |
| Infrastructure as code | Terraform for AWS: VPC, ALB, ECS Fargate, RDS PostgreSQL and S3 |
| Evaluation | Eval harness with golden cases, cost and latency budgets, tolerance bands and a regression check |
| UI | A static page in `ui/` and Next.js sources in `ui-react/` |

## Quick start

### Docker Compose

```bash
make docker-up          # app, PostgreSQL, MinIO, Prometheus, Grafana, OTel collector
make ingest-sample      # load the bundled example files for vendor_123
```

The default provider is Ollama on the host (`http://host.docker.internal:11434`):

```bash
ollama serve
ollama pull llama3.1:8b
```

Ask for a brief:

```bash
curl -sS -X POST "http://localhost:8000/renewal-brief?vendor_id=vendor_123" \
  -H "Content-Type: application/json" \
  -d '{"refresh": false}' | python -m json.tool
```

Grafana runs on http://localhost:3000 and Prometheus on http://localhost:9090.

### Helm on a local Kubernetes cluster

```bash
make helm-install            # builds the image, installs the chart with Ollama inside the cluster
make helm-ingest-sample
make helm-renewal-brief
```

`make helm-install-ollama-external` uses an Ollama that runs on the host instead. Grafana is on http://localhost:30030 and the UI on http://localhost:30081. If the cluster does not expose NodePorts, run `make helm-port-forward`.

For kind, load the image into the cluster by name: `make helm-install KIND_CLUSTER=<name>`. To pin the Helm and kubectl commands to one context, add `KUBE_CONTEXT=<context>`.

## Architecture

```text
 client / UI
     |
     v
 FastAPI ──> rate limit, metrics middleware
     |
     |  POST /ingest ──> object store (local files, encrypted) ──> job queue ──> parse, chunk, embed ──> pgvector
     |
     |  POST /renewal-brief
     v
 agent runner
     1. read stored contract, invoices, usage
     2. injection classifier ──(hit)──> error, no model call
     3. regex extraction and CSV summaries
     4. daily budget check
     5. model router ──> Ollama (retry, circuit breaker)
     6. schema and citation validation, fail closed
     7. fallback to the extracted facts when step 5 fails
     8. cache, metrics, debug trace (PostgreSQL)
```

More detail is in [docs/architecture.md](docs/architecture.md) and [docs/data-flow.md](docs/data-flow.md).

## API

| Method and path | Purpose |
| --- | --- |
| `POST /ingest?vendor_id=` | Upload `contract`, `invoices` and `usage` as form files. Returns `202` with the job ids and the stored file paths. The vendor id is 1 to 64 letters, digits, `_`, `-` or `.`, starting with a letter or digit, and anything else gets `400` |
| `GET /jobs`, `GET /jobs/{job_id}` | Status of the background processing jobs |
| `POST /renewal-brief?vendor_id=` | Generate a brief |
| `POST /renewal-brief/batch` | Generate briefs for a JSON array of vendor ids |
| `GET /demo/renewal-brief` | Generate a brief from the bundled example files |
| `GET /health` | Liveness |
| `GET /llm/health` | Reachability of the configured LLM endpoint |
| `GET /metrics` | Prometheus metrics |
| `GET /debug/trace/{request_id}` | Stored trace of one request |
| `GET /debug/traces`, `GET /debug/traces/export` | Search and export stored traces |

The body of `POST /renewal-brief` accepts `refresh` (skip the cache) and optional `llm_provider` (`mock` or `ollama`), `ollama_base_url` and `ollama_model` for a single request.

An abridged response:

```json
{
  "status": "ok",
  "request_id": "0b4f0c0b-acde-4c11-9bdb-2f0f4e9497db",
  "brief": {
    "vendor_id": "vendor_123",
    "renewal_terms": {
      "term_start": "2024-01-01",
      "term_end": "2024-12-31",
      "notice_window_days": 90,
      "auto_renew": true,
      "citations": [{"doc_id": "contract.pdf", "page": 2, "span": "TERM"}]
    },
    "pricing": {"annual_spend_usd": 120000, "uplift_clause_pct": 5, "citations": [{"doc_id": "invoices.csv", "span": "PRICING"}]},
    "usage": {"allocated_seats": 500, "active_seats": 475, "delta_percent": -5.0, "citations": [{"doc_id": "usage.csv", "span": "USAGE"}]},
    "risk_flags": {"auto_renew_soon": true, "liability_cap_multiple": 2, "dpa_status": "present", "pii_risk": "low", "citations": [{"doc_id": "contract.pdf", "span": "RISK"}]},
    "negotiation_plan": {"target_discount_pct": 10, "walkaway_delta_pct": 15, "levers": ["Usage below contracted seats"], "citations": [{"doc_id": "contract.pdf", "span": "NEGOTIATION"}]},
    "draft_email": {"subject": "vendor_123 renewal discussion", "body": "Hi vendor_123 team, ..."}
  }
}
```

## Guardrails

- **Injection check before the model.** Weighted regular-expression categories, score threshold 0.5. A hit raises an error and records an `injection_detected` metric and trace.
- **Constrained output.** One system prompt, a JSON-only answer and a strict Pydantic schema.
- **Citations or nothing.** A section without citations is blanked and counted in `citation_coverage_ratio`.
- **Budget and limits.** A daily spend estimate (`DAILY_BUDGET_USD`), an output token cap and a request timeout. Requests are limited to 100 per 60 seconds per client address and path (`RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`).
- **Path checks.** Vendor ids and uploaded file names cannot leave the vendor's folder under `DATA_DIR`.
- **Encryption at rest.** Uploaded `.txt` and `.csv` files are encrypted with a Fernet key taken from `ENCRYPTION_KEY` and decrypted when the brief and the indexer read them. PDFs and the data derived from them are not encrypted. Without the variable a fixed demo key from the source is used, which protects nothing.
- **Deterministic fallback.** The brief is still produced from the extracted facts when the model fails.

## Observability

Main metrics at `/metrics`:

| Metric | Type |
| --- | --- |
| `api_requests_total` (`path`, `method`, `status`) | counter |
| `api_request_latency_seconds` (`path`, `method`) | histogram |
| `agent_requests_total` (`status`) | counter |
| `agent_tokens_total`, `llm_tokens_total` (`direction`) | counter |
| `llm_errors_total` (`reason`) | counter |
| `validation_failures_total` (`stage`) | counter |
| `citation_coverage_ratio` | gauge |
| `llm_request_latency_seconds` (`provider`) | histogram |
| `renewal_briefs_generated_total` (`vendor_id`) | counter |

Traces go to the OpenTelemetry collector over OTLP. Each brief also stores a debug trace in the `debug_traces` table with the document ids, token counts, validation result and citation coverage.

The Compose stack loads [infra/prometheus/alerts.yml](infra/prometheus/alerts.yml): high latency, high error rate, low citation coverage, LLM provider failures and an exceeded budget. Grafana loads the dashboards in `infra/grafana/dashboards`.

![Grafana Renewal Desk dashboard](docs/assets/grafana-chart.png)

## UI

`ui/` is a static page that talks to the API. Start the API with `make run-api`, then:

```bash
python -m http.server 5173 -d ui
```

Open http://localhost:5173. It uploads files, requests a brief and shows the debug trace. `ui-react/` holds Next.js sources for a second version of the UI; see its `package.json` for the scripts.

![Renewal Desk UI sample](docs/assets/ui-sample.png)

## Development

```bash
make install        # poetry install
make run-api        # uvicorn with reload
make lint           # ruff
make type           # mypy
make test           # pytest
make eval           # eval harness with the golden cases
make smoke-eval     # loads the eval cases and writes the report, does not run the agent
make helm-lint      # lint and render the Helm chart
```

Configuration comes from environment variables (a `.env` file is read too):

| Variable | Default | Meaning |
| --- | --- | --- |
| `LLM_PROVIDER` | `ollama` | `ollama` calls the model. Any other value, such as `mock`, skips the model and uses the extracted facts |
| `LLM_BASE_URL` | `http://host.docker.internal:11434` | Ollama endpoint |
| `LLM_MODEL` | `llama3.1:8b` | Ollama model |
| `MAX_OUTPUT_TOKENS` | `800` | Output token cap |
| `REQUEST_TIMEOUT_S` | `30` | Timeout of one model call |
| `DAILY_BUDGET_USD` | `1.0` | Daily spend estimate limit, `0` turns it off |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/renewaldesk` | PostgreSQL connection string |
| `DATA_DIR` | `.data` | Where uploaded files are stored |
| `ENCRYPTION_KEY` | unset (demo key) | Fernet key for uploaded `.txt` and `.csv` files. Create one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `RATE_LIMIT_MAX_REQUESTS` | `100` | Requests allowed per window and client address and path |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Length of the rate-limit window |
| `CORS_ORIGINS` | local UI ports | Allowed origins |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | unset | Registers the OpenAI client in the router (see Design limits) |

## Deployment

**Docker Compose** (`infra/docker-compose.yml`) runs the app with PostgreSQL, MinIO, Prometheus, Grafana and the OpenTelemetry collector. The credentials in it are local demo values.

**Helm** (`charts/renewal-desk`) installs the app, UI, PostgreSQL, Prometheus, Grafana, the OpenTelemetry collector, MinIO and optionally Ollama. It is a demo stack for a local cluster: it uses NodePort services and demo database credentials, so do not install it on a shared cluster as it is. Ingress is optional:

```bash
helm upgrade --install renewal-desk charts/renewal-desk \
  --namespace renewal-desk --create-namespace \
  --set ingress.enabled=true \
  --set ingress.className=nginx
```

**AWS** (`infra/terraform`) defines a VPC, an Application Load Balancer, an ECS Fargate service, RDS PostgreSQL and an S3 bucket. [infra/terraform/README.md](infra/terraform/README.md) has the variables and the backend setup. `.github/workflows/deploy.yml` is a manual workflow that builds the image, pushes it to ECR and updates the ECS service.

## Pipeline

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on pushes to `main` and on pull requests:

| Job | Steps |
| --- | --- |
| `build-and-test` | Ruff, mypy, pytest, eval smoke, Gitleaks, Docker build |
| `helm` | `helm lint` and `helm template` of the chart, with and without ingress |
| `terraform` | `terraform fmt -check` and `terraform validate` without a backend |

## Troubleshooting

- **Grafana is empty.** Generate traffic: `make helm-traffic REQUESTS=10 SLEEP=1`.
- **NodePorts are not reachable.** Use `make helm-port-forward`.
- **Reset the Compose state.** `docker compose -f infra/docker-compose.yml down -v` and remove `.data`.
- **Migration pod fails.** Check the PostgreSQL connection and that the pgvector extension can be created.

## Design limits

- **Retrieval is not on the brief path.** Documents are chunked, embedded and stored in pgvector at ingestion, and `rag/retrieval.py` implements the hybrid search, but the runner reads the extracted text directly. Hooking the search into the runner is the next step for long contracts.
- **Hybrid search ranks with PostgreSQL full-text rank, not BM25.** The vector score has weight 0.7 and a simple rerank follows. When the vector store is off, a placeholder result is returned.
- **One model in practice.** The router has an OpenAI client and selection rules, but the runner always asks for standard quality and only calls the router when `LLM_PROVIDER=ollama`, so Ollama serves every request. The per-request override accepts `mock` or `ollama`.
- **Extraction is pattern based.** The regular expressions match the sentence forms of the example contract. Other contract wording needs new patterns or the model.
- **State is per process.** The daily budget tracker, the response cache (one hour) and the rate limiter live in memory, so they reset on restart and are not shared between replicas.
- **Files stay on local disk.** The object store writes to `DATA_DIR`. MinIO and the S3 bucket are provisioned, but the application does not use them yet.
- **Injection detection is pattern based.** It catches known phrasing and is one layer, not a complete defence.
- **Present but not connected.** The repository has API-key authentication (`core/auth.py`), PII detection (`core/pii_detection.py`), A/B experiment helpers (`core/experiments.py`) and a tool allowlist gateway (`tools/`). None of them is wired into the API routes yet.
- **Local demo defaults.** The container runs as root, the chart and Compose files carry demo database credentials, and the Terraform root passes the database URL to the task as an environment value.
- **PDF input is text only.** Scanned PDFs without a text layer produce no contract text.

## Documentation

- [docs/architecture.md](docs/architecture.md): components and what is built
- [docs/data-flow.md](docs/data-flow.md): ingestion and brief request step by step
- [docs/local-development.md](docs/local-development.md): Compose and Helm workflows
- [docs/evals.md](docs/evals.md): the eval harness
- [docs/runbook.md](docs/runbook.md): operating the stack
- [docs/threat-model.md](docs/threat-model.md): risks and which mitigations exist

## Roadmap

- [x] PDF parsing with PyMuPDF
- [x] Embeddings and pgvector indexing at ingestion
- [x] Hybrid search implementation (vector plus PostgreSQL full-text rank)
- [x] Ollama routing with retry and circuit breaker
- [x] Background document processing with a job queue
- [x] Database migrations with Alembic
- [x] Eval harness with budgets, tolerance bands and a regression check
- [x] Terraform for VPC, ALB, ECS, RDS and S3
- [x] Next.js UI sources
- [ ] Use hybrid search in the brief path
- [ ] Read and write files through S3 or MinIO
- [ ] Connect authentication and per-tenant limits to the routes
- [ ] Route to the OpenAI client by quality and budget
- [ ] OCR for scanned PDFs

## License

Apache License 2.0, see [LICENSE](LICENSE).
