#!/usr/bin/env python3
"""Enhanced eval harness with budgets, tolerance bands, and regression detection.

Usage:
    python eval/harness.py --cases eval/golden/cases.jsonl --expected eval/golden/expected.jsonl
    python eval/harness.py --smoke
    python eval/harness.py --regression-check
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.app.agent import runner
from src.app.agent.exceptions import InjectionDetectedError
from src.app.core.config import Settings


@dataclass
class EvalCase:
    case_id: str
    payload: Dict[str, Any]
    cost_budget_usd: float = 0.01
    latency_budget_seconds: float = 30.0
    tolerance: Dict[str, float] | None = None


@dataclass
class EvalResult:
    case_id: str
    status: str
    passed: bool
    latency_seconds: float
    cost_usd: float
    cost_budget_exceeded: bool
    latency_budget_exceeded: bool
    mismatches: List[str]
    citation_gaps: List[str]
    tolerance_violations: List[str]
    details: Dict[str, Any] | None = None


def load_jsonl(path: pathlib.Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def evaluate_case(
    case: EvalCase,
    expected: Dict[str, Any],
    smoke: bool = False,
    baseline_results: Dict[str, EvalResult] | None = None,
) -> EvalResult:
    if smoke:
        return EvalResult(
            case_id=case.case_id,
            status="smoke_passed",
            passed=True,
            latency_seconds=0.0,
            cost_usd=0.0,
            cost_budget_exceeded=False,
            latency_budget_exceeded=False,
            mismatches=[],
            citation_gaps=[],
            tolerance_violations=[],
            details={"message": "Smoke mode: case loaded, agent skipped"},
        )

    settings = Settings()
    vendor_id = case.payload.get("vendor_id", case.case_id)
    paths = _build_input_paths(case.payload.get("inputs", {}))
    expect_injection = bool(case.payload.get("expect_injection")) or (
        expected.get("expected_behavior") == "injection_detected"
    )

    start_time = time.perf_counter()
    cost_estimate = 0.0

    try:
        brief = runner.generate_brief(vendor_id=vendor_id, refresh=False, settings=settings, inputs=paths)
        latency = time.perf_counter() - start_time

        actual = json.loads(brief.model_dump_json())
        mismatches = _diff_expected(actual, expected, case.tolerance or {})
        if expect_injection:
            mismatches.append("injection_detected: expected the request to be blocked")
        citation_gaps = _citation_gaps(brief)
        tolerance_violations = _check_tolerance(actual, expected, case.tolerance or {})

        cost_budget_exceeded = cost_estimate > case.cost_budget_usd
        latency_budget_exceeded = latency > case.latency_budget_seconds

        passed = (
            not mismatches
            and not citation_gaps
            and not tolerance_violations
            and not cost_budget_exceeded
            and not latency_budget_exceeded
        )

        status = "passed" if passed else "failed"

        return EvalResult(
            case_id=case.case_id,
            status=status,
            passed=passed,
            latency_seconds=latency,
            cost_usd=cost_estimate,
            cost_budget_exceeded=cost_budget_exceeded,
            latency_budget_exceeded=latency_budget_exceeded,
            mismatches=mismatches,
            citation_gaps=citation_gaps,
            tolerance_violations=tolerance_violations,
        )

    except InjectionDetectedError:
        latency = time.perf_counter() - start_time
        expected_behavior = "injection_detected" if expect_injection else expected.get("expected_behavior")
        passed = expect_injection

        return EvalResult(
            case_id=case.case_id,
            status="injection_detected",
            passed=passed,
            latency_seconds=latency,
            cost_usd=cost_estimate,
            cost_budget_exceeded=False,
            latency_budget_exceeded=latency > case.latency_budget_seconds,
            mismatches=[],
            citation_gaps=[],
            tolerance_violations=[],
            details={"expected_behavior": expected_behavior},
        )

    except Exception as e:
        latency = time.perf_counter() - start_time
        return EvalResult(
            case_id=case.case_id,
            status="error",
            passed=False,
            latency_seconds=latency,
            cost_usd=cost_estimate,
            cost_budget_exceeded=False,
            latency_budget_exceeded=latency > case.latency_budget_seconds,
            mismatches=[],
            citation_gaps=[],
            tolerance_violations=[],
            details={"error": str(e)},
        )


def _tolerance_for(tolerance: Dict[str, float], section: str, key: str) -> float | None:
    """Fractional tolerance for a field, given as `section.key` or just `key`."""
    if f"{section}.{key}" in tolerance:
        return tolerance[f"{section}.{key}"]
    return tolerance.get(key)


def _check_tolerance(actual: Dict[str, Any], expected: Dict[str, Any], tolerance: Dict[str, float]) -> List[str]:
    violations: List[str] = []
    if not tolerance:
        return violations

    for section, exp_value in expected.items():
        if section in ["case_id", "expected_behavior"]:
            continue

        act_section = actual.get(section)
        if isinstance(exp_value, dict) and isinstance(act_section, dict):
            for key, exp_val in exp_value.items():
                tol = _tolerance_for(tolerance, section, key)
                if tol is not None:
                    act_val = act_section.get(key)
                    if isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
                        diff = abs(act_val - exp_val)
                        threshold = abs(exp_val * tol)
                        if diff > threshold:
                            violations.append(
                                f"{section}.{key}: difference {diff} exceeds tolerance {threshold}"
                            )

    return violations


def _diff_expected(
    actual: Dict[str, Any],
    expected: Dict[str, Any],
    tolerance: Dict[str, float],
) -> List[str]:
    if not expected:
        return []
    mismatches: List[str] = []
    for section, exp_value in expected.items():
        if section in ["case_id", "expected_behavior"]:
            continue
        act_section = actual.get(section)
        if isinstance(exp_value, dict):
            for key, val in exp_value.items():
                act_val = act_section.get(key) if isinstance(act_section, dict) else None
                tol = _tolerance_for(tolerance, section, key)
                if tol is not None:
                    if isinstance(val, (int, float)) and isinstance(act_val, (int, float)):
                        diff = abs(act_val - val)
                        threshold = abs(val * tol)
                        if diff > threshold:
                            mismatches.append(f"{section}.{key}: expected {val}, got {act_val} (diff: {diff})")
                    elif str(act_val) != str(val):
                        # A missing or non-numeric value cannot sit inside a numeric band.
                        mismatches.append(f"{section}.{key}: expected {val}, got {act_val}")
                else:
                    if str(act_val) != str(val):
                        mismatches.append(f"{section}.{key}: expected {val}, got {act_val}")
        else:
            if str(act_section) != str(exp_value):
                mismatches.append(f"{section}: expected {exp_value}, got {act_section}")
    return mismatches


def _citation_gaps(brief: Any) -> List[str]:
    gaps: List[str] = []
    sections = {
        "renewal_terms": brief.renewal_terms,
        "pricing": brief.pricing,
        "usage": brief.usage,
        "risk_flags": brief.risk_flags,
        "negotiation_plan": brief.negotiation_plan,
    }
    for name, section in sections.items():
        citations = getattr(section, "citations", [])
        if not citations:
            gaps.append(name)
    return gaps


def check_regression(
    current_results: List[EvalResult],
    baseline_path: pathlib.Path,
    regression_threshold: float = 0.05,
) -> Dict[str, Any]:
    if not baseline_path.exists():
        return {"status": "no_baseline", "message": "No baseline results found"}

    with baseline_path.open("r", encoding="utf-8") as handle:
        baseline_data = json.load(handle)

    baseline_map = {r["case_id"]: r for r in baseline_data.get("results", [])}

    regressions: List[Dict[str, Any]] = []
    improvements: List[Dict[str, Any]] = []

    for current in current_results:
        baseline = baseline_map.get(current.case_id)
        if not baseline:
            continue

        baseline_passed = baseline.get("passed", False)
        current_passed = current.passed

        if baseline_passed and not current_passed:
            regressions.append(
                {
                    "case_id": current.case_id,
                    "baseline": "passed",
                    "current": "failed",
                    "details": {
                        "mismatches": current.mismatches,
                        "citation_gaps": current.citation_gaps,
                    },
                }
            )

        baseline_latency = baseline.get("latency_seconds", 0.0)
        if baseline_latency <= 0:
            # A zero baseline, for example one saved from a smoke run, has no latency to compare with.
            continue
        if current.latency_seconds > baseline_latency * (1 + regression_threshold):
            regressions.append(
                {
                    "case_id": current.case_id,
                    "metric": "latency",
                    "baseline": baseline_latency,
                    "current": current.latency_seconds,
                    "regression_pct": ((current.latency_seconds - baseline_latency) / baseline_latency) * 100,
                }
            )

        if current.latency_seconds < baseline_latency * (1 - regression_threshold):
            improvements.append(
                {
                    "case_id": current.case_id,
                    "metric": "latency",
                    "baseline": baseline_latency,
                    "current": current.latency_seconds,
                    "improvement_pct": ((baseline_latency - current.latency_seconds) / baseline_latency) * 100,
                }
            )

    return {
        "regressions": regressions,
        "improvements": improvements,
        "regression_count": len(regressions),
        "improvement_count": len(improvements),
    }


def run(
    cases_path: pathlib.Path,
    expected_path: pathlib.Path,
    smoke: bool,
    regression_check: bool = False,
) -> int:
    """Run the cases, write the reports and return the process exit code."""
    cases_data = load_jsonl(cases_path)
    cases = [
        EvalCase(
            case_id=item["case_id"],
            payload=item,
            cost_budget_usd=item.get("cost_budget_usd", 0.01),
            latency_budget_seconds=item.get("latency_budget_seconds", 30.0),
            tolerance=item.get("tolerance", {}),
        )
        for item in cases_data
    ]

    expected_map = {item["case_id"]: item for item in load_jsonl(expected_path)} if expected_path.exists() else {}

    baseline_path = pathlib.Path(".reports/baseline-results.json")
    baseline_results = None
    if baseline_path.exists():
        with baseline_path.open("r", encoding="utf-8") as handle:
            baseline_data = json.load(handle)
            baseline_results = {r["case_id"]: r for r in baseline_data.get("results", [])}

    results = [
        evaluate_case(case, expected_map.get(case.case_id, {}), smoke=smoke, baseline_results=baseline_results)
        for case in cases
    ]

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "injection_detected": sum(1 for r in results if r.status == "injection_detected"),
        "smoke_passed": sum(1 for r in results if r.status == "smoke_passed"),
        "cost_budget_exceeded": sum(1 for r in results if r.cost_budget_exceeded),
        "latency_budget_exceeded": sum(1 for r in results if r.latency_budget_exceeded),
        "avg_latency": sum(r.latency_seconds for r in results) / len(results) if results else 0.0,
        "max_latency": max((r.latency_seconds for r in results), default=0.0),
        "total_cost": sum(r.cost_usd for r in results),
    }

    report_dir = pathlib.Path(".reports")
    report_dir.mkdir(exist_ok=True)

    results_dict = [
        {
            "case_id": r.case_id,
            "status": r.status,
            "passed": r.passed,
            "latency_seconds": r.latency_seconds,
            "cost_usd": r.cost_usd,
            "cost_budget_exceeded": r.cost_budget_exceeded,
            "latency_budget_exceeded": r.latency_budget_exceeded,
            "mismatches": r.mismatches,
            "citation_gaps": r.citation_gaps,
            "tolerance_violations": r.tolerance_violations,
            "details": r.details,
        }
        for r in results
    ]

    report_path = report_dir / "eval-summary.json"
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump({"results": results_dict, "summary": summary}, handle, indent=2)

    regression_count = 0
    if regression_check:
        regression_report = check_regression(results, baseline_path)
        regression_path = report_dir / "regression-report.json"
        with regression_path.open("w", encoding="utf-8") as handle:
            json.dump(regression_report, handle, indent=2)
        if regression_report.get("status") == "no_baseline":
            print(f"Regression check skipped: no baseline at {baseline_path}")
        else:
            regression_count = regression_report["regression_count"]
            print(f"Regression check: {regression_count} regressions found")
        print(f"Wrote regression report to {regression_path}")

    print(json.dumps(summary, indent=2))
    print(f"Wrote report to {report_path}")

    # A smoke run never calls the agent, so only a full run can fail on cases.
    failed_cases = 0 if smoke else summary["failed"]
    return 1 if failed_cases or regression_count else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Renewal Desk eval harness")
    parser.add_argument("--cases", type=pathlib.Path, default=pathlib.Path("eval/golden/cases.jsonl"))
    parser.add_argument("--expected", type=pathlib.Path, default=pathlib.Path("eval/golden/expected.jsonl"))
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Load the cases and write the report without running the agent",
    )
    parser.add_argument("--regression-check", action="store_true", help="Check for regressions against baseline")
    return parser.parse_args()


def _build_input_paths(inputs: Dict[str, Any]) -> runner.InputPaths:
    def _maybe_path(key: str) -> Optional[pathlib.Path]:
        value = inputs.get(key)
        return pathlib.Path(value) if value else None

    return runner.InputPaths(
        contract_path=_maybe_path("contract_path"),
        invoices_path=_maybe_path("invoices_path"),
        usage_path=_maybe_path("usage_path"),
    )


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run(args.cases, args.expected, smoke=args.smoke, regression_check=args.regression_check))
