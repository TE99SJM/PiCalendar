"""No real Google login or secrets used in these tests."""
from __future__ import annotations

import json
from fastapi.testclient import TestClient
from family_calendar.main import app
from family_calendar import oauth
from family_calendar.storage import SECRETS_FILE


def test_oauth_client_upload_validation_and_status():
    with TestClient(app) as client:
        bad = client.post('/api/google/client', files={'file': ('wrong.json', b'{"web":{}}', 'application/json')})
        assert bad.status_code == 422
        assert not SECRETS_FILE.exists()
        correct = {'installed': {
            'client_id':'test-client-id', 'client_secret':'test-secret',
            'auth_uri':'https://accounts.google.com/o/oauth2/auth',
            'token_uri':'https://oauth2.googleapis.com/token'
        }}
        valid = client.post('/api/google/client', files={'file': ('client.json',json.dumps(correct).encode(),'application/json')})
        assert valid.status_code == 200,valid.text
        assert client.get('/api/status').json()['google_client_configured'] is True
        assert oct(SECRETS_FILE.stat().st_mode & 0o777) == '0o600'
        assert 'test-secret' not in client.get('/api/status').text
        assert 'test-secret' not in client.get('/api/settings').text


def test_login_url_and_callback(monkeypatch):
    called=[]
    monkeypatch.setattr(oauth, 'start_authorization', lambda port: f'https://accounts.google.com/o/oauth2/v2/auth?client_id=test&port={port}')
    monkeypatch.setattr(oauth, 'complete_authorization', lambda state,url: called.append((state,url)))
    monkeypatch.setattr('family_calendar.main.sync_google', lambda: {'connected': True})
    with TestClient(app) as client:
        r=client.post('/api/google/start')
        assert r.status_code==200
        assert r.json()['authorization_url'].startswith('https://accounts.google.com/')
        # OAuth redirects to a local URL; never iframe the Google sign-in page.
        r=client.get('/api/google/callback?state=test&code=google-authorization-code',follow_redirects=False)
        assert r.status_code==303
        assert r.headers['location']=='/?google=connected'
        assert called and 'state=test' in called[0][1]


def test_callback_errors_not_exposed(monkeypatch):
    def fail(*args):
        raise ValueError('bad state')
    monkeypatch.setattr(oauth,'complete_authorization',fail)
    with TestClient(app) as client:
        r=client.get('/api/google/callback?state=wrong&code=code',follow_redirects=False)
        assert r.status_code==303 and r.headers['location']=='/?google=error'
