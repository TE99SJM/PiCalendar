# PiCalendar v0.3.2

Source snapshot for Raspberry Pi 5. Includes all v0.3.1 features and the v0.3.2 calendar slide clipping fix.

- Standalone Raspberry Pi kiosk, branded logo and readiness-based startup splash
- Google Calendar integration using your own OAuth Desktop App credentials
- Local calendar database, local shopping, chores, meals and photos; Google events synchronize when connected
- Touch-driven side panel scrolling and smooth calendar month swipes
- Calendar animation clipped to the calendar pane to avoid overlapping the sidebar

See README.md and README-v0.3.1.md for setup and permissions.

Install from a clean checkout (Raspberry Pi OS Desktop 64-bit):

```sh
bash install.sh
bash install-v0.3.sh
bash install-v0.3.1.sh
sudo reboot
```

Do not commit `.env`, `data/`, any OAuth JSON/token files, SQLite files, or backups. They are intentionally not included here. The included `.gitignore` helps protect these files, but review `git status` before pushing.

**Note:** The v0.3.2 CSS containment fix has passed source review but must be verified on your specific touchscreen/compositor.
