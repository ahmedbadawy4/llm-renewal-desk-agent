export interface Citation {
  doc_id: string
  page: number
  span?: string
}

export interface RenewalTerms {
  term_start?: string
  term_end?: string
  notice_window_days?: number
  auto_renew?: boolean
  citations?: Citation[]
}

export interface Pricing {
  annual_spend_usd?: number
  uplift_clause_pct?: number
  citations?: Citation[]
}

export interface Usage {
  allocated_seats?: number
  active_seats?: number
  delta_percent?: number
  citations?: Citation[]
}

export interface RiskFlags {
  auto_renew_soon?: boolean
  liability_cap_multiple?: number
  dpa_status?: string
  pii_risk?: string
  citations?: Citation[]
}

export interface NegotiationPlan {
  target_discount_pct?: number
  walkaway_delta_pct?: number
  levers?: string[]
  citations?: Citation[]
}

export interface DraftEmail {
  subject?: string
  body?: string
}

export interface Brief {
  vendor_id: string
  request_id: string
  renewal_terms?: RenewalTerms
  pricing?: Pricing
  usage?: Usage
  risk_flags?: RiskFlags
  negotiation_plan?: NegotiationPlan
  draft_email?: DraftEmail
}
