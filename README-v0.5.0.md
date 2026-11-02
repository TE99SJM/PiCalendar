# PiCalendar v0.5.0 — integrated touchscreen calendar and Google login

This branch is an actual Git merge of **0.4.2** (first parent) and **0.3.3**
(second parent). Both original branch histories are retained.

## Included from 0.4.2
- Quiet, logo-based boot using the dedicated systemd Cage kiosk service
- Hidden mouse cursor, including cursor theme and HDMI phantom-pointer udev rule
- Existing month-slide animation and local dashboard features

## Included from 0.3.3
- Google Sign-In directly in PiCalendar Settings via Google Desktop OAuth
- Verified loopback callback, state validation, and HTTPS OAuth token exchange
- Automatic Google Calendar import after login; ongoing two-way synchronization
- Reconnect, Sync now, and Sign out controls
- One-time developer Google OAuth client configuration (no end-user token uploads)
- Service launcher that works even when shell scripts lose executable permissions

## Install / update existing Raspberry Pi

**Preserve** `data/`, `.env`, `.venv/` and
`config/google-oauth-desktop.json` when copying v0.5.0 onto your installed
PiCalendar. The OAuth client and Google refresh tokens stay on the Pi; they are
**not included in GitHub**.

After downloading the 0.5.0 branch and copying source over the existing app:

```bash
cd ~/family-calendar-pi
bash install.sh
# If upgrading from before v0.4.2's quiet console boot:
# bash startup/install-kiosk-service.sh
sudo reboot
```

If your Pi already runs the dedicated 0.4.2 kiosk service, you do not need to
run the kiosk installer again. The local calendar API remains bound to
127.0.0.1:8080; the boot checker uses 127.0.0.1:8081.

## Google configuration

A Desktop OAuth client and enabled Calendar API are still required once
**by the PiCalendar developer**, not by each user. Reuse your existing local
`config/google-oauth-desktop.json` when upgrading. Do not commit or share it.

After login on the touchscreen, PiCalendar fetches selected Google calendars.
The login is local to the Raspberry Pi, without hosting an external server.
This release does not add an operating-system on-screen keyboard to Google's
separate login page.

## Verification

```bash
.venv/bin/python -m pytest -q
node --check static/app.js
node tests/touch-gestures.test.cjs
bash -n install.sh run-kiosk.sh startup/launch-console-kiosk.sh
curl -fsS http://127.0.0.1:8080/api/status
```

The merged code requires testing on the physical Pi to confirm the 0.4.2 kiosk
startup/USB touchscreen and Google login work together.
