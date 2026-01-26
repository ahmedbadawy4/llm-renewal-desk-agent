from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from ..core.config import Settings
from ..storage import pdf_parser
from ..storage.indexing import index_document

logger = logging.getLogger(__name__)


async def process_document_async(
    vendor_id: str,
    filename: str,
    file_path: Path,
    doc_type: str,
    settings: Settings,
) -> Dict[str, str]:
    try:
        if not file_path.exists():
            error_msg = f"File not found: {file_path}. It may have been corrupted during ingestion. Please re-ingest."
            logger.error(error_msg)
            return {
                "status": "failed",
                "vendor_id": vendor_id,
                "filename": filename,
                "doc_type": doc_type,
                "error": error_msg,
            }
        
        if file_path.suffix.lower() == ".pdf":
            parse_result = pdf_parser.parse_pdf(file_path)
            vendor_dir = file_path.parent
            pdf_parser.save_parsed_data(vendor_dir, file_path, parse_result)

        index_document(vendor_id, filename, doc_type, file_path, settings)

        return {
            "status": "completed",
            "vendor_id": vendor_id,
            "filename": filename,
            "doc_type": doc_type,
        }
    except Exception as e:
        logger.error(f"Document processing failed for {filename}: {e}")
        return {
            "status": "failed",
            "vendor_id": vendor_id,
            "filename": filename,
            "doc_type": doc_type,
            "error": str(e),
        }
