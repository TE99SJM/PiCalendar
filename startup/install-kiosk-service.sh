#!/usr/bin/env bash
# PiCalendar v0.4.2: replace tty1 auto-login with a quiet systemd Cage session.
# Run over SSH as the normal Pi account. Reboot only after installer finishes.
set -euo pipefail
[[ "$EUID" -ne 0 ]] || { echo "Run as your regular user (not sudo)." >&2; exit 1; }
APP="$(cd "$(dirname "$0")/.." && pwd)"
[[ "$APP" == "$HOME/family-calendar-pi" ]] || { echo "Expected $HOME/family-calendar-pi, got $APP" >&2; exit 1; }
[[ -f "$APP/static/index.html" && -f "$APP/startup/splash.html" ]] || { echo "PiCalendar files missing." >&2; exit 1; }
for cmd in cage chvt python3 systemctl; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }; done
[[ -c /dev/tty1 ]] || { echo "/dev/tty1 missing." >&2; exit 1; }
sudo systemctl is-active --quiet family-calendar || { echo "Start family-calendar first." >&2; exit 1; }

BACKUP="$HOME/.config/picalendar-kiosk-v042"
mkdir -p "$BACKUP"
chmod 700 "$BACKUP"
[[ -f "$BACKUP/default-target.before" ]] || systemctl get-default > "$BACKUP/default-target.before"
[[ -f "$BACKUP/getty-enabled.before" ]] || { systemctl is-enabled getty@tty1.service > "$BACKUP/getty-enabled.before" 2>/dev/null || true; }
for target in /etc/pam.d/picalendar /etc/systemd/system/picalendar-kiosk.service; do
  old="$BACKUP/$(basename "$target").before"
  if [[ -f "$target" && ! -f "$old" ]]; then sudo cp -p "$target" "$old"; fi
done
for name in .bash_profile .bash_login .profile; do
  [[ -f "$HOME/$name" && ! -e "$BACKUP/$name.before" ]] && cp -p "$HOME/$name" "$BACKUP/$name.before" || true
done

# Create a local transparent Xcursor theme without modifying system-wide icons.
python3 - "$HOME" <<'PY'
from pathlib import Path
import struct, sys
home=Path(sys.argv[1])
root=home/'.local/share/icons/PiCalendarInvisible'
cursors=root/'cursors'
cursors.mkdir(parents=True, exist_ok=True)
(root/'index.theme').write_text('[Icon Theme]\nName=PiCalendarInvisible\nComment=Invisible touchscreen kiosk pointer\n')
t=0xfffd0002
data=(struct.pack('<4I',0x72756358,16,65536,1)
      +struct.pack('<3I',t,24,28)
      +struct.pack('<9I',36,t,24,1,1,1,0,0,0)
      +struct.pack('<I',0))
(cursors/'left_ptr').write_bytes(data)
for name in ('default','pointer','hand1','hand2','text','xterm','watch','crosshair',
             'move','grabbing','grab','not-allowed','wait','progress','arrow','ibeam'):
    path=cursors/name
    if path.is_file() or path.is_symlink(): path.unlink()
    path.symlink_to('left_ptr')
PY

# Eliminate the old shell-login kiosk hook, which was flashing GNU/Linux text.
python3 - "$HOME" <<'PY'
from pathlib import Path
import re, sys
home=Path(sys.argv[1])
pattern=re.compile(r'\n?# PICALENDAR_V03_BEGIN[^\n]*\n.*?# PICALENDAR_V03_END[^\n]*\n?',re.S)
for name in ('.bash_profile','.bash_login','.profile'):
    p=home/name
    if p.is_file():
        old=p.read_text()
        new=pattern.sub('\n',old)
        if new != old: p.write_text(new)
PY

PAM_TMP="$(mktemp)"
UNIT_TMP="$(mktemp)"
trap 'rm -f "$PAM_TMP" "$UNIT_TMP"' EXIT
cat > "$PAM_TMP" <<'PAM'
# Cage systemd login session, based on the upstream Cage documentation.
auth       required     pam_unix.so nullok
account    required     pam_unix.so
session    required     pam_unix.so
session    required     pam_systemd.so
PAM

USER_NAME="$(id -un)"
CAGE_BIN="$(command -v cage)"
CHVT_BIN="$(command -v chvt)"
cat > "$UNIT_TMP" <<UNIT
[Unit]
Description=PiCalendar quiet touchscreen kiosk
Wants=family-calendar.service dbus.socket systemd-logind.service
After=systemd-user-sessions.service plymouth-quit-wait.service family-calendar.service dbus.socket systemd-logind.service getty@tty1.service
Conflicts=getty@tty1.service
ConditionPathExists=/dev/tty0

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$APP
PAMName=picalendar
UtmpIdentifier=tty1
UtmpMode=user
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
TTYVTDisallocate=yes
StandardInput=tty-fail
StandardOutput=journal
StandardError=journal
Environment=XDG_SESSION_TYPE=wayland
Environment=XDG_CURRENT_DESKTOP=cage
Environment=MOZ_ENABLE_WAYLAND=1
Environment=XCURSOR_THEME=PiCalendarInvisible
Environment=XCURSOR_PATH=$HOME/.local/share/icons:/usr/share/icons
Environment=XCURSOR_SIZE=24
ExecStart=$CAGE_BIN -- $APP/run-kiosk.sh
ExecStartPost=+$CHVT_BIN 1
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT
sudo install -m 644 "$PAM_TMP" /etc/pam.d/picalendar
sudo install -m 644 "$UNIT_TMP" /etc/systemd/system/picalendar-kiosk.service
chmod u+x "$APP/run.sh" "$APP/run-kiosk.sh"
sudo systemctl daemon-reload

# The desktop remains untouched; stop the console getty only on the next boot.
sudo systemctl disable getty@tty1.service || true
sudo systemctl set-default multi-user.target
sudo systemctl enable picalendar-kiosk.service

echo "PiCalendar v0.4.2 quiet kiosk configured. Reboot when ready."
echo "SSH remains enabled. Rollback: bash $APP/startup/rollback-kiosk-service.sh"
