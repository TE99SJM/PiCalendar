#!/usr/bin/env bash
# OPTIONAL: change early Linux boot logo + hide default Raspberry Pi firmware splash.
# Raspberry Pi firmware display comes up before any user-space program; the actual
# dynamic progress bar remains in the desktop's pre-launch checker.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$EUID" == 0 ]]; then echo 'Run as regular user; script invokes sudo.'; exit 1; fi
if ! command -v plymouth-set-default-theme >/dev/null 2>&1; then
  echo 'Installing Plymouth splash support. Internet access may be needed.'
  sudo apt-get update
  sudo apt-get install -y plymouth plymouth-themes
fi
THEME_DIR=/usr/share/plymouth/themes/picalendar
sudo install -d "$THEME_DIR"
sudo install -m 644 startup/picalendar-logo.png startup/picalendar.plymouth startup/picalendar.script "$THEME_DIR/"
# Changing kernel boot configuration is always backed up and deliberately opt-in.
CFG=/boot/firmware/config.txt
CMD=/boot/firmware/cmdline.txt
if [[ ! -f "$CFG" || ! -f "$CMD" ]]; then
  echo 'Nonstandard Raspberry Pi boot partition; leaving boot settings untouched.'
  echo 'Plymouth theme files installed. Configure firmware manually if needed.'
  exit 1
fi
STAMP=$(date +%Y%m%d-%H%M%S)
sudo cp -p "$CFG" "${CFG}.picalendar-backup-${STAMP}"
sudo cp -p "$CMD" "${CMD}.picalendar-backup-${STAMP}"
# Set disable_splash=1 in the global configuration, not inside a [pi4] block.
sudo python3 - "$CFG" "$CMD" <<'PY'
from pathlib import Path
import sys
conf, cmd = [Path(x) for x in sys.argv[1:]]
s=conf.read_text()
# prepend in global scope so later model sections do not shadow it
if not any(line.strip()=='disable_splash=1' for line in s.splitlines()):
    s='disable_splash=1\n'+s
    conf.write_text(s)
line=cmd.read_text().strip()
words=line.split()
for word in ('quiet','splash','logo.nologo','vt.global_cursor_default=0'):
    if word not in words: words.append(word)
cmd.write_text(' '.join(words)+'\n')
PY
sudo plymouth-set-default-theme picalendar
# Some Pi installations do not build an initramfs; warn rather than breaking boot.
if command -v update-initramfs >/dev/null 2>&1; then sudo update-initramfs -u; fi
printf '\nEarly boot branding enabled. Previous firmware files saved as *.picalendar-backup-%s\n' "$STAMP"
printf 'PiCalendar will show the REAL action-based progress bar later, during desktop app startup.\n'
printf 'A firmware/HDMI black screen before Linux initializes cannot display a software progress bar.\n'
