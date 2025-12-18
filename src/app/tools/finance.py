from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean


def get_spend_summary(vendor_id: str) -> dict[str, float]:
    path = Path("examples/invoices.csv")
    with path.open() as handle:
        reader = csv.DictReader(handle)
        rows = [row for row in reader if row["vendor_id"] == vendor_id]
    total = sum(float(row["amount_usd"]) for row in rows)
    avg_seats = mean(float(row["seats"]) for row in rows) if rows else 0
    return {"annual_spend_usd": total, "avg_seats": avg_seats}
