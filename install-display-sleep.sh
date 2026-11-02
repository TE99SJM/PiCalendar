#!/bin/bash
# Run as the same normal desktop user that installed PiCalendar.
set -euo pipefail
cd "$(dirname "$0")"
[[ $EUID -ne 0 ]] || { echo 'Run without sudo, as the kiosk user.'; exit 1; }
APP_DIR="$(pwd)"
[[ "$APP_DIR" =~ ^[a-zA-Z0-9_./-]+$ ]] || { echo 'Install in a path without spaces or special characters.'; exit 1; }
[[ -x .venv/bin/python ]] || { echo 'Run bash install.sh first.'; exit 1; }
if [[ -f .env ]]; then set -a; source .env; set +a; fi
PANEL=$(.venv/bin/python -c 'from family_calendar.display import backlight; p=backlight.device(); print(p.name if p else "")')
[[ -n "$PANEL" ]] || { echo 'Select one valid FAMILY_CALENDAR_BACKLIGHT_DEVICE in .env; no hardware was changed.'; exit 1; }
USER_NAME="$(id -un)"
sudo groupadd -f picalendar-backlight
sudo usermod -a -G picalendar-backlight "$USER_NAME"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
# Scope write access to the selected backlight, never to touch, USB or GPIO.
for ATTR in brightness bl_power; do
  if [[ -f "/sys/class/backlight/$PANEL/$ATTR" ]]; then
    printf 'SUBSYSTEM=="backlight", KERNEL=="%s", RUN+="/bin/chgrp picalendar-backlight /sys/class/backlight/%%k/%s", RUN+="/bin/chmod g+w /sys/class/backlight/%%k/%s"\n' "$PANEL" "$ATTR" "$ATTR" >> "$TMP_DIR/rules"
    sudo chgrp picalendar-backlight "/sys/class/backlight/$PANEL/$ATTR"
    sudo chmod g+w "/sys/class/backlight/$PANEL/$ATTR"
  fi
done
sudo install -m 644 "$TMP_DIR/rules" /etc/udev/rules.d/70-picalendar-backlight.rules
sudo udevadm control --reload-rules
cat > "$TMP_DIR/service" <<EOF
[Unit]
Description=PiCalendar independent backlight recovery guardian
After=local-fs.target

[Service]
Type=simple
User=${USER_NAME}
SupplementaryGroups=picalendar-backlight
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/bash ${APP_DIR}/run-display-guardian.sh
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
EOF
sudo install -m 644 "$TMP_DIR/service" /etc/systemd/system/picalendar-display-guardian.service
sudo systemctl daemon-reload
sudo systemctl enable --now picalendar-display-guardian.service
sudo systemctl restart picalendar-display-guardian.service
sudo systemctl restart family-calendar.service
sudo systemctl is-active --quiet picalendar-display-guardian.service
printf 'Backlight configured: %s. Reload Chromium. See README-v0.5.4.md for timed recovery tests.\n' "$PANEL"
