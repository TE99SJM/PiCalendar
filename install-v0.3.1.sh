#!/usr/bin/env bash
# Upgrade PiCalendar v0.3 without overwriting the private data/, .env, or tokens.
set -euo pipefail
cd "$(dirname "$0")"
[[ "${EUID}" -ne 0 ]] || { echo 'Run as the ordinary Pi user, not sudo.'; exit 1; }
mkdir -p backups
chmod 700 backups
if [[ -f data/calendar.sqlite3 ]]; then
  .venv/bin/python tools/backup-local.py || true
fi
bash install-v0.3.sh
bash startup/install-silent-boot.sh
sudo systemctl restart family-calendar
printf '
PiCalendar v0.3.1 installed. Reboot with sudo reboot.
'
