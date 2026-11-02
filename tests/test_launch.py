"""Git checkout must remain bootable in Raspberry Pi's systemd kiosk."""
from pathlib import Path

from fastapi.testclient import TestClient
from family_calendar.main import app

ROOT = Path(__file__).resolve().parent.parent


def test_executable_launchers():
    for path in ('run.sh', 'run-kiosk.sh', 'startup/launch-console-kiosk.sh'):
        assert (ROOT / path).stat().st_mode & 0o111, f'{path} is not executable'


def test_systemd_uses_shell_launcher():
    text = (ROOT / 'install.sh').read_text(encoding='utf-8')
    assert 'ExecStart=/usr/bin/bash ${APP_DIR}/run.sh' in text
    assert 'sudo systemctl restart family-calendar.service' in text


def test_local_server_status_and_home():
    with TestClient(app) as client:
        response = client.get('/api/status')
        assert response.status_code == 200
        assert response.json()['version'] == '0.5.1'
        assert client.get('/').status_code == 200
