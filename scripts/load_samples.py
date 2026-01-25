#!/usr/bin/env python3
"""Loads sample contract/invoice/usage data into the local object store."""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.app.core.config import Settings  # noqa: E402
from src.app.storage import object_store  # noqa: E402
from src.app.workers.job_queue import get_job_queue  # noqa: E402

SAMPLES = {
    "contract": REPO_ROOT / "examples" / "sample_contract.pdf",
    "invoices": REPO_ROOT / "examples" / "invoices.csv",
    "usage": REPO_ROOT / "examples" / "usage.csv",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Load sample data into .data/")
    parser.add_argument("--vendor-id", default="vendor_123")
    parser.add_argument("--wait", action="store_true", help="Wait for jobs to complete")
    args = parser.parse_args()

    missing = [name for name, path in SAMPLES.items() if not path.exists()]
    if missing:
        raise SystemExit(f"Missing sample files: {', '.join(missing)}")

    settings = Settings()
    vendor_id = args.vendor_id
    manifest = object_store.load_manifest(vendor_id)
    
    job_ids = []
    job_queue = get_job_queue(settings)

    for label, path in SAMPLES.items():
        data = path.read_bytes()
        stored = object_store.store_file(vendor_id, f"{label}_{path.name}", data)
        manifest[label] = str(stored)
        print(f"Stored {label} -> {stored}")

        job_id = job_queue.submit(vendor_id, f"{label}_{path.name}", stored, label)
        job_ids.append(job_id)
        print(f"Submitted job {job_id} for {label}")

    object_store.save_manifest(vendor_id, manifest)
    print(f"Updated manifest for {vendor_id}: {manifest}")
    print(f"Object store bucket (logical): {settings.object_store_bucket}")
    print(f"Job IDs: {job_ids}")
    print("\nNote: Jobs are processing asynchronously. Use the /jobs API to check status.")

    if args.wait:
        print("Waiting for jobs to complete...")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(_wait_for_jobs(job_queue, job_ids))
            else:
                loop.run_until_complete(_wait_for_jobs(job_queue, job_ids))
        except RuntimeError:
            asyncio.run(_wait_for_jobs(job_queue, job_ids))


async def _wait_for_jobs(job_queue, job_ids, max_wait=60):
    start = time.time()
    while time.time() - start < max_wait:
        all_done = True
        for job_id in job_ids:
            job = job_queue.get_job(job_id)
            if not job:
                continue
            if job.status.value in ["pending", "processing"]:
                all_done = False
                break
            elif job.status.value == "failed":
                print(f"Job {job_id} failed: {job.error}")
        if all_done:
            print("All jobs completed!")
            return
        await asyncio.sleep(1)
    print("Timeout waiting for jobs to complete")


if __name__ == "__main__":
    main()
