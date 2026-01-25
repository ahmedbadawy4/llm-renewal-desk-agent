import { Brief } from '@/types'

interface RenewalBriefViewerProps {
  brief: Brief
}

export default function RenewalBriefViewer({ brief }: RenewalBriefViewerProps) {
  return (
    <div className="brief-viewer">
      <section>
        <h3>Renewal Terms</h3>
        <p>Term: {brief.renewal_terms?.term_start} to {brief.renewal_terms?.term_end}</p>
        <p>Notice Window: {brief.renewal_terms?.notice_window_days} days</p>
        <p>Auto-renew: {brief.renewal_terms?.auto_renew ? 'Yes' : 'No'}</p>
        {brief.renewal_terms?.citations && brief.renewal_terms.citations.length > 0 && (
          <div className="citations">
            Citations:
            {brief.renewal_terms.citations.map((cite, i) => (
              <span key={i} className="citation">
                {cite.doc_id} (page {cite.page})
              </span>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3>Pricing</h3>
        <p>Annual Spend: ${brief.pricing?.annual_spend_usd?.toLocaleString()}</p>
        <p>Uplift: {brief.pricing?.uplift_clause_pct}%</p>
      </section>

      <section>
        <h3>Usage</h3>
        <p>Allocated Seats: {brief.usage?.allocated_seats}</p>
        <p>Active Seats: {brief.usage?.active_seats}</p>
        <p>Delta: {brief.usage?.delta_percent}%</p>
      </section>

      <section>
        <h3>Risk Flags</h3>
        <ul>
          <li>Auto-renew soon: {brief.risk_flags?.auto_renew_soon ? 'Yes' : 'No'}</li>
          <li>Liability Cap: {brief.risk_flags?.liability_cap_multiple}x</li>
          <li>DPA Status: {brief.risk_flags?.dpa_status}</li>
        </ul>
      </section>

      <section>
        <h3>Negotiation Plan</h3>
        <p>Target Discount: {brief.negotiation_plan?.target_discount_pct}%</p>
        <p>Walkaway Delta: {brief.negotiation_plan?.walkaway_delta_pct}%</p>
        <p>Levers: {brief.negotiation_plan?.levers?.join(', ')}</p>
      </section>

      <section>
        <h3>Draft Email</h3>
        <div className="email">
          <p><strong>Subject:</strong> {brief.draft_email?.subject}</p>
          <pre>{brief.draft_email?.body}</pre>
        </div>
      </section>
    </div>
  )
}
