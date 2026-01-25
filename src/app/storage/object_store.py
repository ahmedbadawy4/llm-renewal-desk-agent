from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict

from ..core.encryption import encrypt_data
from . import pdf_parser
from .indexing import index_document

logger = logging.getLogger(__name__)


def _resolve_default_dir() -> str:
    try:
        from ..core.config import Settings
    except Exception:  # pragma: no cover - settings may not be importable early
        return ".data"
    try:
        return Settings().data_dir
    except Exception:
        return ".data"


DATA_ROOT = Path(os.environ.get("DATA_DIR", _resolve_default_dir()))


def vendor_dir(vendor_id: str) -> Path:
    path = DATA_ROOT / vendor_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_file(vendor_id: str, filename: str, data: bytes, doc_type: str | None = None, encrypt: bool = True) -> Path:
    base = vendor_dir(vendor_id)
    target = base / filename

    if encrypt and filename.lower().endswith((".txt", ".csv")):
        try:
            data_str = data.decode("utf-8", errors="ignore")
            encrypted = encrypt_data(data_str)
            target.write_text(encrypted, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Encryption failed, storing unencrypted: {e}")
            target.write_bytes(data)
    else:
        target.write_bytes(data)

    if filename.lower().endswith(".pdf"):
        try:
            parse_result = pdf_parser.parse_pdf(target)
            pdf_parser.save_parsed_data(base, target, parse_result)
        except Exception as e:
            logger.warning(f"PDF parsing failed for {filename}: {e}")

    if doc_type:
        try:
            index_document(vendor_id, filename, doc_type, target)
        except Exception as e:
            logger.warning(f"Document indexing failed for {filename}: {e}")

    return target


def _manifest_path(vendor_id: str) -> Path:
    return vendor_dir(vendor_id) / "manifest.json"


def load_manifest(vendor_id: str) -> Dict[str, str]:
    path = _manifest_path(vendor_id)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_manifest(vendor_id: str, manifest: Dict[str, str]) -> Path:
    path = _manifest_path(vendor_id)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return path
