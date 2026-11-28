# PiCalendar Linux kiosk

This installs PiCalendar on a minimal Debian 13 ARM64 system. The target is a
dedicated touchscreen tablet. Use a fresh console-only installation with systemd,
working DRM/KMS graphics, touch input, and a regular account with sudo and Git installed. Configure
networking and a way to log in remotely before dedicating tty1 to the kiosk.

The installer configures a local PiCalendar server and starts Chromium under
Cage on tty1 at boot. It uses the existing PiCalendar startup screen, database,
and Google Calendar integration. The tablet needs a working Linux installation
before running these steps. Hardware support on the Alexa Tablet 11 is unverified.

1. Clone this branch into your regular user's home directory.

   ```sh
   git clone --branch alexa-linux-kiosk https://github.com/TE99SJM/PiCalendar.git
   cd PiCalendar
   ```

2. Run the installer. If it stops, fix the first reported error before rebooting.

   ```sh
   bash linux-kiosk/install.sh
   ```

3. Verify the local API, then reboot to start the touchscreen kiosk.

   ```sh
   curl -fsS http://127.0.0.1:8080/api/status
   sudo reboot
   ```

4. Connect Google Calendar from PiCalendar Settings after provisioning the
   Desktop OAuth client described in [PiCalendar v0.5.0](../README-v0.5.0.md#google-configuration).
   The checkout holds the database and settings. Keep the checkout in place and
   back up `data/`, `.env`, and your local OAuth client when upgrading.

If the screen stays blank, connect remotely and check the service logs with
`sudo journalctl -b -u picalendar-linux-kiosk -u picalendar-linux --no-pager`.
To restore the text console, run
`sudo systemctl disable --now picalendar-linux-kiosk.service picalendar-linux.service`
and then `sudo systemctl start getty@tty1.service`.
