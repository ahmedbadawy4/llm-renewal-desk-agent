# Runbook

This runbook documents standard operating procedures for the Renewal Desk agent. Keep it close during demos and real incidents.

## 1. High latency / timeouts
1. Check Grafana `Renewal Desk` dashboard → `Latency p95` panel.
2. Inspect `/debug/trace/{request_id}` for representative slow requests; look for large retrieval counts or model retries.
3. Actions:
   - Verify caches warm (cache hit panel). If low, confirm `doc_hash` changes.
   - Lower `MAX_TOOL_CALLS` or `MAX_TOKENS` temporarily via config map.
   - Scale API/service replicas via docker-compose `app` service or ECS task count.
4. Postmortem: record root cause, add regression test if missing.

## 2. Token/cost spike
1. Alert fired (`Token Budget Breach`).
2. Pull trace for offending request, check `token_usage_in/out` attributes.
3. Ensure routing rules still send extraction tasks to small model.
4. Actions:
   - Tighten retrieval top-k.
   - Increase cache TTL or warm caches.
   - Temporarily disable expensive features (draft email) via feature flag.

## 3. Citation validator failures
1. Failing requests appear as `unknown` or `validation_error`.
2. Retrieve stored artifacts (request_id) and inspect citations vs. doc_id/page.
3. Common fixes: adjust chunking, update heuristics, fix contract parsing.
4. Add new regression case to golden set before closing incident.

## 4. Prompt injection detection
1. Harness or runtime flags `injection_detected`.
2. Inspect offending document snippet; update sanitization rules or tool gateway policies.
3. If system followed malicious instruction, halt deployments, rotate secrets, and run secret scans.

## 5. Database or storage outage
1. Docker-compose: check `docker compose ps`.
2. Cloud: failover to standby RDS, verify S3 bucket access.
3. App should degrade gracefully: respond with `temporarily_unavailable` and log error.
4. After recovery, run `make migrate` and `make eval --smoke` to ensure consistency.

## 6. Rolling back prompt/model versions
1. Prompts and configs stored under `src/app/agent/prompts/<version>.md` (placeholder today).
2. Use IaC/feature-flag service to flip `PROMPT_VERSION` env var back.
3. Redeploy `app` service; verify via `/debug/trace` that new requests use expected version.
4. Record rollback reason + add regression test/eval case.

## 7. Onboarding checklist
- Provide engineer with API keys, sample docs, Grafana creds.
- Walk through Quickstart, eval harness, runbook scenarios above.
- Assign ownership for docs/evals/instrumentation updates each sprint.

Treat this runbook as living documentation. Update after each incident or notable change.
