"""Optional hardware display power support for touchscreen sleep mode.

Touch input must remain available while the panel is dark. Supports explicitly
selected Linux backlight devices and DDC/CI monitor standby. Most HDMI-only
monitors need DDC/CI enabled and may not keep USB touch active in standby, so
the opaque browser overlay remains the safe fallback.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

BACKLIGHT_ROOT = Path('/sys/class/backlight')


class BacklightController:
    def __init__(self):
        self.previous_brightness: int | None = None

    def device(self) -> Path | None:
        name = os.environ.get('FAMILY_CALENDAR_BACKLIGHT_DEVICE', '').strip()
        # Prevent user-supplied paths and traversal; only single sysfs device names.
        if not name or not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in ('.', '..'):
            return None
        return BACKLIGHT_ROOT / name

    def ddcutil_display(self) -> int | None:
        """Return the explicitly selected ddcutil display number, if valid."""
        value = os.environ.get('FAMILY_CALENDAR_DDCUTIL_DISPLAY', '1').strip()
        if not value:
            return None
        if not value.isdigit() or int(value) < 1:
            return None
        return int(value)

    def status(self) -> dict:
        base = self.device()
        if base is not None:
            available = (base / 'brightness').is_file() and (base / 'max_brightness').is_file()
            return {'configured': True, 'available': available,
                    'mode': 'hardware' if available else 'software'}

        display = self.ddcutil_display()
        if display is not None:
            available = shutil.which('ddcutil') is not None
            return {'configured': True, 'available': available,
                    'mode': 'ddcutil' if available else 'software',
                    'display': display}

        return {'configured': False, 'available': False, 'mode': 'software'}

    def power(self, asleep: bool) -> dict:
        base = self.device()
        if base is not None:
            try:
                brightness = base / 'brightness'
                maximum = int((base / 'max_brightness').read_text().strip())
                if maximum <= 0:
                    raise ValueError('Backlight has no valid maximum brightness')
                current = int(brightness.read_text().strip())
                if asleep:
                    if current > 0:
                        self.previous_brightness = min(current, maximum)
                    brightness.write_text('0\n')
                else:
                    brightness.write_text(f'{self.previous_brightness or maximum}\n')
                return {'mode': 'hardware', 'changed': True}
            except (OSError, ValueError) as exc:
                # Do not break touch wake when a particular panel lacks sysfs control.
                return {'mode': 'software', 'changed': False, 'error': str(exc)}

        display = self.ddcutil_display()
        if display is None:
            return {'mode': 'software', 'changed': False}

        ddcutil = shutil.which('ddcutil')
        if ddcutil is None:
            return {'mode': 'software', 'changed': False,
                    'error': 'ddcutil is not installed'}

        # MCCS VCP D6 value 0x02 requests DPMS standby (panel dark, monitor
        # still powered); 0x01 requests normal operation. Do not request full
        # power-off because the monitor may stop accepting the wake command.
        power_mode = '0x02' if asleep else '0x01'
        command = [
            ddcutil, 'setvcp', '--display', str(display),
            'D6', power_mode,
        ]
        try:
            subprocess.run(
                command, check=True, timeout=8,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            return {'mode': 'ddcutil', 'changed': True, 'display': display}
        except (OSError, subprocess.SubprocessError) as exc:
            # Keep software double-tap wake usable if DDC/CI is unavailable.
            return {'mode': 'software', 'changed': False, 'error': str(exc)}


backlight = BacklightController()
