from __future__ import annotations

from pathlib import Path


def get_contract_text(vendor_id: str) -> str:
    # Placeholder: return bundled sample file contents.
    path = Path("examples/sample_contract.pdf")
    return path.read_text()
