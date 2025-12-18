from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict


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


def store_file(vendor_id: str, filename: str, data: bytes) -> Path:
    base = vendor_dir(vendor_id)
    target = base / filename
    target.write_bytes(data)
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
