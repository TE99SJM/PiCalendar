"""Regression checks for the sleep API: software fallback and opt-in sysfs."""
import os
import tempfile
from pathlib import Path

os.environ.setdefault('FAMILY_CALENDAR_DISABLE_SYNC', '1')
from fastapi.testclient import TestClient
from family_calendar.display import BacklightController
from family_calendar.main import app
from family_calendar import display


def test_display_default_software_only(monkeypatch):
    monkeypatch.delenv('FAMILY_CALENDAR_BACKLIGHT_DEVICE', raising=False)
    with TestClient(app) as client:
        assert client.get('/api/display/status').json()['mode'] == 'software'
        assert client.post('/api/display/sleep').json() == {'mode':'software','changed':False}
        assert client.post('/api/display/wake').json() == {'mode':'software','changed':False}


def test_sleep_wake_backlight_roundtrip(tmp_path, monkeypatch):
    root = tmp_path / 'backlights'
    panel = root / 'testpanel'
    panel.mkdir(parents=True)
    (panel / 'brightness').write_text('65\n')
    (panel / 'max_brightness').write_text('100\n')
    monkeypatch.setenv('FAMILY_CALENDAR_BACKLIGHT_DEVICE', 'testpanel')
    monkeypatch.setattr(display, 'BACKLIGHT_ROOT', root)
    controller = BacklightController()
    assert controller.status()['mode'] == 'hardware'
    assert controller.power(asleep=True)['changed']
    assert (panel / 'brightness').read_text() == '0\n'
    assert controller.power(asleep=False)['changed']
    assert (panel / 'brightness').read_text() == '65\n'
    # After a service restart, it falls back to the max brightness.
    (panel / 'brightness').write_text('0\n')
    assert BacklightController().power(asleep=False)['changed']
    assert (panel / 'brightness').read_text() == '100\n'
    monkeypatch.setenv('FAMILY_CALENDAR_BACKLIGHT_DEVICE','../../etc/shadow')
    assert controller.status()['configured'] is False
    assert controller.power(asleep=True)['mode'] == 'software'
