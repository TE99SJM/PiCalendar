"""v0.5.1 cursor guard: no active display or credentials needed."""
from pathlib import Path
from unittest.mock import patch
from startup import cursor_guard as guard
import subprocess

ROOT = Path(__file__).resolve().parent.parent

def test_active_cursor_plane_detection(tmp_path):
    card = tmp_path / "0"
    card.mkdir()
    state = card / "state"
    state.write_text("plane[22]: primary-0\n  crtc=crtc-0\n  fb=32\n"
                     "plane[23]: cursor-0\n  crtc=crtc-0\n  fb=44\n"
                     "  crtc-pos=64x64+0+0\n")
    assert guard.cursor_plane_active(tmp_path) is True
    state.write_text("plane[23]: cursor-0\n  crtc=(null)\n  fb=0\n")
    assert guard.cursor_plane_active(tmp_path) is False
    state.write_text("plane[22]: primary-0\n  crtc=crtc-0\n  fb=32\n")
    assert guard.cursor_plane_active(tmp_path) is None

def test_unready_kiosk_does_not_switch():
    with patch.object(guard.Path, "exists", return_value=True), \
         patch.object(guard, "await_ready", return_value=False), \
         patch.object(guard, "flip_vt") as flip:
        assert guard.run_guard(settling=0) == 1
        flip.assert_not_called()

def test_unobservable_drm_causes_only_one_cycle():
    with patch.object(guard.Path, "exists", return_value=True), \
         patch.object(guard, "await_ready", return_value=True), \
         patch.object(guard, "service_running", return_value=True), \
         patch.object(guard, "cursor_plane_active", return_value=None), \
         patch.object(guard, "flip_vt") as flip, \
         patch.object(guard.time, "sleep"):
        assert guard.run_guard(settling=0) == 0
        flip.assert_called_once()

def test_retry_when_cursor_reappears():
    with patch.object(guard.Path, "exists", return_value=True), \
         patch.object(guard, "await_ready", return_value=True), \
         patch.object(guard, "service_running", return_value=True), \
         patch.object(guard, "cursor_plane_active", side_effect=[True,False,True,False,False]), \
         patch.object(guard, "flip_vt") as flip, \
         patch.object(guard.time, "sleep"):
        assert guard.run_guard(settling=0, attempts=3, confirmation=0) == 0
        assert flip.call_count == 2

def test_restore_kiosk_if_switch_fails():
    def fake(cmd, *args, **kwargs):
        if cmd[:2] == ["chvt", "2"]:
            raise subprocess.CalledProcessError(1, cmd)
    with patch.object(guard.subprocess, "run", side_effect=fake) as run:
        try:
            guard.flip_vt()
        except subprocess.CalledProcessError:
            pass
        assert ["chvt", "1"] in [arg.args[0] for arg in run.call_args_list]

def test_systemd_installer_and_rollback():
    installer = (ROOT / "startup/install-kiosk-service.sh").read_text()
    rollback = (ROOT / "startup/rollback-kiosk-service.sh").read_text()
    assert "picalendar-cursor-guard.service" in installer
    assert "WantedBy=picalendar-kiosk.service" in installer
    assert "PartOf=picalendar-kiosk.service" in installer
    assert "disable --now picalendar-cursor-guard.service" in rollback
