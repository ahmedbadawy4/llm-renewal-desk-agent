#!/usr/bin/env python3
"""Lightweight eval harness scaffolding.

Usage:
    python eval/harness.py --cases eval/golden/cases.jsonl --expected eval/golden/expected.jsonl
"""
from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.app.agent import runner
from src.app.agent.exceptions import InjectionDetectedError
from src.app.core.config import Settings


@dataclass
class EvalCase:
    case_id: str
    payload: Dict[str, Any]


def load_jsonl(path: pathlib.Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def evaluate_case(case: EvalCase, expected: Dict[str, Any], smoke: bool = False) -> Dict[str, Any]:
    if smoke:
        return {"case_id": case.case_id, "status": "smoke_passed", "details": "Files parsed"}

    settings = Settings()
    vendor_id = case.payload.get("vendor_id", case.case_id)
    paths = _build_input_paths(case.payload.get("inputs", {}))

    try:
        brief = runner.generate_brief(vendor_id=vendor_id, refresh=False, settings=settings, inputs=paths)
    except InjectionDetectedError:
        status = "injection_detected"
        expected_behavior = expected.get("expected_behavior")
        return {
            "case_id": case.case_id,
            "status": status,
            "expected_behavior": expected_behavior,
            "passed": expected_behavior == status,
        }

    actual = json.loads(brief.model_dump_json())
    mismatches = _diff_expected(actual, expected)
    citation_gaps = _citation_gaps(brief)
    status = "passed" if not mismatches else "failed"

    return {
        "case_id": case.case_id,
        "status": status,
        "mismatches": mismatches,
        "citation_gaps": citation_gaps,
        "vendor_id": vendor_id,
    }


def run(cases_path: pathlib.Path, expected_path: pathlib.Path, smoke: bool) -> None:
    cases = [EvalCase(case_id=item["case_id"], payload=item) for item in load_jsonl(cases_path)]
    expected_map = {item["case_id"]: item for item in load_jsonl(expected_path)} if expected_path.exists() else {}

    results = [evaluate_case(case, expected_map.get(case.case_id, {}), smoke=smoke) for case in cases]

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "injection_detected": sum(1 for r in results if r["status"] == "injection_detected"),
        "smoke_passed": sum(1 for r in results if r["status"] == "smoke_passed"),
    }

    report_dir = pathlib.Path(".reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "eval-summary.json"
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump({"results": results, "summary": summary}, handle, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"Wrote report to {report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Renewal Desk eval harness")
    parser.add_argument("--cases", type=pathlib.Path, default=pathlib.Path("eval/golden/cases.jsonl"))
    parser.add_argument("--expected", type=pathlib.Path, default=pathlib.Path("eval/golden/expected.jsonl"))
    parser.add_argument("--smoke", action="store_true", help="Only verify files and serialization")
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


def _diff_expected(actual: Dict[str, Any], expected: Dict[str, Any]) -> List[str]:
    if not expected:
        return []
    mismatches: List[str] = []
    for section, exp_value in expected.items():
        if section == "case_id" or section == "expected_behavior":
            continue
        act_section = actual.get(section)
        if isinstance(exp_value, dict):
            for key, val in exp_value.items():
                act_val = act_section.get(key) if isinstance(act_section, dict) else None
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


if __name__ == "__main__":
    args = parse_args()
    run(args.cases, args.expected, smoke=args.smoke)
