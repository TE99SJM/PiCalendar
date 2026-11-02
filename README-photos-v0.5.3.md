# PiCalendar photo imports — 0.5.2 / 0.5.3

## Branches

- `0.5.2` adds Google Drive imports.
- `0.5.3` includes those imports and adds iPhone photo uploads.
- Both retain the localhost-only Calendar server and local JPEG slideshow.

## Install

On the Raspberry Pi, after checking out the desired branch, run:

```bash
cd ~/family-calendar-pi
bash install.sh
```

The installer starts the additional photo-only service for 0.5.3 on TCP 8787.
The existing Calendar API remains on 127.0.0.1:8080. Keep the Pi on a trusted
private network; do **not** forward port 8787 to the Internet. The upload link
is an expiring 48-character bearer token: anyone with that QR/link can upload
photos until it expires. Generate a new link for each transfer session.
The 0.5.2 branch does not require or install the photo-only service.

## Google Drive 0.5.2+

1. In Google Cloud Console, enable the **Google Drive API** for the project
   that contains PiCalendar's installed-app OAuth client.
2. Add your Google account as an OAuth test user if the consent app is in Testing.
3. On the Pi, open Settings > Family photos > Connect Google Drive.
4. Grant **read-only Drive permission**. Your Calendar permissions and token are
   independent. Browse My Drive folders, select 1–20 images, and import.
5. Imported images are saved as optimized local JPEGs and remain available offline.

**Important**: `drive.readonly` is a Google-restricted OAuth scope. It may
require verification/security assessment for broad public distribution. This
prototype targets personal use/testing. Google Picker with `drive.file` is
the preferred narrower authorization path for a future public release.
The Drive browser is folder-based, not Google Photos integration.
Drive imports do not automatically update when a source file changes.

## iPhone QR upload 0.5.3

1. On PiCalendar, open Settings > Family photos > Send photos from iPhone.
2. Scan the QR code with your iPhone while connected to the Pi's local Wi-Fi.
3. Select images in Safari's file/photo picker and tap Upload photos.
4. Select Close transfer on the Pi when finished.

Uploads are limited to 12 images per batch and 30 MB per image. The 15-minute
QR token expires automatically. Images are converted to local JPEGs; iPhone
HEIC conversion depends on successful installation of `pillow-heif`.
If automatic IP discovery chooses the wrong interface, set
`FAMILY_CALENDAR_TRANSFER_HOST` to the Pi's LAN IPv4 address in `.env`,
then restart the Calendar service.

The QR service uses unencrypted HTTP on the *local network*; only use it on a
trusted Wi-Fi, not shared/public networks. Avoid storing the QR link or sharing
it beyond your home. There is no genuine Apple AirDrop integration.

## Testing

```bash
cd ~/family-calendar-pi
.venv/bin/python -m pytest -q
systemctl status family-calendar picalendar-phone --no-pager
```

For v0.5.2, omit `picalendar-phone` from the status command.
