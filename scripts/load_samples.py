#!/usr/bin/env python3
"""Loads sample contract/invoice/usage data into the local object store."""
from __future__ import annotations

import argparse
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.app.core.config import Settings  # noqa: E402
from src.app.storage import object_store  # noqa: E402

SAMPLES = {
    "contract": REPO_ROOT / "examples" / "sample_contract.pdf",
    "invoices": REPO_ROOT / "examples" / "invoices.csv",
    "usage": REPO_ROOT / "examples" / "usage.csv",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Load sample data into .data/")
    parser.add_argument("--vendor-id", default="vendor_123")
    args = parser.parse_args()

    missing = [name for name, path in SAMPLES.items() if not path.exists()]
    if missing:
        raise SystemExit(f"Missing sample files: {', '.join(missing)}")

    settings = Settings()
    vendor_id = args.vendor_id
    manifest = object_store.load_manifest(vendor_id)

    for label, path in SAMPLES.items():
        data = path.read_bytes()
        stored = object_store.store_file(vendor_id, f"{label}_{path.name}", data)
        manifest[label] = str(stored)
        print(f"Stored {label} -> {stored}")

    object_store.save_manifest(vendor_id, manifest)
    print(f"Updated manifest for {vendor_id}: {manifest}")
    print(f"Object store bucket (logical): {settings.object_store_bucket}")


if __name__ == "__main__":
    main()
