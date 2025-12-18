# Evaluation Strategy

Evaluation is non-negotiable: every change must prove it did not erode factual accuracy, citation quality, or guardrails.

## Golden datasets
- **`eval/golden/cases.jsonl`**: Input descriptors (vendor metadata, doc paths, required outputs).
- **`eval/golden/expected.jsonl`**: Ground-truth structured responses aligned to schema.
- Cases cover:
  - Notice window extraction (30/45/60/90 days, missing clause → `unknown`).
  - Auto-renew + termination semantics.
  - Pricing uplifts and true usage vs. contracted.
  - Risk scenarios (missing DPA, liability cap mismatch).

## Behavioral suites
- **Prompt injection**: `eval/injection_suite.jsonl` includes malicious instructions embedded inside contracts/invoices. Harness verifies agent ignores them and flags `injection_detected` if needed.
- **Tool abuse**: Simulated repeated tool calls to ensure budgets stop runaway loops.
- **Observability**: Checks that traces/logs contain required metadata (request_id, prompt_version, doc_ids).

## Metrics
| Metric | Description | Target |
| --- | --- | --- |
| Field accuracy | Exact match vs. expected for key fields | >= 0.9 on golden set |
| Citation coverage | % of fields with at least one valid citation | 1.0 (fail closed) |
| Unknown rate | % of required fields returned as `unknown`; tracked vs. budget | < 0.2 except for intentionally missing data |
| Injection resilience | % of hostile cases blocked/detected | 1.0 |
| Cost per brief | Tokens * price + tool cost; ensures budgets honored | <$0.50 for sample |

## Harness flow
1. `python eval/harness.py --cases eval/golden/cases.jsonl --expected eval/golden/expected.jsonl`.
2. Harness loads cases, invokes the agent runner directly (optionally overriding file paths per case), and captures structured results.
3. Schema, field accuracy, and citation validation performed locally to avoid polluting API metrics.
4. Summary report printed + JSON artifact stored under `.reports/eval-<timestamp>.json` (folder ignored by git).

## CI integration
- `.github/workflows/ci.yml` runs `make lint test type`, `python eval/harness.py --smoke`, and `gitleaks detect`.
- Full eval suite required before main branch deploy or tagged release.
- Eval history (scorecards) stored in Postgres or S3 for longitudinal tracking.

Future work: integrate with Langfuse/Weights & Biases for richer analytics, add human review loops, and include latency/cost regressions in gating.
