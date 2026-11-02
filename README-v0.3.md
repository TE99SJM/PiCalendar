# PiCalendar v0.3 — no desktop, centered boot icon, actual readiness loading bar

This is the **complete standalone PiCalendar** source code, with v1.2's calendar features, offline SQLite data and touchscreen gestures.

## Changes from the previous package

- **No Raspberry Pi desktop** is launched. Raspberry Pi OS auto-logs into a text console on tty1, and `cage` launches only Chromium in fullscreen kiosk mode.
- User-supplied logo remains unchanged in `static/logo.png`. A proportional **341 × 341** copy of the original 1024 × 1024 image is provided for the early Plymouth boot logo. It is centered, with no bar or text baked in.
- PiCalendar's graphical splash uses a logo display **one-third the original size**, centered both horizontally and vertically, black background, with a separate bottom progress bar.
- The progress bar uses **real local startup checks** (files, SQLite, API server, events and lists) to reach 95%, then waits until the actual dashboard JavaScript has fetched and rendered its data before reaching 100% and revealing the UI.
- No on-screen status messages, desktop bar, terminal window or ordinary scrollbar.
- Offline saved events, chores, meals, groceries and photos remain on the Pi and work without Internet. Google two-way sync still requires Internet when available.

## Update on your Raspberry Pi (from v1.2)

Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\PiCalendar-v0.3.zip" samuel@192.168.50.211:~/
ssh samuel@192.168.50.211
```

Then on the Pi SSH session:

```bash
cd ~/family-calendar-pi
# Back up your existing project source and private data before upgrading
mkdir -p ~/picalendar-backups
tar -czf ~/picalendar-backups/pre-v0.3-$(date +%Y%m%d-%H%M%S).tgz -C ~ family-calendar-pi
unzip -o ~/PiCalendar-v0.3.zip -d ~/family-calendar-pi
bash install-v0.3.sh
sudo reboot
```

**Do not use `sudo bash install-v0.3.sh`**; the script invokes sudo only when needed. It installs `cage` if missing, switches Raspberry Pi OS to console auto-login, removes the old desktop autostart entry (with backups) and updates the already-installed Plymouth logo.

### How the display boots

1. The early Plymouth theme (if previously installed) shows the centered small logo.
2. The Pi auto-logs into tty1 without opening the desktop.
3. `cage` launches Chromium directly with a black background.
4. The web splash shows the centered logo and a real progress bar until the *actual app* sends its ready signal.
5. The app appears full-screen. The Pi's local server continues running even without Wi-Fi.

A brief black display may occur as firmware, kernel, compositor and browser hand off the display; the browser progress bar cannot run before the browser has started. Pi firmware splash and OS boot happen earlier than the application progress checks.

### Troubleshooting / rollback

If the screen is black after the boot transition, SSH remains available. Check:

```bash
systemctl status family-calendar --no-pager
command -v cage
journalctl -b -p err --no-pager | tail -40
```

Switch back to your prior desktop auto-login behavior:

```bash
cd ~/family-calendar-pi
bash rollback-v0.3.sh
sudo reboot
```

The installer backs up the altered login profile and desktop kiosk startup configuration in `~/.config/picalendar-v0.3/`. It does **not** erase your events, photos, `.env`, Google OAuth credentials, or other local data. The ZIP contains no account credentials or personal calendar data.

### Note on actual display power-off

The black-screen sleep button is a software sleep overlay unless your screen has a working Linux backlight control. Physically switching the LCD backlight off while touch is still active depends on the screen hardware; do not assume this works without identifying its controller.
