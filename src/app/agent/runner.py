from __future__ import annotations

import csv
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Optional

from . import schemas
from .exceptions import InjectionDetectedError
from .safety import contains_prompt_injection
from ..core import debug as core_debug
from ..core import metrics as core_metrics
from ..core.config import Settings
from ..storage import object_store

DATE_FORMATS = ("%b %d %Y", "%B %d %Y", "%b %d, %Y", "%Y-%m-%d")
ContractFields = Dict[str, Any]


@dataclass
class InputPaths:
    contract_path: Optional[Path] = None
    invoices_path: Optional[Path] = None
    usage_path: Optional[Path] = None


@dataclass
class SpendSummary:
    annual_spend_usd: Optional[float]
    avg_seats: Optional[float]


@dataclass
class UsageSummary:
    allocated_seats: Optional[int]
    active_seats: Optional[int]
    delta_percent: Optional[float]


def generate_brief(
    vendor_id: str,
    refresh: bool,
    settings: Settings,
    inputs: Optional[InputPaths] = None,
) -> schemas.RenewalBrief:
    paths = inputs or _resolve_inputs(vendor_id, settings)
    contract_text = _read_text(paths.contract_path)
    invoices_text = _read_text(paths.invoices_path)
    usage_text = _read_text(paths.usage_path)

    if not contract_text:
        raise RuntimeError("Missing contract text; ingest files before requesting a brief")

    request_id = str(uuid.uuid4())
    contract_doc = str(paths.contract_path) if paths.contract_path else "contract"
    invoices_doc = str(paths.invoices_path) if paths.invoices_path else "invoices"
    usage_doc = str(paths.usage_path) if paths.usage_path else "usage"

    if contains_prompt_injection(contract_text):
        core_metrics.record_agent_completion("injection_detected")
        core_debug.record_trace(
            request_id,
            {
                "vendor_id": vendor_id,
                "retrieved_doc_ids": [contract_doc, invoices_doc, usage_doc],
                "tool_calls": [],
                "tokens": {"in": 0, "out": 0, "total": 0},
                "cost_usd_estimate": None,
                "validation": {"prompt_injection": "blocked"},
            },
        )
        raise InjectionDetectedError()

    contract_fields = _extract_contract_fields(contract_text)
    invoices_summary = _summarize_invoices(paths.invoices_path)
    licensed_seats = _get_int_field(contract_fields, "licensed_seats")
    usage_summary = _summarize_usage(paths.usage_path, licensed_seats)

    renewal_terms = schemas.RenewalTerms(
        term_start=_get_date_field(contract_fields, "term_start"),
        term_end=_get_date_field(contract_fields, "term_end"),
        notice_window_days=_get_int_field(contract_fields, "notice_window_days"),
        auto_renew=_get_bool_field(contract_fields, "auto_renew"),
        citations=_citations(contract_doc, span="TERM"),
    )

    pricing = schemas.Pricing(
        annual_spend_usd=invoices_summary.annual_spend_usd,
        uplift_clause_pct=_get_float_field(contract_fields, "uplift_pct"),
        citations=_citations(invoices_doc, span="PRICING"),
    )

    usage = schemas.UsageInsights(
        allocated_seats=usage_summary.allocated_seats,
        active_seats=usage_summary.active_seats,
        delta_percent=usage_summary.delta_percent,
        citations=_citations(usage_doc, span="USAGE"),
    )

    risk_flags = schemas.RiskFlags(
        auto_renew_soon=_auto_renew_risk(_get_int_field(contract_fields, "notice_window_days")),
        liability_cap_multiple=_get_float_field(contract_fields, "liability_cap_multiple"),
        dpa_status=_get_str_field(contract_fields, "dpa_status"),
        pii_risk="low",
        citations=_citations(contract_doc, span="RISK"),
    )

    negotiation_plan = _build_negotiation_plan(contract_fields, usage_summary, contract_doc)
    draft_email = _draft_email(vendor_id, usage_summary, invoices_summary)

    brief = schemas.RenewalBrief(
        vendor_id=vendor_id,
        request_id=request_id,
        renewal_terms=renewal_terms,
        pricing=pricing,
        usage=usage,
        risk_flags=risk_flags,
        negotiation_plan=negotiation_plan,
        draft_email=draft_email,
    )

    tokens_in = _estimate_tokens(contract_text, invoices_text, usage_text)
    tokens_out = _estimate_tokens(brief.model_dump_json())
    core_metrics.record_agent_completion("success")
    core_metrics.record_token_usage("in", tokens_in)
    core_metrics.record_token_usage("out", tokens_out)

    core_debug.record_trace(
        request_id,
        {
            "vendor_id": vendor_id,
            "retrieved_doc_ids": [contract_doc, invoices_doc, usage_doc],
            "tool_calls": [
                "extract_contract_fields",
                "summarize_invoices",
                "summarize_usage",
                "build_negotiation_plan",
                "draft_email",
            ],
            "tokens": {"in": tokens_in, "out": tokens_out, "total": tokens_in + tokens_out},
            "cost_usd_estimate": None,
            "validation": _validation_snapshot(brief, injection_status="not_detected"),
        },
    )

    return brief


def _validation_snapshot(brief: schemas.RenewalBrief, injection_status: str) -> Dict[str, Any]:
    sections = {
        "renewal_terms": brief.renewal_terms.citations,
        "pricing": brief.pricing.citations,
        "usage": brief.usage.citations,
        "risk_flags": brief.risk_flags.citations,
        "negotiation_plan": brief.negotiation_plan.citations,
    }
    coverage = sum(1 for citations in sections.values() if citations) / len(sections)
    return {
        "citation_coverage": round(coverage, 2),
        "sections_with_citations": [name for name, cites in sections.items() if cites],
        "sections_missing_citations": [name for name, cites in sections.items() if not cites],
        "prompt_injection": injection_status,
    }


def _resolve_inputs(vendor_id: str, settings: Settings) -> InputPaths:
    manifest = object_store.load_manifest(vendor_id)
    contract = _path_or_none(manifest.get("contract"))
    invoices = _path_or_none(manifest.get("invoices"))
    usage = _path_or_none(manifest.get("usage"))

    examples = Path(settings.examples_dir)
    if not contract or not contract.exists():
        default_contract = examples / "sample_contract.pdf"
        if default_contract.exists():
            contract = default_contract
    if not invoices or not invoices.exists():
        fallback_invoices = examples / "invoices.csv"
        if fallback_invoices.exists():
            invoices = fallback_invoices
    if not usage or not usage.exists():
        fallback_usage = examples / "usage.csv"
        if fallback_usage.exists():
            usage = fallback_usage

    return InputPaths(contract_path=contract, invoices_path=invoices, usage_path=usage)


def _path_or_none(path_str: Optional[str]) -> Optional[Path]:
    if not path_str:
        return None
    return Path(path_str)


def _read_text(path: Optional[Path]) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_contract_fields(text: str) -> ContractFields:
    result: ContractFields = {}
    term_match = re.search(r"effective\s+([\w\s,]+?)\s+(?:through|to)\s+([\w\s,]+?)\.", text, re.IGNORECASE)
    if term_match:
        result["term_start"] = _parse_date(term_match.group(1).strip())
        result["term_end"] = _parse_date(term_match.group(2).strip())

    notice_match = re.search(r"notice\s+(\d{1,3})\s+days", text, re.IGNORECASE)
    if notice_match:
        result["notice_window_days"] = int(notice_match.group(1))

    result["auto_renew"] = "auto-renew" in text.lower()

    uplift_match = re.search(r"(\d{1,2})%\s+increase", text, re.IGNORECASE)
    if uplift_match:
        result["uplift_pct"] = float(uplift_match.group(1))

    price_match = re.search(r"\$([0-9,]+)", text)
    if price_match:
        result["stated_price"] = float(price_match.group(1).replace(",", ""))

    seats_match = re.search(r"licensed\s+for\s+(\d+)\s+seats", text, re.IGNORECASE)
    if seats_match:
        result["licensed_seats"] = int(seats_match.group(1))

    liability_match = re.search(r"liability.*?(\d+)x", text, re.IGNORECASE)
    if liability_match:
        result["liability_cap_multiple"] = float(liability_match.group(1))

    if "dpa" in text.lower():
        result["dpa_status"] = "missing" if "separately" in text.lower() else "present"

    return result


def _parse_date(value: str) -> Optional[date]:
    cleaned = value.replace(",", "")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _summarize_invoices(path: Optional[Path]) -> SpendSummary:
    if not path or not path.exists():
        return SpendSummary(annual_spend_usd=None, avg_seats=None)
    with path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return SpendSummary(annual_spend_usd=None, avg_seats=None)
    total = sum(float(row.get("amount_usd", 0) or 0) for row in rows)
    seats = [float(row.get("seats", 0) or 0) for row in rows if row.get("seats")]
    avg_seats = mean(seats) if seats else None
    return SpendSummary(annual_spend_usd=total, avg_seats=avg_seats)


def _summarize_usage(path: Optional[Path], fallback_allocated: Optional[int]) -> UsageSummary:
    if not path or not path.exists():
        return UsageSummary(
            allocated_seats=fallback_allocated,
            active_seats=None,
            delta_percent=None,
        )

    with path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return UsageSummary(
            allocated_seats=fallback_allocated,
            active_seats=None,
            delta_percent=None,
        )

    last = rows[-1]
    allocated = float(last.get("allocated_seats", fallback_allocated or 0) or 0)
    active = float(last.get("active_seats", 0) or 0)
    delta_percent = None
    if allocated:
        delta_percent = round(((active - allocated) / allocated) * 100, 2)

    allocated_int = int(allocated) if allocated else fallback_allocated
    active_int = int(active) if active else None

    return UsageSummary(
        allocated_seats=allocated_int,
        active_seats=active_int,
        delta_percent=delta_percent,
    )


def _auto_renew_risk(notice_window_days: Optional[int]) -> bool:
    if notice_window_days is None:
        return False
    return notice_window_days <= 60


def _build_negotiation_plan(
    contract_fields: ContractFields,
    usage_summary: UsageSummary,
    doc_id: str,
) -> schemas.NegotiationPlan:
    delta = usage_summary.delta_percent or 0
    target_discount = 10 if delta < -10 else 5
    walkaway = target_discount + 5
    levers = ["Usage below contracted seats" if delta < 0 else "Usage steady"]
    if contract_fields.get("uplift_pct"):
        levers.append("Seek uplift waiver")
    levers.append("Consider multi-year stabilization")

    return schemas.NegotiationPlan(
        target_discount_pct=target_discount,
        walkaway_delta_pct=walkaway,
        levers=levers,
        citations=_citations(doc_id, span="NEGOTIATION"),
    )


def _draft_email(
    vendor_id: str,
    usage_summary: UsageSummary,
    invoices_summary: SpendSummary,
) -> schemas.DraftEmail:
    delta = usage_summary.delta_percent or 0
    spend = invoices_summary.annual_spend_usd or 0
    subject = f"{vendor_id} renewal discussion"
    body = (
        f"Hi {vendor_id.title()} team,\n\n"
        f"We're preparing for the upcoming renewal. Current annual spend is ${spend:,.0f}"
        f" and usage is {abs(delta):.1f}% {'below' if delta < 0 else 'above'} contracted seats.\n"
        "We'd like to explore a pricing refresh that aligns with actual adoption while keeping the partnership strong.\n\n"
        "Let us know a good time to connect in the next week.\n\nThanks,\nRenewal Desk"
    )
    return schemas.DraftEmail(subject=subject, body=body)


def _citations(doc_id: str, span: Optional[str] = None) -> list[schemas.Citation]:
    return [schemas.Citation(doc_id=doc_id, span=span)]


def _estimate_tokens(*texts: Optional[str]) -> float:
    total = 0.0
    for text in texts:
        if not text:
            continue
        total += max(1, len(text.split()))
    return total


def _get_date_field(fields: ContractFields, key: str) -> Optional[date]:
    value = fields.get(key)
    return value if isinstance(value, date) else None


def _get_int_field(fields: ContractFields, key: str) -> Optional[int]:
    value = fields.get(key)
    if isinstance(value, bool):
        return None
    return int(value) if isinstance(value, int) else None


def _get_bool_field(fields: ContractFields, key: str) -> Optional[bool]:
    value = fields.get(key)
    return value if isinstance(value, bool) else None


def _get_float_field(fields: ContractFields, key: str) -> Optional[float]:
    value = fields.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _get_str_field(fields: ContractFields, key: str) -> Optional[str]:
    value = fields.get(key)
    return value if isinstance(value, str) else None
