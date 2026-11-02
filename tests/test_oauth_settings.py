"""Offline Google sign-in tests (no real Google tokens or network)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from family_calendar import oauth
from family_calendar.main import app
from family_calendar.storage import init_db, db


def test_no_user_client_upload(monkeypatch, tmp_path):
    monkeypatch.delenv('FAMILY_CALENDAR_GOOGLE_CLIENT_ID', raising=False)
    monkeypatch.delenv('FAMILY_CALENDAR_GOOGLE_CLIENT_FILE', raising=False)
    monkeypatch.setattr(oauth, '_BUNDLED_CLIENT_FILE', tmp_path / 'missing.json')
    monkeypatch.setattr(oauth, 'SECRETS_FILE', tmp_path / 'missing-legacy.json')
    assert not oauth.client_configured()
    with TestClient(app) as client:
        assert client.post('/api/google/client', files={'file': ('test.json', '{}')}).status_code == 404
        start = client.post('/api/google/start')
        assert start.status_code == 422
        assert 'publisher' in start.json()['detail']


def test_publisher_configuration_is_not_exposed(monkeypatch):
    monkeypatch.setenv('FAMILY_CALENDAR_GOOGLE_CLIENT_ID', 'test.apps.googleusercontent.com')
    monkeypatch.setenv('FAMILY_CALENDAR_GOOGLE_CLIENT_SECRET', 'do-not-expose')
    assert oauth.client_configured()
    with TestClient(app) as client:
        status = client.get('/api/status')
        assert status.status_code == 200
        assert status.json()['version'] == '0.5.3'
        assert status.json()['google_client_configured']
        assert 'do-not-expose' not in status.text


def test_oauth_callback_and_error_paths(monkeypatch):
    observed = []
    monkeypatch.setattr(oauth, 'start_authorization', lambda port: 'https://accounts.google.com/o/oauth2/v2/auth?client_id=test')
    monkeypatch.setattr(oauth, 'complete_authorization', lambda state, url: observed.append((state, url)))
    monkeypatch.setattr('family_calendar.main.sync_google', lambda: {'connected': True})
    with TestClient(app) as client:
        assert client.post('/api/google/start').status_code == 200
        response = client.get('/api/google/callback?code=abc&state=valid', follow_redirects=False,
                              headers={'host': '127.0.0.1:8080'})
        assert response.status_code == 303
        assert response.headers['location'] == '/?google=connected'
        assert observed and observed[0][0] == 'valid'
        response = client.get('/api/google/callback?error=access_denied', follow_redirects=False,
                              headers={'host': '127.0.0.1:8080'})
        assert response.headers['location'] == '/?google=error'


def test_oauth_redirect_must_be_loopback(monkeypatch):
    monkeypatch.setattr(oauth, 'complete_authorization', lambda *_: (_ for _ in ()).throw(ValueError('invalid')))
    with TestClient(app) as client:
        response = client.get('/api/google/callback?code=test&state=invalid', follow_redirects=False,
                              headers={'host':'127.0.0.1:8080'})
        assert response.headers['location'] == '/?google=error'


def test_disconnect_preserves_local_data(monkeypatch, tmp_path):
    from family_calendar import storage, google_sync
    monkeypatch.setattr(storage, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path/'calendar.sqlite3')
    monkeypatch.setattr(google_sync, 'TOKEN_FILE', tmp_path/'google-token.json')
    init_db()
    with db() as con:
        con.execute("INSERT INTO calendars(id,name,color) VALUES('remote','Remote','#123456')")
        con.execute("INSERT INTO events(id,calendar_id,title,start,end,updated_at) VALUES('local1','local','Local','2026-01-01','2026-01-02','now')")
        con.execute("INSERT INTO events(id,calendar_id,title,start,end,updated_at) VALUES('remote1','remote','Remote','2026-01-01','2026-01-02','now')")
    (tmp_path/'google-token.json').write_text('fake')
    google_sync.disconnect_google()
    assert not (tmp_path/'google-token.json').exists()
    with db() as con:
        assert [r['id'] for r in con.execute('SELECT id FROM events')] == ['local1']

def test_google_callback_uses_authorization_code_not_http_transport(monkeypatch):
    """Google allows HTTP loopback on Desktop OAuth; token exchange stays HTTPS."""
    from types import SimpleNamespace
    import time

    class FakeFlow:
        credentials = SimpleNamespace(refresh_token='fake-refresh-token')

        def __init__(self):
            self.calls = []

        def fetch_token(self, **kwargs):
            self.calls.append(kwargs)

    fake = FakeFlow()
    saved = []
    monkeypatch.setattr(oauth, 'save_credentials', lambda credentials: saved.append(credentials))

    with oauth._LOCK:
        oauth._PENDING.clear()
        oauth._PENDING.update(flow=fake, state='safe-state', created=time.monotonic(), port=8080)
    oauth.complete_authorization(
        'safe-state',
        'http://127.0.0.1:8080/api/google/callback?state=safe-state&code=abc%2B123'
    )
    assert fake.calls == [{'code': 'abc+123'}]
    assert len(saved) == 1


def test_google_callback_rejects_invalid_state_host_or_missing_code(monkeypatch):
    import time
    from types import SimpleNamespace

    class FakeFlow:
        credentials = SimpleNamespace(refresh_token='fake-refresh-token')

        def fetch_token(self, **kwargs):
            raise AssertionError('Invalid callback must never exchange a token')

    for state, callback in [
        ('wrong', 'http://127.0.0.1:8080/api/google/callback?state=safe&code=abc'),
        ('safe', 'http://example.org:8080/api/google/callback?state=safe&code=abc'),
        ('safe', 'http://127.0.0.1:8080/api/google/callback?state=safe'),
        ('safe', 'http://127.0.0.1:8080/api/google/callback?state=other&code=abc'),
    ]:
        with oauth._LOCK:
            oauth._PENDING.clear()
            oauth._PENDING.update(flow=FakeFlow(), state='safe', created=time.monotonic(), port=8080)
        try:
            oauth.complete_authorization(state, callback)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid OAuth callback was accepted')
