from __future__ import annotations

from typing import List

from .hybrid_search import HybridSearcher

_hybrid_searcher: HybridSearcher | None = None


def _get_searcher() -> HybridSearcher:
    global _hybrid_searcher
    if _hybrid_searcher is None:
        _hybrid_searcher = HybridSearcher()
    return _hybrid_searcher


class RetrievalResult(dict):
    """Simple dict-like result placeholder."""


def retrieve_contract_terms(vendor_id: str, query: str) -> List[RetrievalResult]:
    searcher = _get_searcher()
    results = searcher.search(vendor_id, query, source="contract", k=5)

    return [
        RetrievalResult(
            {
                "doc_id": r["doc_id"],
                "page": r.get("chunk_index", 0),
                "snippet": r["snippet"],
                "score": r.get("score", 0.0),
            }
        )
        for r in results
    ]
