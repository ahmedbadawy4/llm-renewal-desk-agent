from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    doc_id: str
    page: Optional[int] = None
    span: Optional[str] = None


class RenewalTerms(BaseModel):
    term_start: Optional[date] = None
    term_end: Optional[date] = None
    notice_window_days: Optional[int] = None
    auto_renew: Optional[bool] = None
    citations: List[Citation] = Field(default_factory=list)


class Pricing(BaseModel):
    annual_spend_usd: Optional[float] = None
    uplift_clause_pct: Optional[float] = None
    citations: List[Citation] = Field(default_factory=list)


class UsageInsights(BaseModel):
    allocated_seats: Optional[int] = None
    active_seats: Optional[int] = None
    delta_percent: Optional[float] = None
    citations: List[Citation] = Field(default_factory=list)


class RiskFlags(BaseModel):
    auto_renew_soon: bool = False
    liability_cap_multiple: Optional[float] = None
    dpa_status: Optional[str] = None
    pii_risk: Optional[str] = None
    citations: List[Citation] = Field(default_factory=list)


class NegotiationPlan(BaseModel):
    target_discount_pct: Optional[float] = None
    walkaway_delta_pct: Optional[float] = None
    levers: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)


class DraftEmail(BaseModel):
    subject: str
    body: str


class RenewalBrief(BaseModel):
    vendor_id: str
    request_id: str
    renewal_terms: RenewalTerms
    pricing: Pricing
    usage: UsageInsights
    risk_flags: RiskFlags
    negotiation_plan: NegotiationPlan
    draft_email: DraftEmail


class RenewalBriefResponse(BaseModel):
    status: str
    request_id: str
    brief: RenewalBrief
