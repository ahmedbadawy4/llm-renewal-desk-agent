# Runbook

What to check when something looks wrong with the Renewal Desk service. It covers the alerts in `infra/prometheus/alerts.yml`, the debug endpoints and the two deployment targets (Docker Compose and the Helm chart).

## Where to look

| What | Where |
| --- | --- |
| Liveness | `GET /health` returns `{"status": "ok", "commit": ...}` |
| Model server | `GET /llm/health`. `ok` means Ollama answers and the configured model is pulled. `missing_model` means Ollama answers but the model is not pulled. `503` means Ollama is unreachable. `skipped` is returned when `LLM_PROVIDER` is not `ollama`. |
| Metrics | `GET /metrics` (Prometheus format) |
| Dashboards | Grafana, dashboards `Renewal Desk` (request rate, p95 latency, 5xx rate, agent requests, tokens, LLM errors, validation failures, citation coverage) and `Renewal Desk - Business Metrics` (briefs generated, vendors processed, SLO gauges) |
| One request | `GET /debug/trace/{request_id}`. The request id is in the brief response. |
| Many requests | `GET /debug/traces?vendor_id=...&error_type=...&start_date=...&end_date=...&limit=...` and `GET /debug/traces/export` |
| Logs | Compose: `docker compose -f infra/docker-compose.yml logs app`. Helm: `kubectl -n <namespace> logs deploy/<release>`. |

A stored trace holds the request id, vendor id, document paths, the steps taken, token and cost estimates and the validation snapshot. It does not hold contract text or the generated brief.

## Alerts

All five rules are in `infra/prometheus/alerts.yml`. The Compose Prometheus loads them. The Helm chart's Prometheus only scrapes the app and has no rules. No Alertmanager is configured in either target, so an alert is visible on the Prometheus `Alerts` page and nowhere else.

### HighLatency (warning)

p95 of `api_request_latency_seconds` above 5 seconds for 5 minutes.

1. Check the `Latency p95` panel and `Request rate by path`. Brief generation is the slow path.
2. Call `/llm/health`. A slow model server is the usual cause. Ollama loads a model on its first request, so a model that is not loaded yet makes that call slow.
3. Open `/debug/traces` for the vendor and look at the steps and token counts of a slow request.
4. Possible actions: lower `MAX_OUTPUT_TOKENS`, raise `REQUEST_TIMEOUT_S` if the model is just slow, or use a smaller `LLM_MODEL`.

### HighErrorRate (critical)

5xx responses are above 1% of all requests for 5 minutes.

1. Check `Request rate by path` and `Error rate (5xx %)` to find the path.
2. `/llm/health` answers `503` when Ollama is unreachable, so a health check that polls it adds to this rate during a model outage.
3. Any other 5xx is an unhandled exception. Read the stack trace in the app logs.
4. A model failure during brief generation does not produce a 5xx. The brief falls back to the extracted facts. Look at `LLMProviderDown` for that case.

### LowCitationCoverage (warning)

`citation_coverage_ratio` below 0.95 for 10 minutes.

1. Look at the `Validation failures` panel. The `stage` label says which check failed.
2. Pull traces with `error_type` set and read the validation snapshot to see which sections lost their citations.
3. When the model is unavailable the fallback brief always carries citations and the ratio reads 1.0, so a healthy ratio during a model outage does not mean the content is good.
4. Add the failing document to `eval/golden/cases.jsonl` before closing the incident.

### LLMProviderDown (critical)

`llm_errors_total{reason="request_failed"}` above 0.1 per second for 5 minutes.

1. Call `/llm/health` and read the detail.
2. Compose: the app reaches Ollama on the host through `host.docker.internal`. Check that Ollama runs on the host and listens on a reachable address. Helm: check the `<release>-ollama` pod and its volume claim, or the `app.ollamaBaseUrl` value when Ollama runs outside the cluster.
3. The router retries three times and then opens a circuit breaker for 60 seconds after five failures. Briefs are still produced from the extracted facts meanwhile.
4. To run without a model, set `LLM_PROVIDER=mock`.

### BudgetExceeded (warning)

At least one `llm_errors_total{reason="budget_exceeded"}` in the last hour.

1. The daily spend estimate passed `DAILY_BUDGET_USD`. The tracker is in memory and resets when the date changes and on restart.
2. The figure is an estimate from token counts. With a local Ollama model the real cost is zero, so raise the value or set `DAILY_BUDGET_USD=0` to turn the check off.

## Other symptoms

**`400` on a brief request mentioning a prompt injection.** The injection check blocked the contract text. Open the trace for the request to see the flag. Any URL in a contract also blocks it (see [threat-model.md](threat-model.md)). Check the contract text before changing the rules.

**`400` on `/ingest` with `Invalid vendor_id`.** Vendor ids are 1 to 64 letters, digits, `_`, `-` or `.`, starting with a letter or digit.

**`429 Too Many Requests`.** The per-client rate limit applies. The defaults are 100 requests per 60 seconds per client address and path. Change them with `RATE_LIMIT_MAX_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`. Rejected requests are not counted in `api_requests_total`.

**Stored `.txt` or `.csv` files cannot be read.** They are encrypted with the Fernet key from `ENCRYPTION_KEY`. If the key changed after the upload, the app logs a warning and the brief is built from unreadable text. Restore the old key or ingest the files again. Without `ENCRYPTION_KEY` the app uses a fixed demo key from the source, so files stay readable across restarts but are not protected.

**A brief looks stale.** Briefs are cached for one hour per vendor. Send `{"refresh": true}` in the request body.

## Database or storage outage

1. Compose: `docker compose -f infra/docker-compose.yml ps` and `... logs postgres`. The `migrate` service runs once before the app starts and must have exited with code 0.
2. Helm: `kubectl -n <namespace> get pods` and `kubectl -n <namespace> logs job/<release>-migrations`. The migration job waits for PostgreSQL, applies the migrations and restarts on failure.
3. PostgreSQL holds the traces and the document chunks. When it is unreachable, trace writes and indexing log a warning (`Failed to record trace`, `Document indexing failed`) and the request carries on, so the symptom is missing traces and an empty search index, not an error response.
4. After the database is back, run `make migrate` against it (it reads `DATABASE_URL`, default `localhost:5432`) and `make smoke-eval`. The smoke run only checks that the cases load. A full run needs the agent and a model, see [evals.md](evals.md).
5. Uploaded files live under `DATA_DIR` inside the app container. In Compose the app has no data volume, so recreating the container removes them. Run `make ingest-sample` again. The Helm chart mounts an `emptyDir` at `/data`, which is also lost when the pod is replaced.

## Settings that matter

| Variable | Default | Effect |
| --- | --- | --- |
| `LLM_PROVIDER` | `ollama` | `ollama` or `mock` |
| `LLM_BASE_URL` | `http://host.docker.internal:11434` | Ollama address |
| `LLM_MODEL` | `llama3.1:8b` | Model name |
| `MAX_OUTPUT_TOKENS` | `800` | Output cap per model call |
| `REQUEST_TIMEOUT_S` | `30` | Model call timeout |
| `DAILY_BUDGET_USD` | `1.0` | Daily spend estimate limit, `0` or less disables it |
| `RATE_LIMIT_MAX_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window length |
| `ENCRYPTION_KEY` | unset | Fernet key for uploaded `.txt` and `.csv` files |
| `DATABASE_URL` | local PostgreSQL | Where traces and chunks are stored |
| `DATA_DIR` | `.data` | Where uploaded files are stored |

In Compose these are set on the `app` service in `infra/docker-compose.yml`. With Helm they are chart values under `app.*` in `charts/renewal-desk/values.yaml`. Change the value and restart the app, because the settings are read at start.

## State that resets on restart

The response cache, the daily budget tracker, the rate limiter and the job queue live in the app process. A restart clears them, and replicas do not share them. An ingestion job that was running during a restart is lost, so run the ingest again.
