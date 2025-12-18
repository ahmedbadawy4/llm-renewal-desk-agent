from __future__ import annotations

from typing import List


class RetrievalResult(dict):
    """Simple dict-like result placeholder."""


def retrieve_contract_terms(vendor_id: str, query: str) -> List[RetrievalResult]:
    # TODO: Replace with pgvector + hybrid search queries.
    return [
        RetrievalResult(
            {
                "doc_id": "examples/sample_contract.pdf",
                "page": 1,
                "snippet": "TERM: Effective Jan 1 2024 ...",
            }
        )
    ]
