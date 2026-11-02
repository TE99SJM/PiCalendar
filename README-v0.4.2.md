# PiCalendar v0.4.2 — quiet boot and touchscreen cursor

Based on the working v0.4.1 logo-only startup and v0.4.0 calendar slide.

This build changes the display launch from console auto-login to a systemd Cage session, preventing the GNU/Linux login message from being shown on tty1. It includes a user-local transparent Xcursor theme and CSS cursor suppression. It does not change events, syncing, storage, month animations, or photos.

## Upgrade on Pi

Download branch 0.4.2 to a temporary directory. Back up your existing installation including private data, then copy the new source over the old application. Do NOT delete `data/` or `.env`.

Run from `~/family-calendar-pi`, as your regular user:

```sh
bash startup/install-kiosk-service.sh
sudo reboot
```

Service logs: `journalctl -u picalendar-kiosk -b --no-pager`

Rollback over SSH: `bash ~/family-calendar-pi/startup/rollback-kiosk-service.sh && sudo reboot`

The firmware can briefly be black before graphics initialize. A Plymouth-to-Wayland handoff may also cause a transient blank image; the fix is intended to remove console words, not guarantee zero display mode transitions. Verify on the Pi itself before considering it stable.
