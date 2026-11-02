#!/usr/bin/env bash
# Console autologin starts ONLY Cage + Chromium, not the Raspberry Pi desktop.
set -uo pipefail
APP="$HOME/family-calendar-pi"
if [[ -f "$HOME/.config/picalendar-v0.3/disable-kiosk" ]]; then
  printf 'PiCalendar kiosk disabled for troubleshooting.\n'
  exit 0
fi
if [[ ! -x "$APP/run-kiosk.sh" ]]; then
  printf 'PiCalendar launcher missing: %s/run-kiosk.sh\n' "$APP" >&2
  exit 1
fi
# Cover the auto-login terminal before taking over the display. SSH stays intact.
if [[ "$(tty 2>/dev/null)" == '/dev/tty1' ]]; then
  setterm --foreground black --background black --cursor off --clear all </dev/tty1 >/dev/tty1 2>/dev/null || true
fi
mkdir -p "$HOME/.local/state/picalendar"
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=cage
export MOZ_ENABLE_WAYLAND=1
# When the browser is closed/crashes, restart without ever opening the desktop.
while :; do
  cage -- "$APP/run-kiosk.sh" >>"$HOME/.local/state/picalendar/kiosk.log" 2>&1 || true
  sleep 2
done
