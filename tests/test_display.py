"""Hardware-independent true-sleep regression tests; run with unittest or pytest."""
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('display_test', Path(__file__).resolve().parents[1] / 'family_calendar/display.py')
display = importlib.util.module_from_spec(spec)
spec.loader.exec_module(display)

class DisplayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for mock in (patch.dict(os.environ, {}, clear=True), patch.object(display, 'BACKLIGHT_ROOT', self.root / 'panels')):
            mock.start()
            self.addCleanup(mock.stop)
        self.c = display.BacklightController(self.root / 'state')
        self.c.guardian_tick()
        self.p = self.panel('4-0045')

    def panel(self, name):
        p = self.root / 'panels' / name
        p.mkdir(parents=True)
        for key, value in [('brightness', '19'), ('max_brightness', '31'), ('bl_power', '0')]:
            (p / key).write_text(value)
        return p

    def brightness(self):
        return int((self.p / 'brightness').read_text())

    def test_roundtrip_repeat_and_restart(self):
        self.assertEqual(self.c.device(), self.p)
        self.assertTrue(self.c.power(True)['asleep'])
        self.assertEqual(self.brightness(), 0)
        self.assertEqual(int((self.p / 'bl_power').read_text()), 4)
        self.c.power(True)
        restarted = display.BacklightController(self.root / 'state')
        self.assertTrue(restarted.power(False)['changed'])
        self.assertEqual(self.brightness(), 19)
        self.assertEqual(int((self.p / 'bl_power').read_text()), 0)

    def test_expiry_and_clock_rollback(self):
        for offset in (31, -100):
            self.c.power(True)
            with patch.object(display.time, 'time', return_value=time.time() + offset):
                self.c.guardian_tick()
            self.assertEqual(self.brightness(), 19)

    def test_active_lease_and_read_only_status(self):
        self.c.power(True)
        deadline = self.c.read_state()['deadline']
        self.c.status()
        self.c.guardian_tick()
        self.assertEqual(self.c.read_state()['deadline'], deadline)
        self.assertEqual(self.brightness(), 0)

    def test_missing_and_stale_guardian(self):
        heartbeat = self.root / 'state/guardian'
        old = time.time() - 10
        os.utime(heartbeat, (old, old))
        self.assertIn('error', self.c.power(True))
        heartbeat.unlink()
        self.assertIn('error', self.c.power(True))
        self.assertEqual(self.brightness(), 19)

    def test_ambiguous_unsafe_and_explicit_selection(self):
        self.panel('6-0045')
        self.assertIsNone(self.c.device())
        for name in ('../etc/shadow', '.', '..', '/tmp/panel', 'missing'):
            os.environ['FAMILY_CALENDAR_BACKLIGHT_DEVICE'] = name
            self.assertIsNone(self.c.device())
            self.assertIn('error', self.c.power(True))
        os.environ['FAMILY_CALENDAR_BACKLIGHT_DEVICE'] = '4-0045'
        self.assertEqual(self.c.device(), self.p)

    def test_no_panel_and_brightness_only(self):
        (self.p / 'bl_power').unlink()
        self.assertTrue(self.c.power(True)['asleep'])
        self.c.power(False)
        self.assertEqual(self.brightness(), 19)
        for p in self.p.iterdir():
            p.unlink()
        self.p.rmdir()
        self.assertEqual(self.c.power(True)['mode'], 'unavailable')
        self.assertFalse(self.c.power(False)['changed'])

    def test_partial_failure_and_restore_retry(self):
        write = self.c.write
        def fail_power(panel, attr, value):
            if attr == 'bl_power' and value == 4:
                raise PermissionError('denied')
            write(panel, attr, value)
        with patch.object(self.c, 'write', side_effect=fail_power):
            self.assertIn('error', self.c.power(True))
        self.assertEqual(self.brightness(), 19)
        self.c.power(True)
        with patch.object(self.c, 'write', side_effect=PermissionError('denied')):
            self.assertTrue(self.c.power(False)['recovery_pending'])
        with patch.object(display.time, 'time', return_value=time.time() + 31):
            self.c.guardian_tick()
        self.assertEqual(self.brightness(), 19)

    def test_ddcci_explicit_only(self):
        self.panel('ddcci1')
        self.assertEqual(self.c.device(), self.p)
        os.environ['FAMILY_CALENDAR_BACKLIGHT_DEVICE'] = 'ddcci1'
        self.assertEqual(self.c.device().name, 'ddcci1')

if __name__ == '__main__':
    unittest.main()
