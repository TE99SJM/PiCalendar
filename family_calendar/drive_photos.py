"""Google Drive photo import with its own OAuth token; Calendar tokens stay untouched.

For personal/prototype use. Google's drive.readonly is a RESTRICTED scope and
may require Google verification for deployment outside OAuth testing users.
"""
from __future__ import annotations

import io
import os
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

from . import oauth
from .photo_files import MAX_PHOTO_BYTES, save_photo
from .storage import DATA_DIR

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
TOKEN_PATH = DATA_DIR / 'google-drive-token.json'
AUTH_TTL = 600
_LOCK = threading.Lock()
_PENDING: dict = {}
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{5,200}$')
_ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp', 'image/gif',
                 'image/heic', 'image/heif', 'image/bmp', 'image/tiff'}
_FOLDER_MIME = 'application/vnd.google-apps.folder'

def connected() -> bool:
    return TOKEN_PATH.is_file()

def save_credentials(credentials) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = TOKEN_PATH.with_suffix('.tmp')
    temp.write_text(credentials.to_json(), encoding='utf-8')
    os.chmod(temp, 0o600)
    temp.replace(TOKEN_PATH)

def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    if not connected():
        raise ValueError('Connect Google Drive in Settings first.')
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), DRIVE_SCOPES)
    if creds.scopes and DRIVE_SCOPES[0] not in creds.scopes:
        raise ValueError('Reconnect Drive to grant photo browsing permission.')
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
    if not creds.valid:
        raise ValueError('Google Drive authorization expired; reconnect in Settings.')
    return creds

def _redirect_uri(port: int) -> str:
    if not 1 <= port <= 65535:
        raise ValueError('Invalid PiCalendar port.')
    return f'http://127.0.0.1:{port}/api/drive/callback'

def begin_authorization(port: int) -> str:
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(oauth._client_config(), scopes=DRIVE_SCOPES,
            redirect_uri=_redirect_uri(port), autogenerate_code_verifier=True)
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    with _LOCK:
        _PENDING.clear()
        _PENDING.update(flow=flow, state=state, port=port, created=time.monotonic())
    return url

def finish_authorization(state: str, callback_url: str) -> None:
    url = urlsplit(callback_url)
    with _LOCK:
        session = dict(_PENDING)
        if not session or not state or not secrets.compare_digest(str(session['state']), state):
            raise ValueError('Invalid Drive sign-in session; retry in Settings.')
        _PENDING.clear()
    if time.monotonic() - session['created'] > AUTH_TTL:
        raise ValueError('Drive sign-in timed out.')
    if (url.scheme != 'http' or url.hostname != '127.0.0.1'
            or url.port != session['port'] or url.path != '/api/drive/callback'):
        raise ValueError('Invalid Drive OAuth callback.')
    args = parse_qs(url.query, keep_blank_values=True)
    if args.get('state') != [state] or len(args.get('code', [])) != 1 or not args['code'][0]:
        raise ValueError('Invalid Drive authorization code.')
    flow = session['flow']
    # Google's desktop OAuth permits HTTP loopback redirects, but oauthlib's
    # authorization_response parser rejects HTTP. Validate then pass only code.
    flow.fetch_token(code=args['code'][0])
    if not flow.credentials or not flow.credentials.refresh_token:
        raise ValueError('No offline Drive token; reconnect in Settings.')
    save_credentials(flow.credentials)

def disconnect() -> None:
    TOKEN_PATH.unlink(missing_ok=True)

def _service():
    from googleapiclient.discovery import build
    return build('drive', 'v3', credentials=_credentials(), cache_discovery=False)

def list_files(folder_id: str = 'root', page_token: str = '') -> dict:
    if folder_id != 'root' and not _ID_RE.fullmatch(folder_id):
        raise ValueError('Invalid Drive folder.')
    if page_token and len(page_token) > 2048:
        raise ValueError('Invalid page token.')
    query = (f"'{folder_id}' in parents and trashed = false and "
             f"(mimeType = '{_FOLDER_MIME}' or mimeType contains 'image/')")
    params = dict(q=query, pageSize=100,
                  fields='nextPageToken,files(id,name,mimeType,size)',
                  orderBy='folder,name_natural')
    if page_token:
        params['pageToken'] = page_token
    data = _service().files().list(**params).execute(num_retries=2)
    files = [f for f in data.get('files', [])
             if f.get('mimeType') == _FOLDER_MIME or f.get('mimeType') in _ALLOWED_MIME]
    return {'files': files, 'next_page_token': data.get('nextPageToken', '')}

def import_files(file_ids: list[str]) -> dict:
    from googleapiclient.http import MediaIoBaseDownload
    if not 1 <= len(file_ids) <= 20 or len(set(file_ids)) != len(file_ids):
        raise ValueError('Choose 1–20 distinct photos.')
    if any(not _ID_RE.fullmatch(file_id) for file_id in file_ids):
        raise ValueError('Invalid Drive file ID.')
    service = _service()
    imported, errors = [], []
    for file_id in file_ids:
        try:
            info = service.files().get(fileId=file_id, fields='id,name,mimeType,size',
                                       supportsAllDrives=True).execute(num_retries=2)
            if info.get('mimeType') not in _ALLOWED_MIME:
                raise ValueError('Not a supported photo format.')
            if int(info.get('size') or 0) > MAX_PHOTO_BYTES:
                raise ValueError('Photo exceeds 30 MB.')
            output = io.BytesIO()
            downloader = MediaIoBaseDownload(output,
                 service.files().get_media(fileId=file_id, supportsAllDrives=True),
                 chunksize=1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk(num_retries=2)
                if output.tell() > MAX_PHOTO_BYTES:
                    raise ValueError('Photo exceeds 30 MB.')
            saved = save_photo(output.getvalue())
            imported.append({'source_name': info.get('name', 'Photo'), **saved})
        except Exception as exc:
            # Partial success is reported without leaking token details.
            errors.append({'id': file_id, 'error': str(exc) if isinstance(exc, ValueError)
                           else 'Could not import this photo.'})
    return {'imported': imported, 'errors': errors}
