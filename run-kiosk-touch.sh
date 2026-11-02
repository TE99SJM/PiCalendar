#!/usr/bin/env bash
# Opt-in launcher: retains the existing prelaunch page and Chromium lifecycle.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 tools/touch_keyboard.py -- bash ./run-kiosk.sh
