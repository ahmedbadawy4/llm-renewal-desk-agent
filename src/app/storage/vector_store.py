from __future__ import annotations

import logging
from typing import List

from ..core.config import Settings, get_settings
from .postgres import get_connection

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.enabled = self._check_pgvector_enabled()

    def _check_pgvector_enabled(self) -> bool:
        try:
            with get_connection(self.settings) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                    return cur.fetchone() is not None
        except Exception as e:
            logger.warning(f"pgvector extension check failed: {e}")
            return False

    def _ensure_schema(self) -> None:
        with get_connection(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id BIGSERIAL PRIMARY KEY,
                        vendor_id VARCHAR(255) NOT NULL,
                        doc_id VARCHAR(255) NOT NULL,
                        doc_type VARCHAR(50) NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        chunk_text TEXT NOT NULL,
                        embedding vector(384),
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(vendor_id, doc_id, chunk_index)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_vendor_doc 
                    ON document_chunks(vendor_id, doc_id)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
                    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata 
                    ON document_chunks USING gin(metadata)
                    """
                )

    def upsert(self, vendor_id: str, doc_id: str, doc_type: str, chunks: List[tuple[int, str, list[float]]]) -> None:
        if not self.enabled:
            logger.warning("pgvector not enabled, skipping upsert")
            return

        self._ensure_schema()

        with get_connection(self.settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM document_chunks 
                    WHERE vendor_id = %s AND doc_id = %s
                    """,
                    (vendor_id, doc_id),
                )

                for chunk_index, chunk_text, embedding in chunks:
                    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
                    cur.execute(
                        """
                        INSERT INTO document_chunks 
                        (vendor_id, doc_id, doc_type, chunk_index, chunk_text, embedding, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s::vector, %s)
                        ON CONFLICT (vendor_id, doc_id, chunk_index) 
                        DO UPDATE SET 
                            chunk_text = EXCLUDED.chunk_text,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """,
                        (
                            vendor_id,
                            doc_id,
                            doc_type,
                            chunk_index,
                            chunk_text,
                            embedding_str,
                            "{}",
                        ),
                    )

    def query(
        self,
        vendor_id: str,
        query_embedding: list[float],
        k: int = 5,
        doc_type: str | None = None,
    ) -> list[dict[str, float | str | int]]:
        if not self.enabled:
            return []

        self._ensure_schema()

        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        with get_connection(self.settings) as conn:
            with conn.cursor() as cur:
                if doc_type:
                    cur.execute(
                        """
                        SELECT doc_id, chunk_index, chunk_text,
                               1 - (embedding <=> %s::vector) as similarity
                        FROM document_chunks
                        WHERE vendor_id = %s AND doc_type = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (embedding_str, vendor_id, doc_type, embedding_str, k),
                    )
                else:
                    cur.execute(
                        """
                        SELECT doc_id, chunk_index, chunk_text,
                               1 - (embedding <=> %s::vector) as similarity
                        FROM document_chunks
                        WHERE vendor_id = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (embedding_str, vendor_id, embedding_str, k),
                    )

                results = []
                for row in cur.fetchall():
                    results.append(
                        {
                            "doc_id": row[0],
                            "chunk_index": row[1],
                            "chunk_text": row[2],
                            "similarity": float(row[3]),
                        }
                    )
                return results
