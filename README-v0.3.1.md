# PiCalendar v0.3.1 — silent startup, animated calendar, Google sign-in in Settings

This is an **incremental upgrade for an existing PiCalendar v0.3 installation** on Raspberry Pi OS 64-bit with a working Cage/Chromium kiosk. It keeps the uploaded 1024x1024 PNG in `static/logo.png`, the smaller centered early-boot image, and **all private SQLite data, calendar history, photos, and Google OAuth files already on the Pi**.

## What changed

- **Silent boot**: adds Plymouth logo, disables Raspberry Pi's default firmware splash, suppresses visible Linux boot status and routes kernel log messages to tty3 instead of tty1, and clears/hides the console before opening Cage. The existing kiosk shows a black startup page with **only your center logo and real progress bar**, then switches to the calendar only after local API checks and dashboard rendering finish. No ordinary desktop is started.
- **Calendar animation**: tap arrows or swipe horizontally; the old month slides away and the new month slides in over 730 milliseconds. UI prevents overlapping animations. Animations are disabled by the system's reduced-motion setting. Existing touch scrolling in the right sidebar remains.
- **Google account in Settings**: one-time upload of your own Google Cloud OAuth **Desktop app** client JSON through Settings (no terminal OAuth command). Then tap **Sign in with Google**. Google's login/consent page opens in the **top-level Chromium window**, not inside an iframe. On completion PiCalendar returns to the dashboard and starts a sync.
- **Two-way Google Calendar**: the existing event editor allows creating, editing and deleting events on a selected **writable Google calendar**. Changes save to local SQLite immediately and are pushed to Google shortly afterward when online. A 5-minute background retry handles connectivity loss. Edits made on other devices download on sync. **Events saved under `Family (local)` are intentionally local-only**, even when a Google account is connected. Chores, groceries, meals, and photos are local-only.

## Step-by-step upgrade

From Windows PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\PiCalendar-v0.3.1.zip" samuel@192.168.50.211:~/
ssh samuel@192.168.50.211
```

On the Pi **over SSH**:

```bash
# 1. Preserve entire prior installation, including private data
sudo systemctl stop family-calendar
tar -czf "$HOME/PiCalendar-pre-v0.3.1-$(date +%Y%m%d-%H%M%S).tar.gz" -C "$HOME" family-calendar-pi
sudo systemctl start family-calendar

# 2. Extract over the existing installation (does not remove data or settings)
unzip -o ~/PiCalendar-v0.3.1.zip -d ~/family-calendar-pi

# 3. Install as your usual account, NOT with sudo bash
cd ~/family-calendar-pi
bash install-v0.3.1.sh

# 4. Reboot to see the startup and scrolling behavior
sudo reboot
```

The install script makes timestamped backups of `/boot/firmware/config.txt` and `/boot/firmware/cmdline.txt` before changing them. It installs Plymouth if needed, updates the early-boot theme, and preserves SSH and the local database. **Do not run the install script until your Pi is on stable power and a backup exists.**

### Boot display limitations

During the **earliest firmware/HDMI initialization** the display may briefly be dark, and there can be a momentary KMS switch when Plymouth hands over to Cage. No Raspberry Pi OS userspace application can guarantee that the logo is visible from the very first electrical instant of power-on or that the handoff never blanks. PiCalendar aims to show only the small centered logo and then the graphical progress bar with no desktop or ordinary boot text. The progress bar is not fake; it is driven by local readiness checks and waits for the app to render. Wi-Fi is not required to boot using saved data.

### Connect to your Google account on the Pi touchscreen

1. In Google Cloud Console, create a project and **enable Google Calendar API**. Configure the OAuth consent screen (add your Google address as a test user while in Testing) and create an OAuth client of type **Desktop app**. Download its JSON file; keep it private.
2. In the calendar tap **Settings → Google Calendar → OAuth client JSON file** and select the downloaded JSON. If you prepared it on a different computer, move the client JSON onto the Pi first, e.g. `scp` it into the user's Downloads folder (not the app's public `static/` directory).
3. Tap **Sign in with Google**, sign in to your account directly on Google's website, and grant calendar-event editing permission. The browser returns to PiCalendar, begins importing calendars, and populates the list of writable calendars.
4. In the event editor, select a **Google calendar** (not `Family (local)`) to create a two-way-synced event. Use **Sync** for an immediate refresh; otherwise automatic syncing runs periodically.

You do **not** type your Google password into PiCalendar. The app keeps a refresh token at `data/google-token.json` with restrictive permissions, and only binds the web service to `127.0.0.1` by default. Never upload the OAuth JSON or token to GitHub.

**Note on Google Testing mode**: Google may expire refresh tokens after about seven days for external apps that remain in Testing. If the session stops working, reconnect through Settings and consult the Google Cloud OAuth publishing requirements for a long-lived personal installation.

## Diagnostics and rollback

To see service and kiosk logs over SSH (without adding words to the display):

```bash
systemctl status family-calendar --no-pager
journalctl -u family-calendar -n 50 --no-pager
cat ~/.local/state/picalendar/kiosk.log | tail -60
```

To restore the previous *desktop login* (not the `/boot/firmware` command-line changes):

```bash
cd ~/family-calendar-pi
bash rollback-v0.3.sh
sudo reboot
```

To restore the **early-boot command line and config**, use the timestamped files named `/boot/firmware/cmdline.txt.picalendar-v031-*.bak` and `/boot/firmware/config.txt.picalendar-v031-*.bak` with `sudo cp` after verifying the backup names. Never guess the backup timestamp. To avoid losing SSH access, do boot changes only with a recovery path available.

Hardware backlight-off and wake-by-touch are still subject to your display's power/controller capabilities and are not part of this release.
