"""Verify PiCalendar v0.5.1 retains key components of both parents."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def test_integrated_version_and_login():
    assert (ROOT/'VERSION').read_text().strip() == '0.5.1'
    api=(ROOT/'family_calendar/main.py').read_text()
    oauth=(ROOT/'family_calendar/oauth.py').read_text()
    assert "'version': '0.5.1'" in api
    assert "flow.fetch_token(code=codes[0])" in oauth
    assert "OAUTHLIB_INSECURE_TRANSPORT" not in oauth
    assert "def google_authorize_callback" in api

def test_quiet_kiosk_cursor_preserved():
    style=(ROOT/'static/style.css').read_text()
    assert 'cursor: none !important' in style
    assert '.google-login-actions' in style
    assert (ROOT/'startup/install-kiosk-service.sh').is_file()
    assert (ROOT/'startup/99-picalendar-cursor.rules').is_file()

def test_launcher_and_asset_version():
    installer=(ROOT/'install.sh').read_text()
    html=(ROOT/'static/index.html').read_text()
    assert 'ExecStart=/usr/bin/bash ${APP_DIR}/run.sh' in installer
    assert 'sudo systemctl restart family-calendar.service' in installer
    assert '/static/style.css?v=0.5.1' in html
    assert '/static/app.js?v=0.5.1' in html
