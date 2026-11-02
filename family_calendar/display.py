"""Backlight-only sleep with a persistent lease and independent recovery service.

Never suspends the Pi, powers down video, or disconnects the touchscreen.
Run `python -m family_calendar.display --guardian` in a separate systemd service.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import time
from pathlib import Path

BACKLIGHT_ROOT = Path('/sys/class/backlight')
LEASE_SECONDS = 30
NAME = re.compile(r'[A-Za-z0-9_.:@-]+')


class BacklightController:
    def __init__(self, state_dir=None):
        self.state_dir = Path(state_dir or os.environ.get(
            'FAMILY_CALENDAR_DISPLAY_STATE_DIR',
            str(Path.home() / '.local/state/picalendar-display')))

    @contextlib.contextmanager
    def locked(self):
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.state_dir / 'lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def read_state(self):
        try:
            return json.loads((self.state_dir / 'sleep.json').read_text())
        except FileNotFoundError:
            return None

    def save_state(self, state):
        target = self.state_dir / 'sleep.json'
        if state is None:
            target.unlink(missing_ok=True)
        else:
            temp = self.state_dir / 'sleep.tmp'
            with temp.open('w') as handle:
                json.dump(state, handle)
                handle.flush()
                os.fsync(handle.fileno())
            temp.replace(target)

    def devices(self):
        return sorted(p for p in BACKLIGHT_ROOT.glob('*')
                      if (p / 'brightness').is_file() and (p / 'max_brightness').is_file())

    def device(self):
        name = os.environ.get('FAMILY_CALENDAR_BACKLIGHT_DEVICE', '').strip()
        if name:
            if not NAME.fullmatch(name) or name in ('.', '..'):
                return None
            panel = BACKLIGHT_ROOT / name
            return panel if panel in self.devices() else None
        candidates = [p for p in self.devices() if not p.name.startswith('ddcci')]
        return candidates[0] if len(candidates) == 1 else None

    def guardian_ready(self):
        try:
            age = time.time() - (self.state_dir / 'guardian').stat().st_mtime
            return 0 <= age < 5
        except OSError:
            return False

    def status(self):
        try:
            with self.locked():
                panel = self.device()
                writable = bool(panel and os.access(panel / 'brightness', os.W_OK)
                                and (not (panel / 'bl_power').exists()
                                     or os.access(panel / 'bl_power', os.W_OK)))
                ready = self.guardian_ready()
                state = self.read_state()
                return {'version': '0.5.4', 'configured': panel is not None,
                        'available': writable and ready, 'guardian': ready,
                        'device': panel.name if panel else None,
                        'devices': [p.name for p in self.devices()],
                        'asleep': state is not None,
                        'mode': 'hardware' if writable and ready else 'unavailable'}
        except (OSError, ValueError, TypeError) as exc:
            return {'available': False, 'mode': 'unavailable', 'error': str(exc)}

    @staticmethod
    def write(panel, attribute, value):
        path = panel / attribute
        path.write_text(f'{value}\n')
        if int(path.read_text().strip()) != value:
            raise OSError(f'{attribute} readback did not match requested value')

    def restore(self, state):
        name = state['device']
        if not NAME.fullmatch(name) or name in ('.', '..'):
            raise ValueError('Invalid recovery device')
        panel = BACKLIGHT_ROOT / name
        maximum = int((panel / 'max_brightness').read_text())
        value = max(1, min(int(state['brightness']), maximum))
        self.write(panel, 'brightness', value)
        if (panel / 'bl_power').exists():
            self.write(panel, 'bl_power', 0)
        self.save_state(None)

    def power(self, asleep):
        try:
            with self.locked():
                state = self.read_state()
                if not asleep:
                    if state:
                        self.restore(state)
                    return {'mode': 'hardware' if state else 'unchanged',
                            'changed': bool(state), 'asleep': False}
                if not self.guardian_ready():
                    raise OSError('Recovery guardian is not running; hardware sleep refused')
                if state:
                    # Renew only the lease, never overwrite the saved brightness.
                    if state.get('recovering'):
                        raise OSError('Backlight recovery pending; sleep refused')
                    state['deadline'] = time.time() + LEASE_SECONDS
                    self.save_state(state)
                    return {'mode': 'hardware', 'changed': False, 'asleep': True}
                panel = self.device()
                if panel is None:
                    raise OSError('No unambiguous backlight device; select one or use a supported panel')
                maximum = int((panel / 'max_brightness').read_text())
                current = int((panel / 'brightness').read_text())
                if maximum <= 0 or not 0 < current <= maximum:
                    raise ValueError('Start with the display lit at a valid brightness')
                state = {'device': panel.name, 'brightness': current,
                         'deadline': time.time() + LEASE_SECONDS}
                # Journal before changing hardware, so another process can recover.
                self.save_state(state)
                try:
                    self.write(panel, 'brightness', 0)
                    if (panel / 'bl_power').exists():
                        self.write(panel, 'bl_power', 4)
                except (OSError, ValueError):
                    state.update(recovering=True, deadline=0)
                    self.save_state(state)
                    self.restore(state)
                    raise
                return {'mode': 'hardware', 'changed': True, 'asleep': True}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return {'mode': 'unavailable', 'changed': False, 'error': str(exc),
                    'recovery_pending': (self.state_dir / 'sleep.json').exists()}

    def guardian_tick(self):
        with self.locked():
            (self.state_dir / 'guardian').touch()
            state = self.read_state()
            if state and (state.get('recovering') or
                          not 0 < state['deadline'] - time.time() <= LEASE_SECONDS + 5):
                self.restore(state)


backlight = BacklightController()


def guardian():
    import logging
    import signal
    def stop(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        while True:
            try:
                backlight.guardian_tick()
            except (OSError, ValueError, TypeError, KeyError):
                logging.exception('Backlight recovery failed; retrying in one second')
            time.sleep(1)
    finally:
        backlight.power(False)


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--guardian']:
        guardian()
    elif sys.argv[1:] == ['--wake']:
        print(json.dumps(backlight.power(False)))
    else:
        print(json.dumps(backlight.status(), indent=2))
