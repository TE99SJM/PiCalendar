#!/usr/bin/env bash
# Launch branded startup page, show real pre-launch checks, then switch to calendar.
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then
 set -a
 # shellcheck disable=SC1091
 source .env
 set +a
fi
PORT="${FAMILY_CALENDAR_PORT:-8080}"
PRELAUNCH_PORT="${FAMILY_CALENDAR_PRELAUNCH_PORT:-8081}"
if command -v chromium-browser >/dev/null 2>&1; then BROWSER_BIN=chromium-browser
elif command -v chromium >/dev/null 2>&1; then BROWSER_BIN=chromium
else echo 'Chromium not installed' >&2; exit 1; fi
if [[ -n "${DISPLAY:-}" ]] && command -v xset >/dev/null 2>&1; then xset s off -dpms || true; fi
# The helper only binds to 127.0.0.1 and does not use Wi-Fi or Google credentials.
python3 startup/prelaunch.py --port "$PRELAUNCH_PORT" --app-port "$PORT" \
  --data-dir "${FAMILY_CALENDAR_DATA:-$PWD/data}" &
STARTUP_PID=$!
cleanup(){ kill "$STARTUP_PID" 2>/dev/null || true; wait "$STARTUP_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
for i in $(seq 1 50); do
  if (echo >/dev/tcp/127.0.0.1/"$PRELAUNCH_PORT") >/dev/null 2>&1; then break; fi
  if ! kill -0 "$STARTUP_PID" 2>/dev/null; then echo 'Startup helper exited unexpectedly' >&2; exit 1; fi
  sleep .1
done
# Enabled only by the native-keyboard supervisor. Normal launch is unchanged.
IME_FLAGS=()
if [[ "${PICALENDAR_NATIVE_KEYBOARD:-0}" == "1" ]]; then
  unset WAYLAND_DEBUG WVKBD_DEBUG
  IME_FLAGS=(--enable-wayland-ime --wayland-text-input-version=3)
fi
"$BROWSER_BIN" "${IME_FLAGS[@]}" --ozone-platform=wayland --kiosk --no-first-run --password-store=basic --disable-translate \
  --disable-session-crashed-bubble --noerrdialogs --disable-infobars \
  --disable-pinch --hide-scrollbars --no-default-browser-check \
  --start-fullscreen "http://127.0.0.1:${PRELAUNCH_PORT}/"
