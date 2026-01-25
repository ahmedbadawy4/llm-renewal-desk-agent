from __future__ import annotations

import logging
from pathlib import Path

from ..core.config import Settings, get_settings
from ..rag.chunking import chunk_text
from ..rag.embeddings import generate_embeddings
from ..storage import pdf_parser
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


def index_document(
    vendor_id: str,
    doc_id: str,
    doc_type: str,
    file_path: Path,
    settings: Settings | None = None,
) -> None:
    cfg = settings or get_settings()
    vector_store = VectorStore(cfg)

    if not vector_store.enabled:
        logger.warning("Vector store not enabled, skipping indexing")
        return

    try:
        if file_path.suffix.lower() == ".pdf":
            parse_result = pdf_parser.parse_pdf(file_path)
            text = parse_result.full_text
        else:
            text = file_path.read_text(encoding="utf-8", errors="ignore")

        if not text.strip():
            logger.warning(f"Empty document: {doc_id}")
            return

        chunks = chunk_text(text, chunk_size=800, overlap=80)

        if not chunks:
            logger.warning(f"No chunks extracted from: {doc_id}")
            return

        embeddings = generate_embeddings(chunks)

        chunk_data = [(i, chunk, embedding) for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))]

        vector_store.upsert(vendor_id, doc_id, doc_type, chunk_data)
        logger.info(f"Indexed {len(chunks)} chunks for {doc_id}")

    except Exception as e:
        logger.error(f"Failed to index document {doc_id}: {e}")
