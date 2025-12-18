from __future__ import annotations

from . import schemas


def validate_brief(brief: schemas.RenewalBrief) -> bool:
    """Placeholder validator enforcing citation presence."""
    sections = [
        brief.renewal_terms,
        brief.pricing,
        brief.usage,
        brief.risk_flags,
        brief.negotiation_plan,
    ]
    for section in sections:
        citations = getattr(section, "citations", [])
        if not citations:
            return False
    return True
