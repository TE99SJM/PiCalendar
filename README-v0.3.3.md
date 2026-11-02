# PiCalendar v0.3.3 — Google Sign-In in Settings

Based on main branch v0.3.2 with the calendar month-slide clipping fix retained.
All local calendar, photo, chore, shopping, weather and touchscreen features remain.

## For people using the PiCalendar device

Open **Settings → Google Calendar → Sign in with Google**. A real Google account
page opens in the full-screen Chromium browser. Approve Calendar access. Google
returns to PiCalendar, which begins two-way calendar synchronization. You can
choose calendars, sync immediately, reconnect or sign out using Settings.

**No Google Cloud account, JSON upload, manual access token, or SSH is required
for end users.** Sign-out erases the local Google token and downloaded Google
events while preserving local calendar entries and other local data.

## For the developer/publisher (one-time REQUIRED step)

Google Calendar API requires a Google Cloud OAuth Desktop application for
installed devices. We cannot provide working sign-in without your own
Google OAuth client ID. Create a Google Cloud project, enable Google Calendar
API, configure an OAuth consent screen, and make **Desktop app** credentials.
Keep your credentials out of Git.

At build/deployment time provide ONE of:
- A Desktop OAuth JSON at config/google-oauth-desktop.json (ignored by Git).
- Environment variables FAMILY_CALENDAR_GOOGLE_CLIENT_ID and
  FAMILY_CALENDAR_GOOGLE_CLIENT_SECRET.
- FAMILY_CALENDAR_GOOGLE_CLIENT_FILE pointing to a local desktop-client JSON.

A legacy v0.3.1 client file continues to work for upgrades. The client ID is
an identifier, not a password. Refresh tokens stay local in data/google-token.json,
with file permissions 0600; do not commit device credentials or private data.

The Pi and its Chromium kiosk use a 127.0.0.1 desktop OAuth loopback callback.
Do the first sign-in directly on the Raspberry Pi. The Google sign-in page cannot
be embedded inside an iframe; PiCalendar opens it in the browser's top-level
window then returns to the calendar automatically.

**For public distribution:** Calendar access scopes are sensitive, so Google
may require app verification and a published consent screen. In Testing mode,
only permitted test users can sign in, and refresh tokens may expire in 7 days.

Official documentation:
- https://developers.google.com/identity/protocols/oauth2/native-app
- https://developers.google.com/workspace/calendar/api/auth
- https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification

## Tests

Run with project dependencies installed:
\`\`\`sh
python -m pytest -q
node --check static/app.js
python -m compileall -q family_calendar
\`\`\`

Live Google authentication must be tested with the developer's real OAuth client
on the physical Raspberry Pi; these tests mock Google and require no tokens.

## Startup reliability update
The initial GitHub upload stored `run.sh` without the executable bit.
The systemd service now launches it explicitly through Bash and the installer
repairs launcher permissions. The previous `curl: (7) Connection refused`
can result when systemd cannot execute `run.sh`. If that symptom persists,
use `sudo journalctl -u family-calendar.service -n 60 --no-pager` for diagnosis.

The OAuth callback returns to PiCalendar, which now performs one initial sync
rather than racing with a second background sync. Sync errors are displayed
instead of incorrectly claiming success.
