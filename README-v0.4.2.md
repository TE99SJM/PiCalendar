# PiCalendar v0.4.2 — quiet boot and touchscreen cursor

Based on the working v0.4.1 logo-only startup and v0.4.0 calendar slide.

This build changes the display launch from console auto-login to a systemd Cage session, preventing the GNU/Linux login message from being shown on tty1. It includes a user-local transparent Xcursor theme, CSS cursor suppression, and udev rules that prevent the Raspberry Pi `vc4-hdmi-0` and `vc4-hdmi-1` HDMI input devices from being classified as mice while preserving their keyboard capability and the USB touchscreen. Actual pointer suppression depends on the installed Cage/libinput stack and must be verified on hardware. It does not change events, syncing, storage, month animations, or photos.

## Upgrade on Pi

Download branch 0.4.2 to a temporary directory. Back up your existing installation including private data, then copy the new source over the old application. Do NOT delete `data/` or `.env`.

Run from `~/family-calendar-pi`, as your regular user:

```sh
bash startup/install-kiosk-service.sh
sudo reboot
```

The kiosk installer installs `startup/99-picalendar-cursor.rules` into `/etc/udev/rules.d/`, reloads udev rules, and applies them to input devices. For an already-running kiosk, restart `picalendar-kiosk` or reboot to test pointer behavior.

Service logs: `journalctl -u picalendar-kiosk -b --no-pager`

Rollback over SSH: `bash ~/family-calendar-pi/startup/rollback-kiosk-service.sh && sudo reboot`

The firmware can briefly be black before graphics initialize. A Plymouth-to-Wayland handoff may also cause a transient blank image; the fix is intended to remove console words, not guarantee zero display mode transitions. Verify on the Pi itself before considering it stable.
