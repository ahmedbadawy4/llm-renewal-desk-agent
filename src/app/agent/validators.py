from __future__ import annotations

from . import schemas


def missing_citation_sections(brief: schemas.RenewalBriefSynthesis | schemas.RenewalBrief) -> list[str]:
    sections = {
        "renewal_terms": brief.renewal_terms,
        "pricing": brief.pricing,
        "usage": brief.usage,
        "risk_flags": brief.risk_flags,
        "negotiation_plan": brief.negotiation_plan,
    }
    missing = []
    for name, section in sections.items():
        citations = getattr(section, "citations", [])
        if not citations:
            missing.append(name)
    return missing


def citation_coverage_ratio(brief: schemas.RenewalBriefSynthesis | schemas.RenewalBrief) -> float:
    missing = missing_citation_sections(brief)
    total = 5
    coverage = (total - len(missing)) / total
    return round(coverage, 2)


def fail_closed_section(section_name: str) -> schemas.RenewalTerms | schemas.Pricing | schemas.UsageInsights | schemas.RiskFlags | schemas.NegotiationPlan:
    if section_name == "renewal_terms":
        return schemas.RenewalTerms()
    if section_name == "pricing":
        return schemas.Pricing()
    if section_name == "usage":
        return schemas.UsageInsights()
    if section_name == "risk_flags":
        return schemas.RiskFlags()
    if section_name == "negotiation_plan":
        return schemas.NegotiationPlan()
    raise ValueError(f"Unknown section: {section_name}")


def apply_fail_closed(
    brief: schemas.RenewalBriefSynthesis,
    missing_sections: list[str],
) -> schemas.RenewalBriefSynthesis:
    data = brief.model_dump()
    for name in missing_sections:
        data[name] = fail_closed_section(name).model_dump()
    return schemas.RenewalBriefSynthesis.model_validate(data, strict=True)


def validate_brief(brief: schemas.RenewalBrief) -> bool:
    return not missing_citation_sections(brief)
