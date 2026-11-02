"""Optional Linux backlight support for the calendar's touchscreen sleep mode.

Touch input must remain available while the backlight is dark.  Only explicitly
selected Linux backlight devices are accessed. Most HDMI-only monitors do NOT
expose a /sys/class/backlight device, so those use the black browser overlay.
"""
from __future__ import annotations

import os
import re
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

    def status(self) -> dict:
        base = self.device()
        if base is None:
            return {'configured': False, 'available': False, 'mode': 'software'}
        available = (base / 'brightness').is_file() and (base / 'max_brightness').is_file()
        return {'configured': True, 'available': available, 'mode': 'hardware' if available else 'software'}

    def power(self, asleep: bool) -> dict:
        base = self.device()
        if base is None:
            return {'mode': 'software', 'changed': False}
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


backlight = BacklightController()
