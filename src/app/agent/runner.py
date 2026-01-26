from __future__ import annotations

import csv
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from threading import Lock
from typing import Any, Dict, Optional

from opentelemetry import trace

from . import schemas
from .exceptions import InjectionDetectedError
from .safety import contains_prompt_injection
from . import validators
from ..core import cache as core_cache
from ..core import debug as core_debug
from ..core import metrics as core_metrics
from ..core.config import Settings
from ..llm.router import ModelRouter
from ..storage import object_store
from ..storage import pdf_parser

DATE_FORMATS = ("%b %d %Y", "%B %d %Y", "%b %d, %Y", "%Y-%m-%d")
ContractFields = Dict[str, Any]
COST_PER_1K_TOKENS_USD = 0.0001


class _BudgetTracker:
    def __init__(self) -> None:
        self._lock = Lock()
        self._date = date.today()
        self._spent_usd = 0.0

    def _reset_if_new_day(self) -> None:
        today = date.today()
        if today != self._date:
            self._date = today
            self._spent_usd = 0.0

    def can_spend(self, amount_usd: float, daily_budget_usd: float) -> bool:
        if daily_budget_usd <= 0:
            return True
        with self._lock:
            self._reset_if_new_day()
            return (self._spent_usd + amount_usd) <= daily_budget_usd

    def record(self, amount_usd: float, daily_budget_usd: float) -> float:
        if daily_budget_usd <= 0:
            return 0.0
        with self._lock:
            self._reset_if_new_day()
            self._spent_usd += amount_usd
            return self._spent_usd


_BUDGET_TRACKER = _BudgetTracker()


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
    cache = core_cache.get_cache()
    cache_key = cache.cache_key("brief", vendor_id, refresh)

    if not refresh:
        cached = cache.get(cache_key)
        if cached:
            return schemas.RenewalBrief.model_validate(cached)
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("retrieval") as span:
        paths = inputs or _resolve_inputs(vendor_id, settings)
        contract_text = _read_text(paths.contract_path)
        invoices_text = _read_text(paths.invoices_path)
        usage_text = _read_text(paths.usage_path)
        span.set_attribute("vendor_id", vendor_id)
        span.set_attribute("contract_present", bool(contract_text))
        span.set_attribute("invoices_present", bool(invoices_text))
        span.set_attribute("usage_present", bool(usage_text))

    if not contract_text:
        from ..workers.job_queue import get_job_queue
        job_queue = get_job_queue(settings)
        jobs = job_queue.list_jobs(vendor_id)
        pending_jobs = [j for j in jobs if j.status.value in ["pending", "processing"]]
        
        if pending_jobs:
            job_ids = [j.job_id for j in pending_jobs]
            raise RuntimeError(
                f"Contract text not available yet. Async processing jobs are still running. "
                f"Job IDs: {', '.join(job_ids[:3])}. "
                f"Please wait for jobs to complete or check status at /jobs?vendor_id={vendor_id}"
            )
        elif paths.contract_path:
            raise RuntimeError(
                f"Missing contract text. PDF parsing may have failed for {paths.contract_path}. "
                f"Please check job status at /jobs?vendor_id={vendor_id} or re-ingest the contract."
            )
        else:
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

    contract_fields = _extract_contract_fields(contract_text, paths.contract_path)
    invoices_summary = _summarize_invoices(paths.invoices_path)
    licensed_seats = _get_int_field(contract_fields, "licensed_seats")
    usage_summary = _summarize_usage(paths.usage_path, licensed_seats)

    synthesis = None
    llm_stats: dict[str, Any] = {"tokens_in": 0, "tokens_out": 0, "cost_usd_estimate": None}
    if settings.llm_provider.strip().lower() == "ollama":
        with tracer.start_as_current_span("llm_call"):
            synthesis, llm_stats = _synthesize_brief_with_ollama(
                vendor_id=vendor_id,
                request_id=request_id,
                contract_text=contract_text,
                invoices_text=invoices_text,
                usage_text=usage_text,
                contract_fields=contract_fields,
                invoices_summary=invoices_summary,
                usage_summary=usage_summary,
                contract_doc=contract_doc,
                invoices_doc=invoices_doc,
                usage_doc=usage_doc,
                settings=settings,
            )

    coverage_ratio = None
    with tracer.start_as_current_span("validation"):
        if synthesis:
            missing_sections = validators.missing_citation_sections(synthesis)
            if missing_sections:
                synthesis = validators.apply_fail_closed(synthesis, missing_sections)
            coverage_ratio = validators.citation_coverage_ratio(synthesis)

    with tracer.start_as_current_span("response_build"):
        if synthesis:
            renewal_terms = synthesis.renewal_terms
            pricing = synthesis.pricing
            usage = synthesis.usage
            risk_flags = synthesis.risk_flags
            negotiation_plan = synthesis.negotiation_plan
        else:
            renewal_terms = schemas.RenewalTerms(
                term_start=_get_date_field(contract_fields, "term_start"),
                term_end=_get_date_field(contract_fields, "term_end"),
                notice_window_days=_get_int_field(contract_fields, "notice_window_days"),
                auto_renew=_get_bool_field(contract_fields, "auto_renew"),
                citations=_citations(contract_doc, span="TERM"),
            )

            stated_price = _get_float_field(contract_fields, "stated_price")
            annual_spend = invoices_summary.annual_spend_usd or stated_price
            pricing = schemas.Pricing(
                annual_spend_usd=annual_spend,
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

        draft_email, draft_source = _draft_email(
            vendor_id, 
            usage_summary, 
            invoices_summary, 
            pricing,
            usage,
            settings
        )

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

    if coverage_ratio is None:
        coverage_ratio = validators.citation_coverage_ratio(brief)
    core_metrics.record_citation_coverage(coverage_ratio)

    cache = core_cache.get_cache()
    cache_key = cache.cache_key("brief", vendor_id, refresh)
    cache.set(cache_key, brief.model_dump(), ttl_seconds=3600)

    tokens_in = _estimate_tokens(contract_text, invoices_text, usage_text)
    tokens_out = _estimate_tokens(brief.model_dump_json())
    core_metrics.record_agent_completion("success")
    core_metrics.record_renewal_brief_generated(vendor_id)
    core_metrics.record_vendor_processed()
    core_metrics.record_token_usage("in", tokens_in)
    core_metrics.record_token_usage("out", tokens_out)
    if llm_stats.get("tokens_in"):
        core_metrics.record_llm_token_usage("in", llm_stats["tokens_in"])
    if llm_stats.get("tokens_out"):
        core_metrics.record_llm_token_usage("out", llm_stats["tokens_out"])

    core_debug.record_trace(
        request_id,
        {
            "vendor_id": vendor_id,
            "retrieved_doc_ids": [contract_doc, invoices_doc, usage_doc],
            "tool_calls": [
                "extract_contract_fields",
                "summarize_invoices",
                "summarize_usage",
                "synthesize_brief_llm" if synthesis else "synthesize_brief",
                "build_negotiation_plan" if not synthesis else "llm_negotiation_plan",
                "draft_email_llm" if draft_source == "ollama" else "draft_email",
            ],
            "tokens": {
                "in": tokens_in,
                "out": tokens_out,
                "total": tokens_in + tokens_out,
            },
            "llm_tokens": {
                "in": llm_stats.get("tokens_in", 0),
                "out": llm_stats.get("tokens_out", 0),
            },
            "cost_usd_estimate": llm_stats.get("cost_usd_estimate"),
            "validation": _validation_snapshot(brief, injection_status="not_detected", coverage_ratio=coverage_ratio),
        },
    )

    return brief


def _validation_snapshot(
    brief: schemas.RenewalBrief,
    injection_status: str,
    coverage_ratio: Optional[float] = None,
) -> Dict[str, Any]:
    sections = {
        "renewal_terms": brief.renewal_terms.citations,
        "pricing": brief.pricing.citations,
        "usage": brief.usage.citations,
        "risk_flags": brief.risk_flags.citations,
        "negotiation_plan": brief.negotiation_plan.citations,
    }
    coverage = coverage_ratio
    if coverage is None:
        coverage = sum(1 for citations in sections.values() if citations) / len(sections)
    return {
        "citation_coverage": round(coverage, 2),
        "sections_with_citations": [name for name, cites in sections.items() if cites],
        "sections_missing_citations": [name for name, cites in sections.items() if not cites],
        "prompt_injection": injection_status,
    }


def _synthesize_brief_with_ollama(
    vendor_id: str,
    request_id: str,
    contract_text: str,
    invoices_text: str,
    usage_text: str,
    contract_fields: ContractFields,
    invoices_summary: SpendSummary,
    usage_summary: UsageSummary,
    contract_doc: str,
    invoices_doc: str,
    usage_doc: str,
    settings: Settings,
) -> tuple[Optional[schemas.RenewalBriefSynthesis], Dict[str, Any]]:
    prompt = _build_synthesis_prompt(
        vendor_id=vendor_id,
        request_id=request_id,
        contract_text=contract_text,
        invoices_text=invoices_text,
        usage_text=usage_text,
        contract_fields=contract_fields,
        invoices_summary=invoices_summary,
        usage_summary=usage_summary,
        contract_doc=contract_doc,
        invoices_doc=invoices_doc,
        usage_doc=usage_doc,
    )
    estimated_prompt_tokens = _estimate_tokens(prompt)
    estimated_cost = _estimate_cost_usd(estimated_prompt_tokens)
    if not _BUDGET_TRACKER.can_spend(estimated_cost, settings.daily_budget_usd):
        core_metrics.record_llm_error("budget_exceeded")
        return None, {"tokens_in": 0, "tokens_out": 0, "cost_usd_estimate": None}

    messages = [
        {"role": "system", "content": _load_prompt_base()},
        {"role": "user", "content": prompt},
    ]

    timer = core_metrics.LLMRequestTimer("llm")
    try:
        response = _call_llm(settings, messages, estimated_tokens=int(estimated_prompt_tokens), complexity="medium")
    except Exception:
        core_metrics.record_llm_error("request_failed")
        return None, {"tokens_in": 0, "tokens_out": 0, "cost_usd_estimate": None}
    finally:
        timer.observe()

    content = response.get("message", {}).get("content", "")
    usage = response.get("usage", {})
    tokens_in = float(usage.get("prompt_tokens") or usage.get("prompt_eval_count") or 0)
    tokens_out = float(usage.get("completion_tokens") or usage.get("eval_count") or 0)
    total_tokens = tokens_in + tokens_out
    cost_estimate = _estimate_cost_usd(total_tokens or estimated_prompt_tokens)
    _BUDGET_TRACKER.record(cost_estimate, settings.daily_budget_usd)

    try:
        data = _extract_json_payload(content)
        synthesis = schemas.RenewalBriefSynthesis.model_validate(data)
    except Exception:
        core_metrics.record_validation_failure("schema")
        core_metrics.record_llm_error("invalid_schema")
        return None, {"tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd_estimate": cost_estimate}

    missing_sections = validators.missing_citation_sections(synthesis)
    if missing_sections:
        core_metrics.record_validation_failure("citations")
        repaired = _repair_citations_with_ollama(
            synthesis=synthesis,
            missing_sections=missing_sections,
            prompt=prompt,
            settings=settings,
        )
        if repaired:
            synthesis = repaired
        else:
            core_metrics.record_llm_error("missing_citations")

    return synthesis, {"tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd_estimate": cost_estimate}


def _repair_citations_with_ollama(
    synthesis: schemas.RenewalBriefSynthesis,
    missing_sections: list[str],
    prompt: str,
    settings: Settings,
) -> Optional[schemas.RenewalBriefSynthesis]:
    repair_prompt = (
        "The JSON output is missing citations for sections: "
        f"{', '.join(missing_sections)}.\n"
        "Return corrected JSON only. For any field that cannot be supported by evidence, "
        "set it to null and leave citations empty. Do not add new sections.\n\n"
        f"Original prompt:\n{prompt}\n\n"
        f"Current JSON:\n{synthesis.model_dump_json()}"
    )
    messages = [
        {"role": "system", "content": _load_prompt_base()},
        {"role": "user", "content": repair_prompt},
    ]
    timer = core_metrics.LLMRequestTimer("llm")
    try:
        response = _call_llm(settings, messages, estimated_tokens=500, complexity="simple")
    except Exception:
        core_metrics.record_llm_error("repair_failed")
        return None
    finally:
        timer.observe()

    content = response.get("message", {}).get("content", "")
    try:
        data = _extract_json_payload(content)
        repaired = schemas.RenewalBriefSynthesis.model_validate(data)
    except Exception:
        core_metrics.record_validation_failure("repair_schema")
        return None

    if validators.missing_citation_sections(repaired):
        return None
    return repaired


def _build_synthesis_prompt(
    vendor_id: str,
    request_id: str,
    contract_text: str,
    invoices_text: str,
    usage_text: str,
    contract_fields: ContractFields,
    invoices_summary: SpendSummary,
    usage_summary: UsageSummary,
    contract_doc: str,
    invoices_doc: str,
    usage_doc: str,
) -> str:
    schema = {
        "renewal_terms": {
            "term_start": "YYYY-MM-DD or null",
            "term_end": "YYYY-MM-DD or null",
            "notice_window_days": "int or null",
            "auto_renew": "bool or null",
            "citations": [{"doc_id": contract_doc, "page": None, "span": "TERM"}],
        },
        "pricing": {
            "annual_spend_usd": "float or null",
            "uplift_clause_pct": "float or null",
            "citations": [{"doc_id": invoices_doc, "page": None, "span": "PRICING"}],
        },
        "usage": {
            "allocated_seats": "int or null",
            "active_seats": "int or null",
            "delta_percent": "float or null",
            "citations": [{"doc_id": usage_doc, "page": None, "span": "USAGE"}],
        },
        "risk_flags": {
            "auto_renew_soon": "bool or null",
            "liability_cap_multiple": "float or null",
            "dpa_status": "string or null",
            "pii_risk": "string or null",
            "citations": [{"doc_id": contract_doc, "page": None, "span": "RISK"}],
        },
        "negotiation_plan": {
            "target_discount_pct": "float or null",
            "walkaway_delta_pct": "float or null",
            "levers": ["string"],
            "citations": [{"doc_id": contract_doc, "page": None, "span": "NEGOTIATION"}],
        },
    }

    instructions = (
        "Return JSON only (no markdown). If evidence is missing for a field, set it to null "
        "and leave citations empty for that section. Each populated section must include at least "
        "one citation with doc_id and span. Use spans: TERM, PRICING, USAGE, RISK, NEGOTIATION."
    )

    return (
        f"{instructions}\n"
        f"Vendor: {vendor_id}\n"
        f"Request: {request_id}\n"
        f"Schema example:\n{json.dumps(schema, indent=2)}\n\n"
        "Structured facts (derived from evidence):\n"
        f"Contract fields: {json.dumps(contract_fields, default=str)}\n"
        f"Invoices summary: {json.dumps(invoices_summary.__dict__)}\n"
        f"Usage summary: {json.dumps(usage_summary.__dict__)}\n\n"
        "Evidence:\n"
        f"[contract doc_id={contract_doc}]\n{contract_text}\n\n"
        f"[invoices doc_id={invoices_doc}]\n{invoices_text}\n\n"
        f"[usage doc_id={usage_doc}]\n{usage_text}\n"
    )


def _load_prompt_base() -> str:
    path = Path(__file__).parent / "prompts" / "base.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return "You are a renewal desk assistant. Follow the schema exactly."


def _extract_json_payload(content: str) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _estimate_cost_usd(tokens: float) -> float:
    return round((tokens / 1000.0) * COST_PER_1K_TOKENS_USD, 6)


_router_cache: Dict[str, ModelRouter] = {}


def _get_router(settings: Settings) -> ModelRouter:
    cache_key = f"{settings.llm_provider}_{settings.ollama_base_url}"
    if cache_key not in _router_cache:
        _router_cache[cache_key] = ModelRouter(settings)
    return _router_cache[cache_key]


def _call_llm(
    settings: Settings,
    messages: list[Dict[str, str]],
    estimated_tokens: int = 0,
    complexity: str = "medium",
) -> Dict[str, Any]:
    router = _get_router(settings)
    budget_available = settings.daily_budget_usd - _BUDGET_TRACKER._spent_usd if settings.daily_budget_usd > 0 else 1.0

    return router.call(
        messages=messages,
        estimated_tokens=estimated_tokens,
        complexity=complexity,
        budget_available=budget_available,
        quality_requirement="standard",
        timeout_seconds=settings.request_timeout_s,
    )


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

    if path.suffix.lower() == ".pdf":
        vendor_dir = path.parent
        base_name = path.stem
        parsed_text_path = vendor_dir / "parsed" / f"{base_name}_text.txt"

        if parsed_text_path.exists():
            return pdf_parser.load_parsed_text(parsed_text_path)

        try:
            parse_result = pdf_parser.parse_pdf(path)
            pdf_parser.save_parsed_data(vendor_dir, path, parse_result)
            return parse_result.full_text
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"PDF parsing failed for {path}: {e}. Async job may still be processing.")
            return ""

    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_contract_fields(text: str, contract_path: Optional[Path] = None) -> ContractFields:
    result: ContractFields = {}

    if contract_path and contract_path.suffix.lower() == ".pdf":
        vendor_dir = contract_path.parent
        base_name = contract_path.stem
        parsed_tables_path = vendor_dir / "parsed" / f"{base_name}_tables.json"

        if parsed_tables_path.exists():
            tables = pdf_parser.load_parsed_tables(parsed_tables_path)
            _extract_from_tables(tables, result)

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

    annual_fee_match = re.search(r"annual\s+(?:license\s+)?fee\s+is\s+\$([0-9,]+)", text, re.IGNORECASE)
    if annual_fee_match:
        result["stated_price"] = float(annual_fee_match.group(1).replace(",", ""))
    else:
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


def _extract_from_tables(tables: list[pdf_parser.ExtractedTable], result: ContractFields) -> None:
    for table in tables:
        table_text = " ".join([" ".join(row) for row in table.data])
        table_lower = table_text.lower()

        if "price" in table_lower or "cost" in table_lower or "$" in table_text:
            for row in table.data:
                for cell in row:
                    price_match = re.search(r"\$([0-9,]+)", str(cell))
                    if price_match and "stated_price" not in result:
                        try:
                            result["stated_price"] = float(price_match.group(1).replace(",", ""))
                        except ValueError:
                            pass

        if "seat" in table_lower or "license" in table_lower:
            for row in table.data:
                for cell in row:
                    seats_match = re.search(r"(\d+)\s*seat", str(cell), re.IGNORECASE)
                    if seats_match and "licensed_seats" not in result:
                        try:
                            result["licensed_seats"] = int(seats_match.group(1))
                        except ValueError:
                            pass

        if "term" in table_lower or "date" in table_lower:
            for row in table.data:
                row_text = " ".join(str(cell) for cell in row)
                term_match = re.search(
                    r"effective\s+([\w\s,]+?)\s+(?:through|to)\s+([\w\s,]+?)",
                    row_text,
                    re.IGNORECASE,
                )
                if term_match:
                    start_date = _parse_date(term_match.group(1).strip())
                    end_date = _parse_date(term_match.group(2).strip())
                    if start_date and "term_start" not in result:
                        result["term_start"] = start_date
                    if end_date and "term_end" not in result:
                        result["term_end"] = end_date


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
    pricing: schemas.Pricing,
    usage: schemas.UsageInsights,
    settings: Settings,
) -> tuple[schemas.DraftEmail, str]:
    if settings.llm_provider.strip().lower() == "ollama":
        llm_email = _draft_email_with_ollama(vendor_id, usage_summary, invoices_summary, pricing, usage, settings)
        if llm_email:
            return llm_email, "ollama"
    return _draft_email_fallback(vendor_id, usage_summary, invoices_summary, pricing, usage), "heuristic"


def _draft_email_fallback(
    vendor_id: str,
    usage_summary: UsageSummary,
    invoices_summary: SpendSummary,
    pricing: schemas.Pricing,
    usage: schemas.UsageInsights,
) -> schemas.DraftEmail:
    spend = pricing.annual_spend_usd
    if spend is None:
        spend = invoices_summary.annual_spend_usd or 0
    delta = usage.delta_percent
    if delta is None:
        delta = usage_summary.delta_percent or 0
    subject = f"{vendor_id} renewal discussion"
    body = (
        f"Hi {vendor_id.title()} team,\n\n"
        f"We're preparing for the upcoming renewal. Current annual spend is ${spend:,.0f}"
        f" and usage is {abs(delta):.1f}% {'below' if delta < 0 else 'above'} contracted seats.\n"
        "We'd like to explore a pricing refresh that aligns with actual adoption while keeping the partnership strong.\n\n"
        "Let us know a good time to connect in the next week.\n\nThanks,\nRenewal Desk"
    )
    return schemas.DraftEmail(subject=subject, body=body)


def _draft_email_with_ollama(
    vendor_id: str,
    usage_summary: UsageSummary,
    invoices_summary: SpendSummary,
    pricing: schemas.Pricing,
    usage: schemas.UsageInsights,
    settings: Settings,
) -> Optional[schemas.DraftEmail]:
    spend = pricing.annual_spend_usd
    if spend is None:
        spend = invoices_summary.annual_spend_usd or 0
    delta = usage.delta_percent
    if delta is None:
        delta = usage_summary.delta_percent or 0
    direction = "below" if delta < 0 else "above"
    prompt = (
        "Write a concise renewal outreach email. Return JSON with keys "
        '`{"subject": "...", "body": "..."}` only.\n\n'
        f"Vendor: {vendor_id}\n"
        f"Annual spend: ${spend:,.0f}\n"
        f"Usage delta vs contracted seats: {abs(delta):.1f}% {direction}\n"
        "Tone: professional, collaborative, and action-oriented."
    )
    messages = [
        {"role": "system", "content": "You are a renewal desk assistant."},
        {"role": "user", "content": prompt},
    ]
    try:
        response = _call_llm(settings, messages, estimated_tokens=200, complexity="simple")
        content = response.get("message", {}).get("content", "")
        data = json.loads(content)
        subject = data.get("subject")
        body = data.get("body")
        if not subject or not body:
            return None
        return schemas.DraftEmail(subject=subject, body=body)
    except Exception:
        return None


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
