#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[[ "${EUID}" -ne 0 ]] || { echo 'Run as normal user, not sudo.' >&2; exit 1; }
for f in static/index.html static/touch-gestures.js startup/prelaunch.py run-kiosk.sh; do
  [[ -f "$f" ]] || { echo "Missing $f" >&2; exit 1; }
done
# The application lives here independently of Google or other servers.
mkdir -p data/photos backups
chmod 700 data backups
if [[ -f data/calendar.sqlite3 ]]; then
  echo 'Backing up existing local events before installing...'
  python3 tools/backup-local.py
fi
chmod +x run-kiosk.sh install-v1.2.sh startup/install-boot-branding.sh tools/backup-local.py
# The existing systemd unit is used; do NOT rewrite .env or Google OAuth files.
if systemctl list-unit-files family-calendar.service --no-legend 2>/dev/null | grep -q '^family-calendar.service'; then
  sudo systemctl restart family-calendar
  sudo systemctl is-active --quiet family-calendar || { echo 'Service failed to start; run journalctl -u family-calendar' >&2; exit 1; }
else
  echo 'First installation: starting service installer.'
  bash install.sh
fi
# Make consistent, offline SQLite snapshots once every day.
cat > /tmp/picalendar-backup.service <<EOF
[Unit]
Description=PiCalendar local SQLite backup
[Service]
Type=oneshot
User=$(id -un)
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/tools/backup-local.py
EOF
cat > /tmp/picalendar-backup.timer <<EOF
[Unit]
Description=PiCalendar daily backups
[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true
Unit=picalendar-backup.service
[Install]
WantedBy=timers.target
EOF
sudo install -m 644 /tmp/picalendar-backup.service /etc/systemd/system/picalendar-backup.service
sudo install -m 644 /tmp/picalendar-backup.timer /etc/systemd/system/picalendar-backup.timer
rm -f /tmp/picalendar-backup.service /tmp/picalendar-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now picalendar-backup.timer
printf '\nPiCalendar v1.2 installed. Existing events, photos and OAuth tokens preserved.\n'
printf 'Reboot to see the new splash. Optional early Pi logo replacement: bash startup/install-boot-branding.sh\n'
