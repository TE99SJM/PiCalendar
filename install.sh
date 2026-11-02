#!/bin/bash
# Run as the normal Pi desktop user, never with sudo.
set -euo pipefail
cd "$(dirname "$0")"
# Preserve the quiet v0.4.2 kiosk launchers; repair ZIP executable permissions.
if [[ "${EUID}" -eq 0 ]]; then
  echo 'Run this as your normal Raspberry Pi user, without sudo.'
  exit 1
fi
if ! python3 -m venv .venv; then
  echo 'Python venv is missing. Installing it...'
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
mkdir -p data/photos
chmod 700 data
.venv/bin/python -c 'from family_calendar.storage import init_db; init_db()'
if [[ ! -f .env ]]; then
  cp .env.example .env
fi
# A checkout can contain shell scripts without executable permissions.
# Repair launcher permissions before configuring the service.
chmod +x run.sh run-kiosk.sh startup/launch-console-kiosk.sh
APP_DIR="$(pwd)"
USER_NAME="$(id -un)"
cat > /tmp/family-calendar.service <<EOF
[Unit]
Description=Standalone Family Touch Calendar
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/bash ${APP_DIR}/run.sh
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
sudo install -m 644 /tmp/family-calendar.service /etc/systemd/system/family-calendar.service
rm -f /tmp/family-calendar.service
sudo systemctl daemon-reload
sudo systemctl enable family-calendar.service
sudo systemctl restart family-calendar.service
# If startup fails, show the real reason instead of claiming installation worked.
if ! sudo systemctl is-active --quiet family-calendar.service; then
  echo 'PiCalendar failed to start. Service diagnostics:' >&2
  sudo journalctl -u family-calendar.service -n 50 --no-pager >&2 || true
  exit 1
fi
printf '\nInstalled! Open http://127.0.0.1:8080 in the Pi browser.\n'
printf 'To start the display automatically in full-screen, run: ./install-kiosk.sh\n'
printf 'To connect Google, follow the instructions in README.md.\n'
