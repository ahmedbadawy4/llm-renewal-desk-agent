from __future__ import annotations

import csv
from pathlib import Path


def get_usage_summary(vendor_id: str) -> dict[str, float]:
    path = Path("examples/usage.csv")
    with path.open() as handle:
        reader = csv.DictReader(handle)
        rows = [row for row in reader if row["vendor_id"] == vendor_id]
    if not rows:
        return {"active_seats": 0, "allocated_seats": 0, "delta_percent": 0}
    last = rows[-1]
    allocated = float(last["allocated_seats"])
    active = float(last["active_seats"])
    delta = ((active - allocated) / allocated) * 100 if allocated else 0
    return {"active_seats": active, "allocated_seats": allocated, "delta_percent": delta}
