#!/usr/bin/env bash
# PiCalendar 0.3.1: silence Raspberry Pi OS boot text and use the supplied logo.
# Backups are made before every /boot/firmware modification.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ "${EUID}" -ne 0 ]] || { echo 'Run as the ordinary Pi user; sudo is called internally.'; exit 1; }
CFG=/boot/firmware/config.txt
CMD=/boot/firmware/cmdline.txt
[[ -f "$CFG" && -f "$CMD" ]] || { echo 'Missing standard Raspberry Pi OS boot settings. No changes made.' >&2; exit 1; }
[[ -f startup/picalendar-logo.png ]] || { echo 'PiCalendar logo missing' >&2; exit 1; }
if ! command -v plymouth-set-default-theme >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y plymouth plymouth-themes
fi
STAMP=$(date +%Y%m%d-%H%M%S)
sudo cp -p "$CFG" "${CFG}.picalendar-v031-${STAMP}.bak"
sudo cp -p "$CMD" "${CMD}.picalendar-v031-${STAMP}.bak"
THEME_DIR=/usr/share/plymouth/themes/picalendar
sudo install -d "$THEME_DIR"
sudo install -m 644 startup/picalendar-logo.png startup/picalendar.plymouth startup/picalendar.script "$THEME_DIR/"
sudo python3 - "$CFG" "$CMD" <<'PY'
from pathlib import Path
import sys
cfg, cmd=(Path(x) for x in sys.argv[1:])
s=cfg.read_text()
if not any(l.strip()=='disable_splash=1' for l in s.splitlines()):
    cfg.write_text('disable_splash=1\n'+s)
words=cmd.read_text().split()
# Send kernel diagnostics to tty3, keeping tty1 ready for the graphical kiosk.
words=[w for w in words if w not in ('console=tty1','console=tty0')]
if not any(w=='console=tty3' for w in words):words.append('console=tty3')
for prefix,value in {'loglevel=':'loglevel=0','systemd.show_status=':'systemd.show_status=false',
                     'rd.systemd.show_status=':'rd.systemd.show_status=false',
                     'udev.log_level=':'udev.log_level=0','vt.global_cursor_default=':'vt.global_cursor_default=0'}.items():
    words=[w for w in words if not w.startswith(prefix)]
    words.append(value)
for w in ('quiet','splash','logo.nologo'):
    if w not in words: words.append(w)
cmd.write_text(' '.join(words)+'\n')
PY
sudo plymouth-set-default-theme picalendar
if command -v update-initramfs >/dev/null; then sudo update-initramfs -u; fi
printf 'Silent boot configured. Backup suffix: %s\n' "$STAMP"
printf 'Boot and kiosk cannot be pixel-perfect seamless during hardware initialization.\n'
