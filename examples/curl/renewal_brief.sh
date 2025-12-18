#!/usr/bin/env bash
set -euo pipefail
VENDOR_ID=${1:-vendor_123}
API_BASE=${API_BASE:-http://localhost:8000}

curl -sS -X POST "${API_BASE}/renewal-brief?vendor_id=${VENDOR_ID}" \
  -H 'Content-Type: application/json' \
  -d '{"refresh": false}' | jq .
