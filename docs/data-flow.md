# Data Flow

This page follows a document from upload to a renewal brief, and notes where each guardrail runs. It describes what the code does today. Anything not built yet is under [Not in the flow yet](#not-in-the-flow-yet).

## 1. Ingestion (`POST /ingest?vendor_id=<id>`)

1. The request carries up to three multipart files: `contract`, `invoices` and `usage`. At least one is required, otherwise the API answers `400`.
2. For each file the object store writes `DATA_DIR/<vendor_id>/<label>_<filename>`. The vendor id must be 1 to 64 letters, digits, `_`, `-` or `.` and start with a letter or digit, otherwise the API answers `400`. Path separators in file names are replaced.
   - `.txt` and `.csv` files are encrypted with Fernet (key from `ENCRYPTION_KEY`). The brief and the indexer decrypt them again when they read the file.
   - A `.pdf` is parsed with PyMuPDF straight away and the parsed text and tables are saved next to it.
3. The vendor's `manifest.json` is updated with the stored paths, so later requests find the files by vendor id.
4. One job per file is submitted to the in-process queue (`asyncio.create_task`) and the API answers `202 Accepted` with the job ids.
5. The worker (`workers/parser.py`) reads the file and `storage/indexing.py` splits the text into chunks of 800 characters with an overlap of 80, creates embeddings with sentence-transformers and writes them to `document_chunks` in PostgreSQL (pgvector).
6. Job status is available at `GET /jobs/{job_id}` and `GET /jobs?vendor_id=<id>`: `pending`, `processing`, `completed` or `failed`, with an error message on failure. The statuses are kept in memory and are lost on restart.

## 2. Brief request (`POST /renewal-brief?vendor_id=<id>`)

1. **Cache.** The cache key is the vendor id. Unless the body sets `"refresh": true`, a cached brief younger than one hour is returned immediately. A refreshed brief replaces the cached one.
2. **Inputs.** Paths come from the vendor's manifest. A missing file falls back to the matching file in `examples/`. If there is no contract text the request fails with a message that points to `GET /jobs?vendor_id=<id>` when ingestion jobs are still running.
3. **Injection check.** The contract text is scored against six weighted regular-expression categories (instruction override, credential extraction, external call, data exfiltration, role impersonation, system prompt extraction). A total score above 0.5 stops the request with `400`, records the `injection_detected` metric and stores a trace with `prompt_injection: blocked`. Invoices and usage files are not scanned.
4. **Extraction.** Regular expressions and the parsed tables give the contract fields (term dates, notice window, auto-renew, price, uplift, liability cap, DPA status, seats). The invoices and usage CSV files are summarised in code (annual spend, allocated and active seats, usage delta).
5. **Model synthesis**, only when `LLM_PROVIDER=ollama`:
   1. The estimated cost is checked against `DAILY_BUDGET_USD`. When the budget is spent the call is skipped and `llm_errors_total{reason="budget_exceeded"}` increases.
   2. The prompt in `src/app/agent/prompts/base.md` plus the extracted facts and document text go to Ollama through `ModelRouter` (three attempts with backoff, circuit breaker, `REQUEST_TIMEOUT_S`, `MAX_OUTPUT_TOKENS`). A failed call increases `llm_errors_total{reason="request_failed"}`.
   3. The answer must be JSON that fits the Pydantic schema. If it does not, `validation_failures_total{stage="schema"}` and `llm_errors_total{reason="invalid_schema"}` increase and the model result is dropped.
6. **Citation validation.** Each of the five sections (terms, pricing, usage, risk flags, negotiation plan) must have at least one citation. When sections lack them, `validation_failures_total{stage="citations"}` increases and one repair call asks the model to fix them. A section that still has no citation is replaced by an empty section (fail closed). `citation_coverage_ratio` is the share of the five sections that have citations after that step.
7. **Fallback.** Without a usable model result the brief is built from the extracted facts, with citations pointing at the contract (`TERM`, `RISK`, `NEGOTIATION`), invoices (`PRICING`) and usage (`USAGE`) documents. A citation is a document id and a span label; `page` stays empty. The fallback negotiation plan follows fixed rules (a 5 or 10 percent target discount depending on the usage delta), so it is a starting point and not an analysis.
8. **Draft email.** Written by the model when Ollama is enabled and by a template otherwise.
9. **Record.** The brief is cached for one hour, counters and token estimates are recorded, and a `debug_traces` row stores the request id, vendor id, document ids, the steps taken, token estimates and the validation snapshot. OpenTelemetry spans `retrieval`, `llm_call`, `validation` and `response_build` cover the main stages.
10. The response is `{"status": "ok", "request_id": ..., "brief": {...}}`. The request id is the key for `GET /debug/trace/{request_id}`.

## 3. Batch briefs (`POST /renewal-brief/batch`)

The body is a list of vendor ids. Each vendor goes through the same flow with `refresh=false`, and the response reports totals and a result per vendor.

## 4. Evaluation

`eval/harness.py` calls the runner directly with the paths in each golden case, so it does not touch the API metrics. See [evals.md](evals.md).

## Not in the flow yet

- Chunk retrieval: the brief reads whole files. The chunks in `document_chunks` are written at ingestion but the brief path does not query them.
- Authentication, PII detection and the tool gateway: the modules exist but no route calls them.
- Object storage in S3 or MinIO: files stay on local disk.
- A scheduled nightly batch: only the batch endpoint runs briefs in bulk.
