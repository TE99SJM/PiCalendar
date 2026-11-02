# PiCalendar 0.5.4 - True Sleep Mode

Baseline: branch 0.5.2 at 9ae5eaa5fce4d2ff5ac03ee64a6fe70094a20518.
No published release was available; its VERSION still said 0.5.0.
Only 0.5.4 is targeted. No existing branch is changed or merged.

## Design

app.js calendar code and double-tap recognition stay unchanged. true-sleep.js
loads afterward and replaces only its sleep/wake policy bindings. The overlay
is an input shield during hardware sleep, NOT a CSS-only sleep fallback.
Unsupported displays stay awake with a warning.

The backend discovers Linux backlights, journals the current brightness, writes
brightness=0 and, where present, bl_power=4. Wake restores the exact brightness
and bl_power=0. No Pi suspend, DPMS, HDMI shutdown, USB disconnect or GPIO power
cuts. Touch, Pi, Google sync/login, kiosk startup and hidden cursor stay running.

A separate systemd guardian restores brightness after a 30-second lease expires.
The browser renews every 8 seconds; missing guardian heartbeat refuses sleep.
A persistent journal/lock supports application restarts and partial failures.
Failed restore retries every second. API requests time out after 5 seconds;
wake retries once. Browser reload requests wake. Clock jumps outside the lease
window trigger recovery. Recovery requires a working OS, driver and writable
hardware. The guardian attempts wake on shutdown and restarts after crashes.

## Hardware

- Official Pi DSI and compatible DSI/PWM panels: need brightness/max_brightness
  in /sys/class/backlight. One non-ddcci device is auto-selected. Names and
  brightness ranges vary by driver/port; neither is hard-coded.
- Multiple panels: explicitly select a device basename in .env.
- HDMI: requires a compatible kernel/vendor independent backlight interface.
  ddcci devices require explicit selection. This release does NOT install
  out-of-tree drivers or send monitor-power commands. DDC brightness zero
  may still glow; that alone does not establish true-sleep compatibility.
- No independent hardware control: safe refusal, not a black-screen substitute.

Sysfs readback validates driver settings, NOT optical darkness or touch input.
Verify both on your hardware; reject drivers that disconnect touch or retain
backlight glow. No physical Pi/display was available for development. These
are interface-based conditions, not hardware-tested panel claims.
Use the manufacturer's Pi 5-compatible driver/wiring. Do not blindly add legacy
overlays to /boot/firmware/config.txt. This release changes no boot configuration.
Linux ABI: https://www.kernel.org/doc/Documentation/ABI/stable/sysfs-class-backlight

## Install

Use the normal kiosk user, not root. Preserve .env, data and Google credentials;
commit/stash tracked local edits. Existing checkout:

```bash
cd ~/PiCalendar
git fetch origin
git switch 0.5.4 || git switch --track origin/0.5.4
git pull --ff-only origin 0.5.4
bash install.sh
ls -l /sys/class/backlight
.venv/bin/python -m family_calendar.display
```

Fresh install: clone with `git clone --branch 0.5.4 https://github.com/TE99SJM/PiCalendar.git`,
then `cd PiCalendar` and `bash install.sh`.
If ambiguous or using eligible HDMI/ddcci hardware, edit .env to set
FAMILY_CALENDAR_BACKLIGHT_DEVICE to the actual listed basename (for example,
4-0045 ONLY if that is your device). Then:

```bash
bash install-display-sleep.sh
sudo systemctl status picalendar-display-guardian.service --no-pager
curl -s http://127.0.0.1:8080/api/display/status
```

The installer grants group writes ONLY to selected brightness/bl_power nodes,
installs a device-specific udev rule, and restarts normal-user services. No root
browser, world-writable sysfs or passwordless sudo. Use a path without spaces
or special characters. Both services must share .env/state-directory settings.
Reload Chromium; manually launched apps need a new login for group membership.
Existing kiosk launchers stay unchanged. For a NEW kiosk, use the existing
README.md procedure and `bash install-kiosk.sh`.

## Acceptance and recovery

Keep SSH available. Status available/guardian must be true. Record brightness,
press Sleep, verify NO physical glow in a dark room, double tap at several
locations and confirm original brightness. Repeat at different levels. Check
Google sync and all calendar/chores/shopping/meals/photos functions.

Test lease recovery WITHOUT browser renewal:

```bash
curl -s -X POST http://127.0.0.1:8080/api/display/sleep
# Should restore after approximately 30 seconds.
```

Also stop ONLY family-calendar.service while sleeping; guardian recovery should
follow lease expiry. Restart the app and repeat after reboot. Do not stop the
guardian during this test. Update configuration if driver/port changes rename
the device. Manual wake, as the same kiosk user:

```bash
cd ~/PiCalendar
set -a; source .env; set +a
.venv/bin/python -m family_calendar.display --wake
sudo journalctl -u picalendar-display-guardian.service -n 50 --no-pager
```

Repair failed permissions/drivers first. Last-resort sudo writes must target
the SPECIFIC device: positive brightness and bl_power=0, never wildcard writes.

## Tests and limits

```bash
.venv/bin/python -m unittest discover -s tests -p test_display.py -v
node --test tests/true-sleep.test.cjs
# Full inherited suites, with their dependencies installed:
.venv/bin/python -m pytest tests
node --test tests/touch-gestures.test.cjs tests/true-sleep.test.cjs
```

Eight grouped Python tests and six Node policy tests passed, plus shell/JS syntax
checks. An earlier expanded 17-test Python suite also passed. The full inherited
suite and physical hardware were NOT run. Double-tap code stays unchanged;
physical touch/darkness requires acceptance testing. VERSION and display/status
report 0.5.4; the inherited generic /api/status literal remains 0.5.0 to avoid
unrelated server rewrites.

## Rollback

Wake and verify the panel is lit FIRST:

```bash
sudo systemctl disable --now picalendar-display-guardian.service
sudo rm -f /etc/udev/rules.d/70-picalendar-backlight.rules
sudo udevadm control --reload-rules
git switch 0.5.2
bash install.sh
```

Current sysfs group permissions persist until reboot. Remote branches unchanged.
