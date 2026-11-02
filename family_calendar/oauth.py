"""Local-only Google OAuth, initiated entirely inside PiCalendar Settings.

The end user must supply their own Google Cloud OAuth 'Desktop app' client JSON
once. No password is collected and OAuth credentials stay on this Raspberry Pi.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path

from .google_sync import SCOPES, save_credentials
from .storage import SECRETS_FILE

_LOCK = threading.Lock()
_PENDING: dict = {}
_SESSION_TTL = 600


def client_configured() -> bool:
    return SECRETS_FILE.is_file()


def save_client_file(content: bytes) -> None:
    if not content or len(content) > 32_000:
        raise ValueError('Expected a Google OAuth Desktop client JSON under 32 KB.')
    try:
        parsed = json.loads(content)
        info = parsed['installed']
        if not isinstance(info, dict) or not all(info.get(k) for k in ('client_id', 'client_secret', 'auth_uri', 'token_uri')):
            raise ValueError('Incomplete OAuth client.')
        if info['auth_uri'] != 'https://accounts.google.com/o/oauth2/auth' and info['auth_uri'] != 'https://accounts.google.com/o/oauth2/v2/auth':
            raise ValueError('Unexpected authorization URL.')
        if info['token_uri'] != 'https://oauth2.googleapis.com/token' and info['token_uri'] != 'https://www.googleapis.com/oauth2/v4/token':
            raise ValueError('Unexpected token URL.')
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError('Select a Google Cloud OAuth Desktop client JSON, not an API key.') from exc
    SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SECRETS_FILE.with_suffix('.tmp')
    try:
        tmp.write_bytes(content)
        os.chmod(tmp, 0o600)
        tmp.replace(SECRETS_FILE)
    finally:
        tmp.unlink(missing_ok=True)


def _redirect_uri(port: int) -> str:
    if not 1 <= port <= 65535:
        raise ValueError('Invalid local port')
    return f'http://127.0.0.1:{port}/api/google/callback'


def start_authorization(port: int) -> str:
    if not client_configured():
        raise ValueError('Upload your Google OAuth Desktop client JSON in Settings first.')
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_secrets_file(str(SECRETS_FILE), scopes=SCOPES,
                                         redirect_uri=_redirect_uri(port), autogenerate_code_verifier=True)
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    with _LOCK:
        _PENDING.clear()
        _PENDING.update(flow=flow, state=state, created=time.monotonic())
    return url


def complete_authorization(state: str, callback_url: str) -> None:
    with _LOCK:
        pending = dict(_PENDING)
        _PENDING.clear()
    if not pending or not state or not secrets.compare_digest(str(pending['state']), state):
        raise ValueError('Google sign-in session was not recognized. Start again in Settings.')
    if time.monotonic() - pending['created'] > _SESSION_TTL:
        raise ValueError('Google sign-in timed out. Start again in Settings.')
    flow = pending['flow']
    flow.fetch_token(authorization_response=callback_url)
    if not flow.credentials or not flow.credentials.refresh_token:
        raise ValueError('Google did not return offline authorization. Reconnect and approve access.')
    save_credentials(flow.credentials)
