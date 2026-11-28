#!/usr/bin/env bash
set -euo pipefail

app_dir="$(cd "$(dirname "$0")/.." && pwd -P)"
account="$(id -un)"

if [[ "$EUID" == 0 ]]; then
  echo 'Run as the regular kiosk user. The installer calls sudo where needed.' >&2
  exit 1
fi
if [[ ! "$app_dir" =~ ^/[a-zA-Z0-9_./-]+$ || ! "$account" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]]; then
  echo 'Use a checkout path and username without spaces or special characters.' >&2
  exit 1
fi
if [[ ! -d /run/systemd/system || ! -c /dev/tty1 ]]; then
  echo 'A running systemd Linux system with a local tty1 console is required.' >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y python3-venv chromium cage dbus-user-session libpam-systemd kbd curl
cd "$app_dir"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
install -d -m 700 data
if [[ ! -e .env ]]; then
  install -m 600 .env.example .env
fi

unit_dir="$(mktemp -d)"
trap 'rm -rf "$unit_dir"' EXIT

cat > "$unit_dir/picalendar-linux.service" <<UNIT
[Unit]
Description=PiCalendar local server
After=network.target

[Service]
User=$account
WorkingDirectory=$app_dir
ExecStart=/usr/bin/bash $app_dir/linux-kiosk/run-local.sh
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

cat > "$unit_dir/picalendar-linux-kiosk.service" <<UNIT
[Unit]
Description=PiCalendar fullscreen touchscreen kiosk
Wants=picalendar-linux.service systemd-logind.service dbus.socket
After=picalendar-linux.service systemd-logind.service dbus.socket systemd-user-sessions.service getty@tty1.service
Conflicts=getty@tty1.service display-manager.service
ConditionPathExists=/dev/tty0

[Service]
User=$account
WorkingDirectory=$app_dir
PAMName=login
TTYPath=/dev/tty1
UtmpIdentifier=tty1
UtmpMode=user
StandardInput=tty-fail
StandardOutput=journal
StandardError=journal
TTYReset=yes
TTYVHangup=yes
TTYVTDisallocate=yes
Environment=XDG_SESSION_TYPE=wayland
Environment=XDG_CURRENT_DESKTOP=cage
ExecStart=/usr/bin/cage -- /usr/bin/bash $app_dir/run-kiosk.sh
ExecStartPost=+/usr/bin/chvt 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

sudo install -m 644 "$unit_dir/"*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable picalendar-linux.service picalendar-linux-kiosk.service
sudo systemctl restart picalendar-linux.service
echo 'PiCalendar is configured. Reboot to start the fullscreen kiosk.'
