#!/usr/bin/env bash
# Restore Desktop Autologin and prior labwc startup settings if desired.
set -euo pipefail
cd "$(dirname "$0")"
BACKUP="$HOME/.config/picalendar-v0.3"
PROFILE=$(cat "$BACKUP/profile-path" 2>/dev/null || true)
if [[ -f "$BACKUP/profile.before" && -n "$PROFILE" ]]; then
  cp -p "$BACKUP/profile.before" "$PROFILE"
elif [[ -n "$PROFILE" && -f "$PROFILE" ]]; then
  sed -i '/# PICALENDAR_V03_BEGIN/,/# PICALENDAR_V03_END/d' "$PROFILE"
fi
if [[ -f "$BACKUP/labwc-autostart.before" ]]; then
  mkdir -p "$HOME/.config/labwc"
  cp -p "$BACKUP/labwc-autostart.before" "$HOME/.config/labwc/autostart"
fi
if [[ -f "$BACKUP/family-calendar.desktop.before" ]]; then
  mkdir -p "$HOME/.config/autostart"
  mv "$BACKUP/family-calendar.desktop.before" "$HOME/.config/autostart/family-calendar.desktop"
fi
if grep -Eq 'do_boot_target\(' /usr/bin/raspi-config; then
  sudo raspi-config nonint do_boot_target B2
  sudo raspi-config nonint do_autologin 2
else
  sudo raspi-config nonint do_boot_behaviour B4
fi
echo 'Desktop autologin restored. Reboot with sudo reboot.'
