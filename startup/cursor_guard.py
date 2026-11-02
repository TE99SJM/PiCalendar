#!/usr/bin/env python3
"""PiCalendar v0.5.1: best-effort Cage cursor-plane guard.

Cage may draw a pointer for HDMI-CEC devices even when no mouse exists.
After the touchscreen kiosk has finished loading, a VT round-trip can clear
the stale DRM cursor plane. This runs separately from the calendar service.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

LOG = logging.getLogger("picalendar-cursor-guard")


def http_json(url: str) -> dict | None:
    try:
        with urlopen(url, timeout=1.2) as response:
            result = json.load(response)
        return result if isinstance(result, dict) else None
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return None


def service_running(name: str) -> bool:
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", name], check=False
    ).returncode == 0


def await_ready(timeout: int = 150) -> bool:
    """Do not switch VTs while Plymouth, Cage or the calendar is loading."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if service_running("picalendar-kiosk.service"):
            progress = http_json("http://127.0.0.1:8081/api/progress")
            if progress and progress.get("done") is True:
                LOG.info("PiCalendar startup readiness checks completed")
                return True
        time.sleep(2)
    return False


def cursor_plane_active(root: Path = Path("/sys/kernel/debug/dri")) -> bool | None:
    """True=active cursor plane, False=inactive, None=no readable DRM evidence."""
    try:
        states = sorted(root.glob("*/state"))
    except OSError:
        return None
    checked = False
    found_cursor = False
    for state in states:
        try:
            data = state.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            continue
        checked = True
        blocks = re.split(r"(?=^\s*plane\[\d+\]:)", data, flags=re.MULTILINE)
        for block in blocks:
            lines = block.splitlines()
            if not lines or not re.match(r"^\s*plane\[\d+\]:", lines[0]):
                continue
            named_cursor = bool(
                re.search(r"\bcursor(?:[-_\s]\w+)?\b", lines[0], re.IGNORECASE)
                or re.search(r"^\s*type\s*=\s*cursor\b", block, re.MULTILINE | re.IGNORECASE)
            )
            if not named_cursor:
                continue
            found_cursor = True
            fb = re.search(r"^\s*fb\s*=\s*(\S+)", block, re.MULTILINE | re.IGNORECASE)
            crtc = re.search(r"^\s*crtc\s*=\s*(\S+)", block, re.MULTILINE | re.IGNORECASE)
            inactive = {"0", "none", "null", "(null)", "-"}
            if (fb and crtc and fb.group(1).lower() not in inactive
                    and crtc.group(1).lower() not in inactive):
                return True
    return False if checked and found_cursor else None


def flip_vt(kiosk_vt: int = 1, scratch_vt: int = 2, delay: float = 0.75) -> None:
    """Always restore the kiosk VT, even if the first switch fails."""
    try:
        subprocess.run(["chvt", str(scratch_vt)], check=True, timeout=5)
        time.sleep(delay)
    finally:
        subprocess.run(["chvt", str(kiosk_vt)], check=True, timeout=5)
        # Don't leave a new login prompt waiting on the temporary VT.
        subprocess.run(["systemctl", "stop", f"getty@tty{scratch_vt}.service"],
                       check=False, timeout=8)


def run_guard(*, ready_timeout: int = 150, settling: int = 25,
              attempts: int = 4, confirmation: int = 45,
              dry_run: bool = False) -> int:
    if not Path("/dev/tty1").exists():
        LOG.error("No tty1; cannot perform a safe kiosk VT reset")
        return 1
    if not await_ready(ready_timeout):
        LOG.warning("Kiosk never became ready; no VT switching attempted")
        return 1
    if settling:
        LOG.info("Waiting %ds for Chromium to finish drawing", settling)
        time.sleep(settling)
    if not service_running("picalendar-kiosk.service"):
        LOG.warning("Kiosk stopped during startup; no VT switching attempted")
        return 1
    LOG.info("DRM cursor-plane state before reset: %s", cursor_plane_active())
    if dry_run:
        return 0

    for attempt in range(1, attempts + 1):
        if not service_running("picalendar-kiosk.service"):
            LOG.warning("Kiosk stopped; aborting cursor guard")
            return 1
        LOG.info("Cursor reset %d/%d: VT2 then back to VT1", attempt, attempts)
        try:
            flip_vt()
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            LOG.error("VT reset failed: %s", exc)
            return 1
        time.sleep(2)
        instant = cursor_plane_active()
        LOG.info("DRM cursor-plane state after reset: %s", instant)
        if instant is None:
            LOG.warning("DRM cursor-plane inspection unavailable; verify result on touchscreen")
            return 0  # Avoid repeated disruptive VT switching without evidence.
        if instant is False:
            time.sleep(confirmation)
            stable = cursor_plane_active()
            LOG.info("DRM cursor-plane state after %ds: %s", confirmation, stable)
            if stable is False:
                LOG.info("Cursor plane stayed cleared")
                return 0
        if attempt < attempts:
            LOG.warning("Cursor plane present or reappeared; retrying")
    LOG.warning("Cursor plane still active; run PiCalendar cursor diagnostics")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="PiCalendar Cage cursor-plane guard")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--settling", type=int, default=25)
    parser.add_argument("--ready-timeout", type=int, default=150)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--confirmation", type=int, default=45)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if args.settling < 0 or args.attempts < 1 or args.confirmation < 0 or args.ready_timeout < 1:
        parser.error("Invalid cursor-guard timing")
    return run_guard(ready_timeout=args.ready_timeout, settling=args.settling,
                     attempts=args.attempts, confirmation=args.confirmation,
                     dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
