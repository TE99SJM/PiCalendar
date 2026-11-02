#!/bin/bash
# Add kiosk to Raspberry Pi OS Desktop using labwc (modern Pi OS) or XDG autostart.
set -euo pipefail
cd "$(dirname "$0")"
APP_DIR="$(pwd)"
if ! command -v chromium-browser >/dev/null && ! command -v chromium >/dev/null; then
  echo 'Installing Chromium...'
  sudo apt-get update
  sudo apt-get install -y chromium-browser || sudo apt-get install -y chromium
fi
mkdir -p "$HOME/.config/labwc" "$HOME/.config/autostart"
ENTRY="${APP_DIR}/run-kiosk.sh"
if [[ -f "$HOME/.config/labwc/autostart" ]] || command -v labwc >/dev/null 2>&1; then
  touch "$HOME/.config/labwc/autostart"
  if ! grep -Fq "$ENTRY" "$HOME/.config/labwc/autostart"; then
    printf '\n# Family Calendar touchscreen\n%s &\n' "$ENTRY" >> "$HOME/.config/labwc/autostart"
  fi
  echo 'Added kiosk startup for labwc.'
else
  cat > "$HOME/.config/autostart/family-calendar.desktop" <<EOF
[Desktop Entry]
Name=Family Calendar Kiosk
Type=Application
Exec=${ENTRY}
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  echo 'Added generic desktop kiosk startup.'
fi
printf 'Restart your Pi or log out and back in to open the calendar full-screen.\n'
