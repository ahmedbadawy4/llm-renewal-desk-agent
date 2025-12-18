from pathlib import Path

import pytest

from src.app.agent import runner
from src.app.agent.exceptions import InjectionDetectedError
from src.app.core.config import Settings


def test_generate_brief_from_examples():
    settings = Settings()
    inputs = runner.InputPaths(
        contract_path=Path("examples/sample_contract.pdf"),
        invoices_path=Path("examples/invoices.csv"),
        usage_path=Path("examples/usage.csv"),
    )
    brief = runner.generate_brief("vendor_123", refresh=False, settings=settings, inputs=inputs)

    assert brief.renewal_terms.notice_window_days == 60
    assert brief.pricing.annual_spend_usd == 120000
    assert brief.usage.allocated_seats == 500
    assert brief.negotiation_plan.target_discount_pct in {5, 10}


def test_generate_brief_injection_detected():
    settings = Settings()
    inputs = runner.InputPaths(contract_path=Path("tests/fixtures/injection_contract.txt"))

    with pytest.raises(InjectionDetectedError):
        runner.generate_brief("vendor_mal", refresh=False, settings=settings, inputs=inputs)
