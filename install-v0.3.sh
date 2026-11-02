#!/usr/bin/env bash
# PiCalendar v0.3: console-autologin + Cage (no Raspberry Pi desktop).
set -euo pipefail
cd "$(dirname "$0")"
[[ "$(id -u)" != 0 ]] || { echo 'Run as your regular user (no sudo before bash).'; exit 1; }
[[ -f static/index.html && -f startup/splash.html && -f startup/launch-console-kiosk.sh ]] || { echo 'Incomplete archive.' >&2; exit 1; }
[[ -f .venv/bin/python ]] || { echo 'Install the app first with bash install.sh'; exit 1; }
command -v raspi-config >/dev/null || { echo 'This installer is for Raspberry Pi OS (raspi-config required).' >&2; exit 1; }
[[ -e /dev/tty1 ]] || { echo 'Expected /dev/tty1 console missing; no changes made.' >&2; exit 1; }
mkdir -p "$HOME/.config/picalendar-v0.3" backups
chmod 700 backups
chmod +x run-kiosk.sh startup/launch-console-kiosk.sh install-v0.3.sh rollback-v0.3.sh
# Install dependencies and validate BEFORE changing boot behavior.
if ! command -v cage >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y cage
fi
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
  sudo apt-get install -y chromium || sudo apt-get install -y chromium-browser
fi
sudo systemctl is-active --quiet family-calendar || sudo systemctl restart family-calendar
sudo systemctl is-active --quiet family-calendar || { echo 'Calendar server is not running; no boot changes made.' >&2; exit 1; }
# Save old app startup configuration and remove desktop autostart to avoid a second browser.
BACKUP="$HOME/.config/picalendar-v0.3"
if [[ -f "$HOME/.config/labwc/autostart" ]]; then
  [[ -e "$BACKUP/labwc-autostart.before" ]] || cp -p "$HOME/.config/labwc/autostart" "$BACKUP/labwc-autostart.before"
  sed -i '\|/family-calendar-pi/run-kiosk.sh|d' "$HOME/.config/labwc/autostart"
fi
if [[ -f "$HOME/.config/autostart/family-calendar.desktop" ]]; then
  mv -n "$HOME/.config/autostart/family-calendar.desktop" "$BACKUP/family-calendar.desktop.before"
fi
# Bash login executes the first existing file among these in order.
PROFILE="$HOME/.profile"
for f in "$HOME/.bash_profile" "$HOME/.bash_login" "$HOME/.profile"; do
  if [[ -f "$f" ]]; then PROFILE="$f"; break; fi
done
printf '%s\n' "$PROFILE" > "$BACKUP/profile-path"
[[ -e "$BACKUP/profile.before" ]] || cp -p "$PROFILE" "$BACKUP/profile.before" 2>/dev/null || true
if ! grep -Fq '# PICALENDAR_V03_BEGIN' "$PROFILE" 2>/dev/null; then
cat >> "$PROFILE" <<'BLOCK'

# PICALENDAR_V03_BEGIN
# Only the local auto-login console launches the graphical kiosk, never SSH.
if [[ -z "${SSH_TTY:-}" && "$(tty 2>/dev/null)" == '/dev/tty1' && -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
  exec "$HOME/family-calendar-pi/startup/launch-console-kiosk.sh"
fi
# PICALENDAR_V03_END
BLOCK
fi
# Raspberry Pi OS releases have slightly different non-interactive raspi-config interfaces.
if grep -Eq 'do_boot_target\(' /usr/bin/raspi-config; then
  sudo raspi-config nonint do_boot_target B1
  sudo raspi-config nonint do_autologin 1
elif grep -q 'do_boot_behaviour' /usr/bin/raspi-config; then
  sudo raspi-config nonint do_boot_behaviour B2
else
  echo 'Unable to select console autologin automatically. Run sudo raspi-config and enable Console Autologin.' >&2
  exit 1
fi
# The previously installed PiCalendar Plymouth image was full resolution.
# Updating the existing theme with a 1/3-size image makes it centered and smaller.
if [[ -d /usr/share/plymouth/themes/picalendar ]]; then
  sudo install -m 644 startup/picalendar-logo.png /usr/share/plymouth/themes/picalendar/picalendar-logo.png
  if command -v update-initramfs >/dev/null 2>&1; then sudo update-initramfs -u; fi
else
  echo 'Optional early Plymouth logo is not installed; run bash startup/install-boot-branding.sh after setup if desired.'
fi
printf '\nPiCalendar v0.3 configured. Run sudo reboot when ready.\n'
printf 'Your data/, .env, Google OAuth tokens, and backups/ were not changed.\n'
printf 'To undo, connect by SSH and run bash rollback-v0.3.sh.\n'
