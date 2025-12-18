#!/usr/bin/env bash
set -euo pipefail
VENDOR_ID=${1:-vendor_123}
API_BASE=${API_BASE:-http://localhost:8000}

curl -sS -X POST "${API_BASE}/ingest" \
  -F "vendor_id=${VENDOR_ID}" \
  -F "contract=@examples/sample_contract.pdf" \
  -F "invoices=@examples/invoices.csv" \
  -F "usage=@examples/usage.csv" | jq .
