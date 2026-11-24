# Threat Model

Renewal Desk reads vendor contracts, invoices and usage data, which are commercially sensitive. This page lists what the code protects, how, and what it does not cover. It describes the repository as it is. Work that is not built yet is under [Planned](#planned).

## Assets

- Vendor contracts, invoices and usage files, and the text and embeddings derived from them.
- The generated briefs and the draft email.
- The system prompt (`src/app/agent/prompts/base.md`) and the extraction rules.
- Stored traces in the `debug_traces` table.

## Trust boundaries

1. **Uploaded files to the API.** A client controls the file bytes, the file name and the vendor id.
2. **Contract text to the model prompt.** The text is untrusted input to the model.
3. **App to the model server.** Contract text and extracted facts go to the configured Ollama endpoint.
4. **App to storage.** Files are written to local disk, derived data to PostgreSQL.
5. **App to the observability stack.** Metrics, spans and traces leave the request path.

## Threats and what the code does

| Threat | What exists in the code |
| --- | --- |
| Prompt injection in the contract text | `agent/injection_classifier.py` scores the contract text against six weighted regular-expression categories (instruction override, credential extraction, external call, data exfiltration, role impersonation, system prompt extraction). A total score above 0.5 stops the request with `400` before any model call and stores a trace with `prompt_injection: blocked`. The model is asked for JSON only and the answer must pass a strict Pydantic schema. |
| A section the model cannot support | `agent/validators.py` requires at least one citation (a document id and a span label) in each of the five sections. Sections without one trigger one repair call and are then replaced by an empty section (fail closed). |
| Path traversal through the vendor id or the file name | `storage/object_store.py` accepts vendor ids of 1 to 64 letters, digits, `_`, `-` and `.` that start with a letter or digit, and answers `400` otherwise. Path separators in file names are replaced, and `.` and `..` are refused. |
| Uploaded files readable on disk | Uploaded `.txt` and `.csv` files are encrypted with Fernet. The key comes from `ENCRYPTION_KEY`. The app decrypts them again when the brief and the indexer read them. See the limits below for what this does not cover. |
| Cost and latency abuse | Output token cap (`MAX_OUTPUT_TOKENS`), request timeout (`REQUEST_TIMEOUT_S`), three attempts with backoff, a circuit breaker (five failures, 60 seconds), a daily spend estimate (`DAILY_BUDGET_USD`), a one-hour cache per vendor and a rate limit of 100 requests per 60 seconds per client address and path (both numbers can be set with `RATE_LIMIT_MAX_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`). |
| Sensitive data in traces and metrics | A trace holds the request id, vendor id, document paths, the names of the steps taken, token estimates and the validation snapshot. It does not hold contract text or the generated brief. Metric labels are paths, methods, status codes, error reasons and stage names. |
| The model service being down or slow | The brief is still built from the extracted facts, so a model failure produces a less detailed brief and not an error. The `LLMProviderDown` alert fires on repeated failures. |

## Limits of these controls

Read these before relying on any control above.

- **The injection check is pattern based.** It catches the phrasings in its list and is easy to get around by rewording or using another language. It also produces false positives: any `http://` or `https://` in the contract text scores 0.8 and blocks the request. Only the contract is scanned. Invoices and usage files are not.
- **Citations are checked for presence only.** The validator does not compare a citation with the source text, so a model can cite a document that does not support its claim. Without a model, the fallback brief always carries citations, so `citation_coverage_ratio` reads 1.0 whether or not the content is useful.
- **Encryption covers less than it suggests.** Only the uploaded `.txt` and `.csv` files are encrypted. PDFs, the text and tables parsed from them, and the chunks and embeddings in PostgreSQL are stored as plain data. If `ENCRYPTION_KEY` is not set, the app uses a fallback key derived from constants in the source, which gives no protection. If encryption fails the file is stored unencrypted and a warning is logged.
- **No authentication.** `core/auth.py` is not connected, so every route, including the `/debug` endpoints that return stored traces, is open to anyone who can reach the service.
- **Uploads are not inspected.** There is no file size limit, content check or malware scan. PDFs are parsed by PyMuPDF inside the API process, so a flaw in the parser would run with the privileges of the app.
- **PII detection is not applied.** `core/pii_detection.py` exists but no route calls it, so personal data in a contract reaches the model and the database.
- **Container and credentials.** The image runs as root. The Compose file and the Helm chart contain demo database and MinIO credentials meant for a local machine.
- **State is per process.** The cache, the budget tracker, the rate limiter and the job queue live in memory. They reset on restart and are not shared between replicas, so with more than one replica the effective limits are multiplied.
- **Model traffic.** Contract text goes to the Ollama endpoint over plain HTTP. The router can register an OpenAI client, but the agent never selects it today, so no text is sent to a third-party model service.

## Planned

- Enforce authentication on every route and restrict the `/debug` endpoints.
- Apply PII detection before the model call.
- Limit upload size and type, and parse files in a separate low-privilege process.
- Verify each citation against the cited text.
- Run the container as a non-root user and read the encryption key from a secrets manager.
- Move the cache, budget tracker, rate limiter and job queue out of process.
- Score external links in context so a URL alone does not block a contract.

Each new capability should add a row to the table above and any new limit to the list that follows it.
