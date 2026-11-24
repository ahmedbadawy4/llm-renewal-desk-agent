# Architecture

Renewal Desk is a reference implementation of a document-grounded agent: it reads a vendor contract, invoices and usage data, and returns a structured renewal brief in which every section carries citations. This page describes what the repository contains and how the parts fit together. Planned work is listed at the end and is not part of the running system.

```text
                  ┌──────────────────────── FastAPI app (src/app) ────────────────────────┐
 upload ────────► │ POST /ingest ──► object store (DATA_DIR) ──► job queue ──► parser      │
                  │                                                   │                    │
                  │                                      chunks + embeddings ──► pgvector  │
                  │                                                                        │
 request ───────► │ POST /renewal-brief ──► cache ──► injection check ──► extraction       │
                  │        │                                   │                           │
                  │        │                           Ollama via ModelRouter              │
                  │        │                                   │                           │
                  │        └───────── citation validation ◄────┘ (fail closed)             │
                  │                          │                                             │
                  │            brief + debug trace (PostgreSQL) + metrics                  │
                  └───────────────────────────┬────────────────────────────────────────────┘
                                              │ /metrics, OTLP spans
                              Prometheus ─► Grafana        OpenTelemetry collector
```

## Components

### API (`src/app/api`, `src/app/main.py`)

FastAPI with these routes:

| Route | Purpose |
| --- | --- |
| `POST /ingest?vendor_id=` | Accepts `contract`, `invoices` and `usage` files and returns `202` with job ids |
| `GET /jobs`, `GET /jobs/{job_id}` | Status of ingestion jobs |
| `POST /renewal-brief?vendor_id=` | Builds a brief for one vendor |
| `POST /renewal-brief/batch` | Builds briefs for a list of vendor ids |
| `GET /demo/renewal-brief` | Builds a brief from the files in `examples/` |
| `GET /llm/health` | Checks that the Ollama server is reachable and the configured model is pulled |
| `GET /debug/trace/{request_id}`, `GET /debug/traces`, `GET /debug/traces/export` | Stored traces |
| `GET /health`, `GET /metrics` | Liveness (with the commit sha) and Prometheus metrics |

Two middlewares wrap every request: a metrics middleware (request count and latency) and a rate limiter (by default 100 requests per 60 seconds per client address and path, set with `RATE_LIMIT_MAX_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`, answered with `429`).

### Ingestion (`storage/object_store.py`, `workers/`, `storage/indexing.py`, `rag/`)

- The object store writes files under `DATA_DIR/<vendor_id>/`, keeps a `manifest.json` per vendor, and encrypts `.txt` and `.csv` files with Fernet. Vendor ids and file names are validated so a path cannot leave that folder (`400` for a bad vendor id). `core/encryption.py` decrypts the files again when the runner and the indexer read them. PDFs are parsed with PyMuPDF at store time and the extracted text is stored next to them.
- `workers/job_queue.py` runs ingestion jobs in the API process with `asyncio.create_task`. Job states (`pending`, `processing`, `completed`, `failed`) are kept in memory.
- `workers/parser.py` parses the file and `storage/indexing.py` splits the text into chunks of 800 characters with an overlap of 80, embeds them with sentence-transformers and writes them to the `document_chunks` table in PostgreSQL with pgvector.

### Agent (`src/app/agent`, `src/app/llm`, `src/app/core`)

- `runner.py` orchestrates a request: cache lookup, input resolution, injection check, field extraction, optional model synthesis, validation, response build, metrics and trace.
- `injection_classifier.py` scores the contract text against weighted regular-expression categories and blocks the request above a total score of 0.5.
- `validators.py` checks that each section has citations (a document id and a span label) and blanks sections that have none. It checks presence; it does not compare a citation against the source text.
- `llm/router.py` (`ModelRouter`) calls Ollama with three attempts and backoff, and opens a circuit breaker after five consecutive failures for 60 seconds. The output token cap comes from `MAX_OUTPUT_TOKENS`.
- `core/cache.py` is an in-memory cache with a one-hour TTL, one entry per vendor. `core/rate_limit.py` is an in-memory sliding window. The daily budget tracker in `runner.py` is also in memory.
- Without a model (`LLM_PROVIDER=mock`, or when the model call fails) the brief is built from the extracted facts alone.

### Storage and schema (`storage/postgres.py`, `alembic/`)

PostgreSQL 15 with the pgvector extension. Five Alembic migrations create `document_chunks`, `debug_traces` and the tables for authentication, batch jobs and experiments. `alembic/env.py` imports the application settings, so migrations need `PYTHONPATH=/app/src`, which the Dockerfile sets and the Helm migration job sets itself.

### Observability (`core/metrics.py`, `core/tracing.py`, `core/debug.py`, `infra/`)

- Prometheus metrics at `/metrics` (listed in the README).
- OpenTelemetry spans `retrieval`, `llm_call`, `validation` and `response_build`, exported over OTLP to the collector.
- A `debug_traces` row per request with the retrieved document ids, the steps taken, token estimates and the validation snapshot. No contract text is stored in it.
- Alert rules in `infra/prometheus/alerts.yml` and two Grafana dashboards in `infra/grafana/dashboards/`.

### Delivery

| Path | Contents |
| --- | --- |
| `Dockerfile` | Python 3.11 image, dependencies installed from `poetry.lock` |
| `infra/docker-compose.yml` | App, one-shot migration, PostgreSQL with pgvector, MinIO, Prometheus, Grafana, OpenTelemetry collector |
| `charts/renewal-desk/` | Helm chart for the same stack plus an optional in-cluster Ollama and the UI |
| `infra/terraform/` | VPC, ALB, ECS Fargate, RDS and S3, plus an optional GitHub OIDC role for the deploy workflow (see its README for the variables and the backend) |
| `.github/workflows/ci.yml` | Lint, type check, tests, eval smoke run, secret scan, image build, Helm lint and render, Terraform format and validate |
| `.github/workflows/deploy.yml` | Manual `workflow_dispatch` pipeline: builds the image, pushes it to ECR, registers a task definition with the new image, updates the ECS service and runs the migrations through ECS Exec. It signs in to AWS through OIDC with the IAM role in the `AWS_ROLE_ARN` variable of the `production` environment (Terraform creates that role when `github_repository` is set), and it needs the cluster and service that Terraform creates and an ECR repository named `renewal-desk` that Terraform does not create |
| `ui/`, `ui-react/` | A static demo page and the sources of a Next.js UI |

## Present but not connected

These modules exist with their own code, but nothing in the API calls them yet:

- `core/auth.py`: API-key authentication.
- `core/pii_detection.py`: PII detection.
- `core/experiments.py`: A/B experiment helpers.
- `tools/`: a tool gateway with an allowlist, with contract, finance and usage tools that read the sample files in `examples/`.
- `rag/retrieval.py` and `rag/hybrid_search.py`: hybrid search (vector similarity plus PostgreSQL full-text rank). The brief path reads whole files instead of retrieving chunks.
- `scheduler.scheduled_renewal_briefs`: a periodic batch run. Only the batch endpoint calls the batch helper.
- S3 and MinIO: the bucket is provisioned, but the object store writes to local disk.

## Planned

- Retrieve chunks with hybrid search in the brief path instead of reading whole files.
- Read and write files through S3 or MinIO.
- Enforce authentication and PII detection on the routes.
- Move the job queue, cache and budget tracker out of process so replicas can share them.
- Verify a citation against the cited text instead of checking that it is present.
- Report cost per request from the model response so the eval cost budget is meaningful.

See [data-flow.md](data-flow.md) for the request steps and [threat-model.md](threat-model.md) for the risks and the mitigations that exist.
