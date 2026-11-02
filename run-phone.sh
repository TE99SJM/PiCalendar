#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
exec .venv/bin/python -m uvicorn family_calendar.phone_transfer:app --host 0.0.0.0 --port 8787
