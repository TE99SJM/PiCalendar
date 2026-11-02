#!/usr/bin/env bash
set -euo pipefail
[[ "$EUID" -ne 0 ]] || { echo "Run as regular user." >&2; exit 1; }
BACKUP="$HOME/.config/picalendar-kiosk-v042"
[[ -d "$BACKUP" ]] || { echo "Missing v0.4.2 backup." >&2; exit 1; }
sudo systemctl disable --now picalendar-cursor-guard.service || true
sudo rm -f /etc/systemd/system/picalendar-cursor-guard.service
sudo systemctl disable --now picalendar-kiosk.service || true
for name in .bash_profile .bash_login .profile; do
  [[ -f "$BACKUP/$name.before" ]] && cp -p "$BACKUP/$name.before" "$HOME/$name"
done
for target in /etc/pam.d/picalendar /etc/systemd/system/picalendar-kiosk.service /etc/udev/rules.d/99-picalendar-cursor.rules; do
  source="$BACKUP/$(basename "$target").before"
  if [[ -f "$source" ]]; then sudo cp -p "$source" "$target"; else sudo rm -f "$target"; fi
done
sudo systemctl daemon-reload
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input
sudo systemctl enable getty@tty1.service || true
if [[ -f "$BACKUP/default-target.before" ]]; then
  sudo systemctl set-default "$(cat "$BACKUP/default-target.before")"
fi
echo "Previous kiosk startup restored; reboot when ready."
