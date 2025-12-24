import json

from fastapi.testclient import TestClient

from src.app.agent import runner, schemas
from src.app.main import create_app


def test_renewal_brief_smoke_with_mocked_llm(monkeypatch):
    def fake_call(settings, payload):
        content = json.dumps(
            {
                "renewal_terms": {
                    "term_start": "2024-02-01",
                    "term_end": "2025-02-01",
                    "notice_window_days": 60,
                    "auto_renew": True,
                    "citations": [{"doc_id": "contract", "page": None, "span": "TERM"}],
                },
                "pricing": {
                    "annual_spend_usd": 120000.0,
                    "uplift_clause_pct": 5.0,
                    "citations": [],
                },
                "usage": {
                    "allocated_seats": 500,
                    "active_seats": 420,
                    "delta_percent": -16.0,
                    "citations": [{"doc_id": "usage", "page": None, "span": "USAGE"}],
                },
                "risk_flags": {
                    "auto_renew_soon": True,
                    "liability_cap_multiple": 2.0,
                    "dpa_status": "present",
                    "pii_risk": "low",
                    "citations": [{"doc_id": "contract", "page": None, "span": "RISK"}],
                },
                "negotiation_plan": {
                    "target_discount_pct": 10.0,
                    "walkaway_delta_pct": 15.0,
                    "levers": ["Usage below contracted seats"],
                    "citations": [{"doc_id": "contract", "page": None, "span": "NEGOTIATION"}],
                },
            }
        )
        return {
            "message": {"content": content},
            "prompt_eval_count": 120,
            "eval_count": 220,
        }

    monkeypatch.setattr(runner, "_call_ollama_chat", fake_call)

    client = TestClient(create_app())
    resp = client.post(
        "/renewal-brief?vendor_id=vendor_123",
        json={"refresh": False, "llm_provider": "ollama"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    response = schemas.RenewalBriefResponse.model_validate(payload)
    brief = response.brief
    assert brief.renewal_terms.citations
    assert brief.usage.citations
    assert brief.risk_flags.citations
    assert brief.negotiation_plan.citations
    assert brief.pricing.annual_spend_usd is None
    assert brief.pricing.uplift_clause_pct is None
    assert brief.pricing.citations == []
    citations = sum(
        len(section.citations)
        for section in [
            brief.renewal_terms,
            brief.pricing,
            brief.usage,
            brief.risk_flags,
            brief.negotiation_plan,
        ]
    )
    assert citations >= 4
