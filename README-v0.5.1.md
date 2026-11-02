# PiCalendar v0.5.1 — Raspberry Pi touchscreen cursor guard

This is a focused fix based on working v0.5.0. Google Sign-In, automatic
Calendar synchronization, quiet splash boot, touch swipes, local storage and
photos are unchanged.

## Why the cursor remained visible

The kiosk uses the Cage Wayland compositor. Some Pi HDMI-CEC devices advertise
pointer capability without a physical mouse, so Cage paints a hardware cursor.
CSS cursor hiding, a transparent Xcursor theme and udev cursor properties may
not suppress that separate DRM cursor plane. This is documented upstream in
Cage's issue tracker: https://github.com/cage-kiosk/cage/issues/299

## Fix

The new picalendar-cursor-guard.service starts with the dedicated kiosk, waits
for the actual startup/splash checks to finish, allows Chromium to settle, then
briefly switches VT2 and back to VT1 to reset Cage's hardware cursor plane.
When /sys/kernel/debug/dri/*/state is readable and exposes named cursor
planes, the guard verifies the cursor stays inactive over a confirmation
period and retries up to four times if it reappears.

If DRM inspection is unavailable, it attempts only one VT cycle, logs that
the result is unverified and avoids repeatedly blanking the screen.

This is a hardware-dependent compositor workaround, not a universal guarantee.
It can cause a brief black screen *after* the application has started.
No pointer/touch device is disabled, Google credentials are not modified and
the family-calendar local server isn't restarted by the guard.

## Update on an existing v0.5.0 Raspberry Pi

Download or sync branch 0.5.1 source into ~/family-calendar-pi, **preserving**
data/, backups/, .env, .venv/ and config/google-oauth-desktop.json.

From a normal Pi SSH account:

\`\`\`bash
cd ~/family-calendar-pi
bash install.sh
bash startup/install-kiosk-service.sh
sudo reboot
\`\`\`

No new Python dependencies are needed (Python standard library only).

## Diagnostics

After reboot:

\`\`\`bash
sudo systemctl status picalendar-kiosk picalendar-cursor-guard --no-pager
sudo journalctl -u picalendar-cursor-guard -b -n 80 --no-pager
\`\`\`

If the cursor is still visible, send the above logs and:

\`\`\`bash
sudo cat /proc/bus/input/devices
ls -l /sys/kernel/debug/dri/*/state 2>/dev/null || true
\`\`\`

A zero-exit guard means it completed its configured actions; only DRM plane
inspection plus observation on the display can confirm actual cursor absence.
To disable the workaround without removing the kiosk:

\`\`\`bash
sudo systemctl disable --now picalendar-cursor-guard.service
\`\`\`

The existing startup/rollback-kiosk-service.sh also removes the guard service
when restoring the pre-v0.4.2 kiosk.
