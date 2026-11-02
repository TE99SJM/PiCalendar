> **Current development branch: PiCalendar v0.3.3.** See [README-v0.3.3.md](README-v0.3.3.md) for Google Sign-In in Settings. The publisher must configure the Google OAuth client once; no end-user token or client JSON setup is needed.

> **Previous release: PiCalendar v0.3.1.** For the no-desktop boot, animated swipes, and Google login directly from Settings, follow **README-v0.3.1.md**. This older document describes the original installation and optional terminal-based OAuth flow.

# PiCalendar v0.3

**For installation and console-only kiosk startup, read [README-v0.3.md](README-v0.3.md) first.**

# PiCalendar v1.2 — Raspberry Pi 5 touchscreen family dashboard

Use the **provided logo exactly as uploaded**. This is a full-source release with
the corrected touch gestures and real prelaunch progress screen.

## Update your existing PiCalendar

**Before unzipping the new release**, back up current data if possible. The update
is designed to overlay `~/family-calendar-pi` without replacing the `data/` directory.

On your Windows computer, transfer `PiCalendar-v1.2.zip` to your Raspberry Pi:

```powershell
scp "$env:USERPROFILE\Downloads\PiCalendar-v1.2.zip" YOUR_PI_USERNAME@YOUR_PI_IP:~/
```

On the Pi through SSH:

```bash
mkdir -p ~/family-calendar-pi
unzip -o ~/PiCalendar-v1.2.zip -d ~/family-calendar-pi
cd ~/family-calendar-pi
bash install-v1.2.sh
sudo reboot
```

If `unzip` isn't installed: `sudo apt-get install unzip`. Don't run `unzip` in Windows PowerShell.

## Touch controls

- Drag the right-hand tasks/chore/shopping sidebar with your finger to scroll.
- Swipe the month grid left/right to change month; the controls work in week view too.
- Scrollbars and accidental text selection are hidden. Editing fields still select text.
- Supports native touch events, pointer-only touch input, and mouse-emulated touchscreen input.
- **Troubleshooting**: open the Pi Chromium DevTools and check for `touch-gestures.js` load errors if touch still doesn't move. Touch input drivers vary; these gestures are browser-tested, but must be validated on your specific hardware.

## Startup screen

- The supplied calendar-and-raspberry logo has **no text or progress bar** embedded.
- Black background, centered icon, a **separate thin bar at the bottom** and **no visible status text**.
- The bar is real, advancing only when local app assets, local database, service and data have passed readiness checks. It waits instead of reaching 100% on a timer.
- The boot checker is local and **doesn't require Wi-Fi**. It opens the saved calendar when Google is offline.
- Optional Linux boot logo replacement: `bash startup/install-boot-branding.sh` (backs up boot config). **This is separate from the actual desktop readiness bar**: firmware boot cannot show that bar before Linux starts. The early Plymouth logo only appears when that option is installed and supported by the OS.

## Offline data

- Local SQLite database stores synced Google events, local events, chores, groceries and meals.
- Photos are local; offline edits to connected Google events are queued for the next successful sync.
- Google sync retains up to 2 years of history / 2 years ahead by default, when available; it is not a substitute for a full Google Calendar export.
- Local SQLite backup runs daily and retains the seven newest snapshots in `backups/`.
- No Google authorization tokens, photos, SQLite databases or private `.env` files belong on GitHub.

## Safety

- PiCalendar API binds to `127.0.0.1:8080` on the Pi (private kiosk).
- Google syncing requires configuring Google Cloud OAuth on the Pi; it is not automatically authorized by installing the release.
- Sleep-to-black remains a black overlay unless your monitor has independent backlight control; physically powering off a USB touchscreen may prevent touch-to-wake.

---

## What's included

| Feature | Behavior |
|---|---|
| Monthly + weekly calendar | Touch to select dates; tap appointments to edit |
| Google Calendar | Reads and writes Google Calendar events, multiple calendars, colors, recurring event instances, automatic sync approximately every 5 minutes |
| Offline | Local calendar, chores, meals, lists, and photos remain available without Internet; edits to linked Google events are queued until online |
| Chore list | Assign names, check off chores, daily / weekly repeat |
| Shopping list | Add, check off, delete items |
| Meal planning | Choose meals for any day; shows the selected day and the following four days |
| Photo slideshow | Upload/remove photos from the touchscreen; rotates every 12 seconds |
| Weather (optional) | Local weather from Open-Meteo, using your latitude/longitude |
| Full-screen kiosk | Starts Chromium on boot after your Raspberry Pi OS desktop login |
| Display sleep and wake | Tap ⏻ to black out the display; double tap to wake. Optional physical backlight-off for compatible screens |
| Data storage | Local SQLite database and local JPEG photos on the Pi |

**Important scope:** Google sync applies to **calendar events**. Chores, groceries, meals, and photos are local-only in this version. You must configure your own Google Cloud OAuth desktop client for Google sync; it is free for ordinary personal calendar API use, subject to Google's terms and quotas. The local calendar works without any Google connection.

## Hardware and software

- Raspberry Pi 5 (2GB+ RAM; 4GB recommended), microSD or SSD, proper Pi 5 power supply.
- Raspberry Pi OS 64-bit **Desktop** (Bookworm or newer) recommended.
- Connected touchscreen working in Raspberry Pi OS. Any HDMI/DSI screen works if the OS already recognizes touch.
- Set the Pi OS **timezone to America/Chicago** (or your actual local timezone) in Raspberry Pi Configuration so the on-screen clock and event time editor display the correct local times. Also update `FAMILY_CALENDAR_TIMEZONE` in `.env` if you live elsewhere.
- Internet for first dependency install and Google account authorization; local features work offline afterward.

## Install (on the Raspberry Pi itself)

1. Copy/extract this `family-calendar-pi` directory into your home directory, so it is at `~/family-calendar-pi`.
2. On your Pi, open Terminal and run:

   ```bash
   cd ~/family-calendar-pi
   bash install.sh
   ```

   This builds a Python virtual environment, downloads required Python packages, initializes SQLite and installs/enables the `family-calendar` systemd service. It may ask for your Linux sudo password to install a system service.
3. Open Chromium on the Pi and visit **http://127.0.0.1:8080**. You can immediately add a local event, task, shopping item, meal or photo.
4. To make the touchscreen automatically open the calendar full-screen after you log in to the Pi desktop:

   ```bash
   cd ~/family-calendar-pi
   bash install-kiosk.sh
   ```

   Set Raspberry Pi OS to **Desktop Autologin**, and reboot. If the OS blanks its screen after inactivity, disable screen blanking in Raspberry Pi Configuration > Display. `install-kiosk.sh` supports the labwc desktop commonly used on current Pi OS, plus a standard XDG autostart fallback. The install does **not** erase your existing autostart commands.

## Sleep button and double-tap to wake

The header includes a **⏻ Sleep screen** button. Tap it to cover the entire screen
with solid black; **double tap roughly the same spot within 650 milliseconds** to
wake it. A single tap does not unlock the calendar. You can also press Enter or
Escape on an attached keyboard as a fallback.

**This is display sleep, not Raspberry Pi CPU hibernation.** The Pi and the touch
controller must remain awake to recognize the double tap. The local Google sync
service can continue working while the screen sleeps. Software blanking is the
default: the picture is black, but an LCD monitor's backlight **may still be on**.

### Optional true backlight-off (screen dependent)

Some official DSI screens and compatible touchscreens expose a Linux backlight
controller. You can optionally make the panel light itself turn off while touch
input stays active. **Do not enable hardware backlight switching until you've
verified touches still work while the backlight is at zero.** On some screens,
disabling the backlight also disables the touch controller, and double-tap wake
would not work.

1. Find your screen's backlight device on the Pi with `ls /sys/class/backlight`.
   An empty list usually means it is an HDMI screen without this sysfs interface.
2. If one exists, check its permissions with
   `ls -l /sys/class/backlight/<DEVICE>/brightness`. Your calendar systemd service
   runs as your regular user and needs permission to write this file. Do not
   use `chmod 777` or run the entire calendar service as root.
3. Once you've established that **touch continues working with the light off**,
   set `FAMILY_CALENDAR_BACKLIGHT_DEVICE=<DEVICE>` in `~/family-calendar-pi/.env`.
   Replace `<DEVICE>` with the exact single name from step 1. Restart the local
   service with `sudo systemctl restart family-calendar`.
4. The next tap of ⏻ writes brightness 0; double tap writes the previous
   brightness back. The current optional mode is available at
   `http://127.0.0.1:8080/api/display/status` on the Pi.

If backlight control is unavailable or cannot be written, the app automatically
uses its black overlay. An HDMI monitor that doesn't expose a Linux backlight
may need model-specific DDC/CI or hardware support. **Turning off the entire
monitor or suspending the Pi is not a drop-in alternative**, since those can
stop delivery of touch gestures.

If you configure an unsuitable backlight and can no longer wake by touch, attach
a keyboard and press Escape; if the light is physically stuck off, restore it
locally over SSH by writing the original brightness to the selected sysfs file,
or reboot and disable the backlight setting. Retain an accessible power switch
while testing.

### Connect Google Calendar (two-way syncing)

This is an **optional one-time setup**. It must be done from the Pi desktop, so the Google consent page can open on the Pi's browser. You cannot reuse the credentials from a ChatGPT Google Calendar connection.

1. Open the [Google Cloud Console](https://console.cloud.google.com/), create or select a project.
2. In **APIs & Services > Library**, enable the **Google Calendar API**.
3. Under **Google Auth Platform / OAuth consent screen**, configure the app. For personal use, add your own Google account as a test user if prompted. You will need calendar-event write access plus read-only access to the list of calendars.
4. Under **Clients** (or **Credentials > Create credentials > OAuth client ID**), choose application type **Desktop app**. Download the OAuth client JSON file.
5. Copy and rename the JSON file onto your Pi as:

   ```text
   ~/family-calendar-pi/data/google-client-secret.json
   ```

   **Keep the JSON private.** Do not post it in chats or commit it to a public repository.
6. In a terminal **on the Pi desktop**:

   ```bash
   cd ~/family-calendar-pi
   .venv/bin/python connect_google.py
   ```

   A browser opens on your Pi. Sign into your Google account and approve the requested permissions. If Google shows an unverified app warning for your own private OAuth project, review that it is your project before proceeding. The app saves its Google refresh token privately in `data/google-token.json` with mode 0600. The token stays on your Pi, and you may revoke it in Google Account settings.
7. Back on the calendar, tap **↻ Sync**. In Settings, enable the calendars you want displayed. New events default to the first selected writable Google calendar when one is connected; you can pick **Family (local)** in the event editor to keep an event on the Pi only.

**Google OAuth note:** Google may expire refresh tokens after roughly seven days when an external OAuth application remains in *Testing*. To make sync persist, review Google's OAuth publishing-status rules for personal apps; switching from Testing to In production may be appropriate, although it may show a verification warning for an unverified private app. If authorization stops working, re-run `connect_google.py`.

## How syncing and offline changes work

- Tapping **Save event** writes it to the Pi's SQLite database immediately.
- If you selected a Google calendar, the event is queued for upload; edits and deletions are also queued when offline.
- Approximately every 5 minutes, the background process first uploads local changes, then downloads changes from Google. **↻ Sync** does it on demand.
- Imported Google events cover approximately 45 days in the past through 370 days in the future.
- For simultaneous edits made in Google and on the Pi, **the Pi's queued edit takes priority at the next sync**. Recurring Google instances can be edited individually, but this app does not create new recurrence rules.
- Google needs Internet. All non-Google features and locally stored calendar events work offline.

## Display, screen, and power

- Screen uses HTML/CSS in Chromium and adapts automatically to display resolution, including 1920×1080 15.6-inch touchscreens.
- The Raspberry Pi 5 and the touchscreen need compatible power. **Do not assume the Pi can safely power a large monitor from USB**, even if both use USB-C. Check your screen's input voltage/current and use a correctly rated supply or manufacturer-approved power distribution.
- Kiosk mode is a separate desktop process; the server starts automatically at boot as a systemd service.

## Settings and weather

Open **⚙ Settings** from the display to change the family name, choose visible calendars, enter optional weather coordinates, and manage photos. You can use a GPS coordinate lookup to find your latitude/longitude. Weather is retrieved from `api.open-meteo.com` no more than once every 15 minutes. When offline or unconfigured, the weather area simply stays empty.

## Logs, testing and troubleshooting

```bash
# Is the server running?
systemctl status family-calendar --no-pager

# See why something failed
journalctl -u family-calendar -n 60 --no-pager

# Restart after editing source code
sudo systemctl restart family-calendar

# Test the backend after installation
cd ~/family-calendar-pi
.venv/bin/python -m pip install pytest httpx
.venv/bin/python -m pytest -q
```

If a touch action does not respond, first verify touch is recognized in the desktop outside Chromium. If the screen has an independent USB touch connection, it usually needs both HDMI for video and USB for touch.

## Security and backups

The server binds to **127.0.0.1** by default, so only apps running on that Raspberry Pi can access it. **Do not change `FAMILY_CALENDAR_HOST` to `0.0.0.0` or forward port 8080 to the Internet** without adding authentication, HTTPS and access controls. This version is intentionally designed for a private standalone kiosk.

The `data/` folder contains the database, family photos and (if connected) private Google authentication files. Keep it secure. To make a consistent local backup:

```bash
cd ~/family-calendar-pi
sudo systemctl stop family-calendar
tar -czf "$HOME/family-calendar-backup.tar.gz" data/
sudo systemctl start family-calendar
```

Don't publish/share the backup; it may contain personal calendar data and Google tokens. A restore is performed by stopping the service, restoring the `data/` directory, then starting the service.

## Project layout

```text
family-calendar-pi/
├── family_calendar/
│   ├── main.py           # Local FastAPI server and data endpoints
│   ├── storage.py        # SQLite database and local paths
│   └── google_sync.py    # Two-way Google Calendar integration
├── static/
│   ├── index.html        # Touchscreen dashboard and dialogs
│   ├── style.css         # Responsive 15.6-inch display styling
│   └── app.js            # Calendar rendering, touch interactions
├── connect_google.py    # One-time OAuth browser authorization
├── install.sh            # Local service installation
├── install-kiosk.sh      # Chromium startup integration
├── run.sh                # Local server
├── run-kiosk.sh          # Fullscreen Chromium
├── requirements.txt
└── data/                 # Created on installation; private data
```

This is a working custom first release rather than a commercial-feature-identical copy of Aluratek or Skylight. You own the local code and can modify it. It does not include a dedicated account system, notifications, remote access, or advanced recurring-event editing yet.
