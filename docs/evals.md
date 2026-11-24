# Evaluation

`eval/harness.py` runs the brief generator over a file of cases, compares the output with expected values where a case has them, and writes a JSON report. This page describes what the harness checks today and where its coverage is thin.

## Files

| File | Contents |
| --- | --- |
| `eval/golden/cases.jsonl` | 64 cases. |
| `eval/golden/expected.jsonl` | Expected output for 2 of the cases. |
| `eval/injection_suite.jsonl` | 2 hostile example strings. The harness does not read this file. |
| `tests/fixtures/injection_contract.txt` | Contract text containing instructions to the model. Six cases use it. |

A case has these fields:

| Field | Meaning |
| --- | --- |
| `case_id` | Unique name. Also the key that links a case to its entry in `expected.jsonl`. |
| `vendor_id` | Vendor id passed to the generator. |
| `inputs` | Paths to `contract_path`, `invoices_path` and `usage_path`. |
| `latency_budget_seconds` | Case fails when the run takes longer. Default 30. |
| `cost_budget_usd` | Cost budget. Default 0.01. |
| `tolerance` | Allowed relative difference per numeric field, keyed `section.key` (for example `pricing.annual_spend_usd: 0.1`) or just `key`. |
| `expect_injection` | When true, the case passes only if the request is blocked as a prompt injection. |
| `notes` | Free text. |

An `expected.jsonl` entry holds one object per brief section (`renewal_terms`, `pricing`, `usage`, `risk_flags`, `negotiation_plan`) with the field values to compare. A different entry shape, `{"expected_behavior": "injection_detected"}`, marks a case that must be blocked.

## What a run checks

For each case the harness calls the same generator the API uses (`agent/runner.py`, with `refresh=False`) and then checks:

1. **Expected values.** Every field in the case's `expected.jsonl` entry is compared with the brief as a string. A field with a `tolerance` is compared as a number inside that band. A field that is missing or not a number fails.
2. **Citation presence.** Each of the five sections must have at least one citation. This checks that a citation exists, not that it supports the claim.
3. **Latency.** The run must finish inside `latency_budget_seconds`.
4. **Injection handling.** A case with `expect_injection` (or an `injection_detected` expected entry) passes only when the generator raises the injection error. If a brief is produced for it, the case fails. If the error is raised for a case that does not expect it, the case fails too.

Any other exception ends the case with status `error`, which counts as a failure.

## Running it

Run inside the Poetry environment so the `src` package imports, for example `poetry run make smoke-eval`.

| Command | What it does |
| --- | --- |
| `make smoke-eval` | Loads the cases and writes the report. It does not run the agent, so no case can fail. |
| `make run-evals` (or `make eval`) | Runs every case. Exits 1 when any case fails. |
| `python eval/harness.py --regression-check` | Runs every case and compares the result with a saved baseline. |

A full run uses whatever `LLM_PROVIDER` is set to. With `ollama` the model is called, so a model server is needed. With `LLM_PROVIDER=mock` no model is called and the brief is built from the facts extracted from the documents, which makes the run repeatable. Traces are written to PostgreSQL when it is reachable and skipped with a warning when it is not.

## Reports and baseline

- `.reports/eval-summary.json` has one entry per case and a summary (totals, passed, failed, injections detected, average and maximum latency).
- `.reports/regression-report.json` is written by `--regression-check`.
- `.reports/baseline-results.json` is the baseline. Create it by copying `eval-summary.json` from a full run you accept as good. A regression is a case that passed in the baseline and fails now, or a latency more than 5% above the baseline. Any regression makes the exit code 1. Latency depends on the machine and the model, so save the baseline on the machine that runs the comparison. A baseline entry with zero latency, such as one from a smoke run, is skipped for the latency comparison.

`.reports/` is ignored by git.

## CI

`.github/workflows/ci.yml` runs `poetry run python eval/harness.py --smoke`. CI has no model server, so this step confirms that the case file parses and the harness starts, not that the agent behaves correctly. Full runs are done by hand.

## Coverage today

- Only 2 of the 64 cases have expected values, so most cases check citation presence and latency and nothing about the content of the brief.
- Most cases point at the same sample contract (`examples/sample_contract.pdf`). Their names describe a scenario to cover (an expired contract, a missing invoice file, a liability cap), and a case only tests that scenario once it has its own input and expected entry.
- The six injection cases share one fixture and rely on the pattern-based classifier described in [threat-model.md](threat-model.md).
- Cost is recorded as `0.0`, so the cost budget never fails a case.

## Planned

- Give each scenario case its own input document and an expected entry.
- Score field accuracy and the share of fields returned as unknown across the set.
- Check citations against the cited text.
- Record real token cost per case and enforce the cost budget.
- Read `injection_suite.jsonl` and add an eval step that sends the full suite through the injection check.
- Run a full evaluation with a pinned model in a scheduled workflow and keep the scorecards.
