#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
exec .venv/bin/python -m uvicorn family_calendar.main:app --host "${FAMILY_CALENDAR_HOST:-127.0.0.1}" --port "${FAMILY_CALENDAR_PORT:-8080}"
