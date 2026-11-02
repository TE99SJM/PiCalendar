"""Google Calendar installed-app sign-in.

The PiCalendar publisher configures a Google OAuth Desktop client once. The
person using the kiosk only selects Sign in with Google in Settings. Google's
own browser page handles account/password/consent; tokens remain on this Pi.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .google_sync import SCOPES, save_credentials
from .storage import PROJECT_ROOT, SECRETS_FILE

_LOCK = threading.Lock()
_PENDING: dict = {}
_SESSION_TTL = 600
_AUTH_URI = 'https://accounts.google.com/o/oauth2/v2/auth'
_TOKEN_URI = 'https://oauth2.googleapis.com/token'
_BUNDLED_CLIENT_FILE = PROJECT_ROOT / 'config' / 'google-oauth-desktop.json'


def _validate_client(config: dict) -> dict:
    if not isinstance(config, dict) or not isinstance(config.get('installed'), dict):
        raise ValueError('PiCalendar publisher must configure a Google Desktop OAuth client.')
    info = config['installed']
    client_id = info.get('client_id')
    if not isinstance(client_id, str) or not client_id.strip():
        raise ValueError('Google OAuth client ID is missing.')
    if info.get('auth_uri', _AUTH_URI) not in (_AUTH_URI, 'https://accounts.google.com/o/oauth2/auth'):
        raise ValueError('Google authorization endpoint is invalid.')
    if info.get('token_uri', _TOKEN_URI) not in (_TOKEN_URI, 'https://www.googleapis.com/oauth2/v4/token'):
        raise ValueError('Google token endpoint is invalid.')
    return {'installed': {
        'client_id': client_id,
        'client_secret': info.get('client_secret', ''),
        'auth_uri': _AUTH_URI,
        'token_uri': _TOKEN_URI,
        'redirect_uris': ['http://127.0.0.1'],
    }}


def _client_config() -> dict:
    """Developer-provisioned environment or local file; legacy installs still work."""
    client_id = os.environ.get('FAMILY_CALENDAR_GOOGLE_CLIENT_ID', '').strip()
    if client_id:
        return _validate_client({'installed': {
            'client_id': client_id,
            'client_secret': os.environ.get('FAMILY_CALENDAR_GOOGLE_CLIENT_SECRET', ''),
        }})
    custom = os.environ.get('FAMILY_CALENDAR_GOOGLE_CLIENT_FILE', '').strip()
    candidates = ([Path(custom).expanduser()] if custom else []) + [_BUNDLED_CLIENT_FILE, SECRETS_FILE]
    for file in candidates:
        if file.is_file():
            return _validate_client(json.loads(file.read_text(encoding='utf-8')))
    raise ValueError('Google Sign-In must be enabled once by the PiCalendar publisher.')


def client_configured() -> bool:
    try:
        _client_config()
        return True
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _redirect_uri(port: int) -> str:
    if not 1 <= port <= 65535:
        raise ValueError('Invalid local port.')
    return f'http://127.0.0.1:{port}/api/google/callback'


def start_authorization(port: int) -> str:
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES,
                                   redirect_uri=_redirect_uri(port),
                                   autogenerate_code_verifier=True)
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    with _LOCK:
        _PENDING.clear()
        _PENDING.update(flow=flow, state=state, created=time.monotonic(), port=port)
    return url


def complete_authorization(state: str, callback_url: str) -> None:
    with _LOCK:
        pending = dict(_PENDING)
        if not pending or not state or not secrets.compare_digest(str(pending['state']), state):
            raise ValueError('Unrecognized Google sign-in session; retry from Settings.')
        if time.monotonic() - pending['created'] > _SESSION_TTL:
            _PENDING.clear()
            raise ValueError('Google sign-in timed out; retry from Settings.')
        target = urlsplit(callback_url)
        if (target.scheme != 'http' or target.hostname != '127.0.0.1'
                or target.port != pending['port'] or target.path != '/api/google/callback'):
            raise ValueError('Invalid Google OAuth redirect.')
        _PENDING.clear()
    flow = pending['flow']
    params = parse_qs(target.query, keep_blank_values=True)
    codes = params.get('code', [])
    if len(codes) != 1 or not codes[0]:
        raise ValueError('Google did not return an authorization code. Try again.')
    callback_states = params.get('state', [])
    if len(callback_states) != 1 or not secrets.compare_digest(callback_states[0], state):
        raise ValueError('Invalid Google sign-in state. Retry from Settings.')
    # Google permits HTTP loopback redirect URIs for Desktop OAuth clients.
    # OAuthlib rejects such URLs when parsing authorization_response directly.
    # Pass the verified code; the token exchange still uses Google's HTTPS URL
    # and retains the OAuth code verifier (PKCE) from the original Flow.
    flow.fetch_token(code=codes[0])
    if not flow.credentials or not flow.credentials.refresh_token:
        raise ValueError('Google did not provide offline access; reconnect in Settings.')
    save_credentials(flow.credentials)
