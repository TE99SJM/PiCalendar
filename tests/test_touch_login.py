"""No hosting or actual Google credentials required for UI/setup tests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_touch_button_explains_missing_setup():
    app = (ROOT / 'static/app.js').read_text()
    assert 'id="settings-google-login"' in app
    assert 'disabled title="Google sign-in not provisioned"' not in app
    assert 'if(!state.status.google_client_configured)' in app
    assert "result=await api('/api/google/start'" in app


def test_developer_only_setup():
    src = (ROOT / 'tools/configure-google-client.sh').read_text()
    assert 'config/google-oauth-desktop.json' in src
    assert 'os.chmod(temp, 0o600)' in src
    assert "all(info.get(k) for k in ('client_id', 'auth_uri', 'token_uri'))" in src


def test_original_kiosk_unchanged():
    kiosk = (ROOT / 'run-kiosk.sh').read_text()
    assert '--kiosk' in kiosk
    assert '--ozone-platform=wayland' in kiosk
