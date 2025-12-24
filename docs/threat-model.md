# Threat Model

The Renewal Desk agent handles sensitive contracts, pricing, and PII. This model surfaces key risks and planned mitigations.

## Assets
- Vendor contracts, amendments, security documents
- Historical invoices + usage data
- Negotiation notes and stakeholder comments
- Prompt templates + retrieval configs (sensitive because they encode policy)
- Audit logs showing tool invocations + doc references

## Trust boundaries
1. **External file sources** -> ingestion pipeline (risk: malicious PDFs/executables)
2. **Retrieved text** -> LLM prompts (risk: prompt injection, data exfil)
3. **Tool gateway** -> downstream services (risk: privilege escalation, mass data access)
4. **Logs/metrics** -> observability stack (risk: PII leakage)

## Threat scenarios & mitigations
| Scenario | Impact | Mitigation |
| --- | --- | --- |
| Prompt injection inside contract text instructs the agent to leak secrets | Data exfiltration, hallucinated actions | Retrieval sanitizer quotes evidence blocks, strips instructions, and the agent policy forbids executing embedded commands. Validator enforces citations referencing trusted sources. |
| Uploaded file contains malware or unsupported format | Compromise workstation, ingestion failures | File type allowlist, size limits, optional ClamAV scan hook, store raw blobs in isolated bucket with no execution. |
| User without access attempts to fetch another vendor's data via tool calls | Data leak | Tool gateway enforces per-tenant RBAC and vendor scoping, logs every call, default deny policy. |
| Logs capture PII or contract text | Compliance violation | Structured logging only captures IDs + hashes; redaction toggle strips PII before LLM; audit logs stored in restricted bucket with lifecycle policies. |
| Model produces output without evidence or fabricates clause | Legal risk | Citation validator fails the response, returns `unknown`, and records search context for follow-up. |
| Long-running agent loops burn tokens/cost | Budget overrun | Hard limits on tool calls, tokens, and wall clock; budgets tracked per tenant and request; on breach agent aborts with partial results + reason. |
| Prompt or retrieval config pushed without testing | Regression in prod | Version prompts/config as artifacts; CI evals + canary release; `/debug/trace` retains prior versions for rollback. |

## Residual risks
- Unknown vulnerabilities in PDF parsing libraries (mitigate via sandboxed parsing container and regular patching).
- Determined insiders could screenshot outputs; requires org-level controls beyond this repo (DLP, workspace policies).
- Third-party LLM providers must be vetted; encrypt traffic and avoid sending secrets.

Keep this doc updated as new tools/endpoints ship. Every new capability should come with an explicit threat analysis entry.
