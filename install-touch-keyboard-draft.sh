#!/usr/bin/env bash
# Install dependencies only. Does not change the compositor or enable autostart.
set -euo pipefail
sudo apt-get update
sudo apt-get install -y wayland-utils wvkbd
printf '%s\n' 'Dependencies installed. Run the capability check inside your Wayland session:'
printf '%s\n' 'python3 tools/touch_keyboard.py --check'
printf '%s\n' 'If wvkbd-deskintl is unavailable, check wvkbd-mobintl with --binary.'
printf '%s\n' 'Packaged wvkbd may lack --auto. Do not enable autostart until all checks pass.'
