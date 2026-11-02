"""Two-way Google Calendar sync. User credentials never leave the Pi."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .storage import TOKEN_FILE, db, get_settings, set_settings, utc_now

SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.calendarlist.readonly',
]
_SYNC_LOCK = threading.Lock()


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    if not TOKEN_FILE.is_file():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
    if not creds.valid:
        raise RuntimeError('Google authorization expired. Run python connect_google.py again.')
    return creds


def save_credentials(creds) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = TOKEN_FILE.with_suffix('.tmp')
    temp.write_text(creds.to_json(), encoding='utf-8')
    os.chmod(temp, 0o600)
    temp.replace(TOKEN_FILE)


def connected() -> bool:
    return TOKEN_FILE.is_file()


def _service():
    from googleapiclient.discovery import build
    creds = _credentials()
    if not creds:
        raise RuntimeError('Google Calendar not connected. Run python connect_google.py on your Pi.')
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


def _all_pages(method, items_key: str, **kwargs):
    token = None
    while True:
        response = method(**kwargs, pageToken=token).execute(num_retries=2)
        yield from response.get(items_key, [])
        token = response.get('nextPageToken')
        if not token:
            break


def _google_payload(row: dict) -> dict:
    if row['all_day']:
        start = {'date': row['start'][:10]}
        end = {'date': row['end'][:10]}
    else:
        start = {'dateTime': row['start']}
        end = {'dateTime': row['end']}
    return {'summary': row['title'], 'description': row['description'], 'start': start, 'end': end}


def _send_changes(service) -> None:
    from googleapiclient.errors import HttpError
    with db() as con:
        changes = [dict(row) for row in con.execute(
            "SELECT * FROM events WHERE pending IS NOT NULL ORDER BY updated_at")]
    for row in changes:
        action = row['pending']
        cal_id = row['calendar_id']
        if cal_id == 'local':
            continue
        if action == 'create':
            result = service.events().insert(calendarId=cal_id, body=_google_payload(row)).execute(num_retries=2)
            with db() as con:
                con.execute("UPDATE events SET google_event_id=?,pending=NULL WHERE id=?", (result['id'], row['id']))
        elif action == 'update':
            service.events().patch(calendarId=cal_id, eventId=row['google_event_id'],
                                   body=_google_payload(row)).execute(num_retries=2)
            with db() as con:
                con.execute('UPDATE events SET pending=NULL WHERE id=?', (row['id'],))
        elif action == 'delete':
            try:
                service.events().delete(calendarId=cal_id, eventId=row['google_event_id']).execute(num_retries=2)
            except HttpError as exc:
                if exc.resp.status not in (404, 410):
                    raise
            with db() as con:
                con.execute('DELETE FROM events WHERE id=?', (row['id'],))


def _fetch_calendar_list(service) -> list[str]:
    writable = []
    remote_ids = set()
    for item in _all_pages(service.calendarList().list, 'items'):
        cal_id = item['id']
        remote_ids.add(cal_id)
        can_edit = item.get('accessRole') in ('owner', 'writer')
        name = item.get('summaryOverride') or item.get('summary', 'Google Calendar')
        color = item.get('backgroundColor') or '#4a88e8'
        with db() as con:
            con.execute('''
                INSERT INTO calendars(id,name,color,editable,selected) VALUES(?,?,?,?,1)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,color=excluded.color,editable=excluded.editable
            ''', (cal_id, name, color, int(can_edit)))
        if can_edit:
            writable.append(cal_id)
    return list(remote_ids)


def _download_events(service, cal_id: str, time_min: str, time_max: str) -> None:
    downloaded = set()
    results = _all_pages(service.events().list, 'items', calendarId=cal_id,
                         timeMin=time_min, timeMax=time_max,
                         singleEvents=True, maxResults=1000, showDeleted=False)
    for event in results:
        if event.get('status') == 'cancelled':
            continue
        start_data = event.get('start', {})
        end_data = event.get('end', {})
        start = start_data.get('dateTime') or start_data.get('date')
        end = end_data.get('dateTime') or end_data.get('date')
        if not start or not end:
            continue
        google_id = event['id']
        downloaded.add(google_id)
        with db() as con:
            existing = con.execute('SELECT id,pending FROM events WHERE calendar_id=? AND google_event_id=?',
                                   (cal_id, google_id)).fetchone()
            if existing and existing['pending']:
                continue
            if existing:
                con.execute('''UPDATE events SET title=?,start=?,end=?,all_day=?,description=?,updated_at=?
                               WHERE id=?''', (event.get('summary', '(Untitled)'), start, end,
                                              int('date' in start_data), event.get('description', ''),
                                              utc_now(), existing['id']))
            else:
                con.execute('''INSERT INTO events
                    (id,google_event_id,calendar_id,title,start,end,all_day,description,source,pending,updated_at)
                    VALUES(?,?,?,?,?,?,?,?, 'google',NULL,?)''',
                    (str(uuid.uuid4()), google_id, cal_id, event.get('summary', '(Untitled)'),
                     start, end, int('date' in start_data), event.get('description', ''), utc_now()))
    # Remove remote events that were deleted in Google, but only inside the fetched time window.
    # The latest user edits (pending) are intentionally protected from removal.
    with db() as con:
        rows = con.execute('''SELECT id,google_event_id FROM events
             WHERE calendar_id=? AND source='google' AND pending IS NULL
             AND start<? AND end>?''', (cal_id, time_max, time_min)).fetchall()
        for row in rows:
            if row['google_event_id'] not in downloaded:
                con.execute('DELETE FROM events WHERE id=?', (row['id'],))


def sync_google() -> dict:
    """Send queued touchscreen edits first, then import changes from Google."""
    if not connected():
        return {'connected': False, 'message': 'Connect Google in Settings when ready.'}
    if not _SYNC_LOCK.acquire(blocking=False):
        return {'connected': True, 'message': 'Sync already running.'}
    try:
        service = _service()
        remote_ids = _fetch_calendar_list(service)
        _send_changes(service)
        today = datetime.now(timezone.utc)
        # Keep a broad two-year history locally for offline access, but only
        # re-fetch the full past window weekly. Routine sync is quicker.
        settings = get_settings()
        old_stamp = settings.get('last_history_sync', '')
        try:
            history_age = today - datetime.fromisoformat(old_stamp)
        except (ValueError, TypeError):
            history_age = timedelta(days=999)
        full_history = history_age >= timedelta(days=7)
        past_days = max(60, int(os.environ.get('FAMILY_CALENDAR_HISTORY_DAYS', '730'))) if full_history else 60
        ahead_days = max(90, int(os.environ.get('FAMILY_CALENDAR_FUTURE_DAYS', '730')))
        time_min = (today - timedelta(days=past_days)).isoformat()
        time_max = (today + timedelta(days=ahead_days)).isoformat()
        with db() as con:
            selected = {r['id'] for r in con.execute('SELECT id FROM calendars WHERE selected=1')}
        for cal_id in remote_ids:
            if cal_id in selected:
                _download_events(service, cal_id, time_min, time_max)
        stamp = utc_now()
        changed = {'last_sync': stamp, 'last_error': ''}
        if full_history:
            changed['last_history_sync'] = stamp
        set_settings(changed)
        return {'connected': True, 'last_sync': stamp, 'message': 'Synced successfully.'}
    except Exception as exc:
        message = f'{type(exc).__name__}: {str(exc)[:300]}'
        set_settings({'last_error': message})
        return {'connected': True, 'error': message}
    finally:
        _SYNC_LOCK.release()
