from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..core.config import Settings, get_settings
from ..storage.postgres import get_connection
from ..storage.vector_store import VectorStore
from .embeddings import generate_embedding

logger = logging.getLogger(__name__)


class HybridSearcher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.vector_store = VectorStore(self.settings)
        self.enabled = self.vector_store.enabled

    def search(
        self,
        vendor_id: str,
        query: str,
        source: str = "contract",
        k: int = 5,
        vector_weight: float = 0.7,
    ) -> List[Dict[str, Any]]:
        if not self.enabled:
            return self._fallback_search(vendor_id, query, source)

        vector_results = self._vector_search(vendor_id, query, source, k * 2)
        bm25_results = self._bm25_search(vendor_id, query, source, k * 2)

        combined = self._combine_results(vector_results, bm25_results, vector_weight, k)
        reranked = self._rerank(combined, query)

        return reranked[:k]

    def _vector_search(
        self,
        vendor_id: str,
        query: str,
        source: str,
        k: int,
    ) -> List[Dict[str, Any]]:
        try:
            query_embedding = generate_embedding(query)
            results = self.vector_store.query(vendor_id, query_embedding, k, doc_type=source)
            return [
                {
                    "doc_id": str(r["doc_id"]),
                    "chunk_index": int(r["chunk_index"]),
                    "snippet": (str(r["chunk_text"])[:200] + "..." if len(str(r["chunk_text"])) > 200 else str(r["chunk_text"])),
                    "score": float(r["similarity"]),
                    "method": "vector",
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    def _bm25_search(
        self,
        vendor_id: str,
        query: str,
        source: str,
        k: int,
    ) -> List[Dict[str, Any]]:
        try:
            with get_connection(self.settings) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT doc_id, chunk_index, chunk_text,
                               ts_rank(to_tsvector('english', chunk_text), 
                                       plainto_tsquery('english', %s)) as rank
                        FROM document_chunks
                        WHERE vendor_id = %s AND doc_type = %s
                          AND to_tsvector('english', chunk_text) @@ plainto_tsquery('english', %s)
                        ORDER BY rank DESC
                        LIMIT %s
                        """,
                        (query, vendor_id, source, query, k),
                    )

                    results = []
                    for row in cur.fetchall():
                        chunk_text = row[2]
                        results.append(
                            {
                                "doc_id": row[0],
                                "chunk_index": row[1],
                                "snippet": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                                "score": float(row[3]),
                                "method": "bm25",
                            }
                        )
                    return results
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []

    def _combine_results(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        vector_weight: float,
        k: int,
    ) -> List[Dict[str, Any]]:
        combined: Dict[str, Dict[str, Any]] = {}

        for result in vector_results:
            key = f"{result['doc_id']}_{result['chunk_index']}"
            if key not in combined:
                combined[key] = result.copy()
                combined[key]["vector_score"] = result["score"]
                combined[key]["bm25_score"] = 0.0
            else:
                combined[key]["vector_score"] = max(combined[key].get("vector_score", 0), result["score"])

        for result in bm25_results:
            key = f"{result['doc_id']}_{result['chunk_index']}"
            if key not in combined:
                combined[key] = result.copy()
                combined[key]["vector_score"] = 0.0
                combined[key]["bm25_score"] = result["score"]
            else:
                combined[key]["bm25_score"] = max(combined[key].get("bm25_score", 0), result["score"])

        normalized = []
        for item in combined.values():
            vector_score = item.get("vector_score", 0.0)
            bm25_score = item.get("bm25_score", 0.0)

            hybrid_score = (vector_weight * vector_score) + ((1 - vector_weight) * bm25_score)
            item["score"] = hybrid_score
            normalized.append(item)

        return sorted(normalized, key=lambda x: x["score"], reverse=True)

    def _rerank(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        for result in results:
            snippet_lower = result["snippet"].lower()
            term_matches = sum(1 for term in query_terms if term in snippet_lower)
            boost = 1.0 + (term_matches * 0.1)
            result["score"] = result["score"] * boost

        return sorted(results, key=lambda x: x["score"], reverse=True)

    def _fallback_search(self, vendor_id: str, query: str, source: str) -> List[Dict[str, Any]]:
        return [
            {
                "doc_id": f"{source}/{vendor_id}",
                "chunk_index": 0,
                "snippet": "Vector search not available",
                "score": 0.42,
                "method": "fallback",
            }
        ]
