"""Touch-first, local-only family calendar server for Raspberry Pi 5."""
from __future__ import annotations

import asyncio
import io
import json
import os
import socket
import threading
import time
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from PIL import Image, ImageOps, UnidentifiedImageError

from .google_sync import connected, sync_google, disconnect_google
from . import oauth
from .display import backlight
from .storage import (
    PHOTOS_DIR, PROJECT_ROOT, db, event_list, get_calendars, get_settings,
    init_db, set_settings, utc_now,
)

STATIC_DIR = PROJECT_ROOT / 'static'
WEATHER_CACHE = {'key': None, 'at': 0.0, 'data': None}
NETWORK_CACHE = {'at': 0.0, 'online': False}
NETWORK_LOCK = threading.Lock()


def can_reach_google() -> bool:
    # Network check is advisory only. It must never interrupt local access.
    with NETWORK_LOCK:
        if time.monotonic() - NETWORK_CACHE['at'] < 25:
            return NETWORK_CACHE['online']
        try:
            sock = socket.create_connection(('www.googleapis.com', 443), timeout=0.65)
            sock.close()
            online = True
        except OSError:
            online = False
        NETWORK_CACHE.update(at=time.monotonic(), online=online)
        return online



async def sync_loop():
    await asyncio.sleep(20)
    while True:
        await asyncio.to_thread(sync_google)
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = None
    if os.environ.get('FAMILY_CALENDAR_DISABLE_SYNC') != '1':
        task = asyncio.create_task(sync_loop())
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title='Family Calendar for Raspberry Pi', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')
# Only local static photos are served. Generated filenames prevent path traversal.
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/photos', StaticFiles(directory=str(PHOTOS_DIR)), name='photos')


class EventInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start: str
    end: str
    all_day: bool = False
    description: str = Field(default='', max_length=10000)
    calendar_id: str = 'local'

    @field_validator('start', 'end')
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            if len(value) == 10:
                date.fromisoformat(value)
            else:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    raise ValueError('Timed events require an offset')
        except (ValueError, TypeError):
            raise ValueError('Expected YYYY-MM-DD or an ISO datetime with timezone')
        return value


class ChoreInput(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    assignee: str = Field(default='', max_length=60)
    repeat: str = 'once'
    due_on: str = ''


class GroceryInput(BaseModel):
    title: str = Field(min_length=1, max_length=150)


class MealInput(BaseModel):
    day: date
    label: str = Field(max_length=200)


class SettingsInput(BaseModel):
    family_name: str = Field(default='Our Family', min_length=1, max_length=70)
    weather_location: str = Field(default='', max_length=100)
    weather_latitude: str = ''
    weather_longitude: str = ''


def local_today() -> date:
    return datetime.now(ZoneInfo(os.environ.get("FAMILY_CALENDAR_TIMEZONE", "America/Chicago"))).date()


def fetch_one(table: str, item_id: str):
    if table not in {'events', 'chores', 'groceries'}:
        raise ValueError('Unknown table')
    with db() as con:
        row = con.execute(f'SELECT * FROM {table} WHERE id=?', (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail='Not found')
    return dict(row)


def validate_event(data: EventInput) -> None:
    if data.all_day:
        if len(data.start) != 10 or len(data.end) != 10:
            raise HTTPException(422, 'All-day events require YYYY-MM-DD dates')
    else:
        if len(data.start) == 10 or len(data.end) == 10:
            raise HTTPException(422, 'Timed events require datetimes with timezone')
    if data.start >= data.end:
        raise HTTPException(422, 'End must be after start')


def check_calendar(cal_id: str) -> None:
    match = next((c for c in get_calendars() if c['id'] == cal_id), None)
    if not match:
        raise HTTPException(422, 'Select a valid calendar')
    if not match['editable']:
        raise HTTPException(422, 'That Google Calendar is read-only')


@app.get('/')
def index():
    return FileResponse(STATIC_DIR / 'index.html')


@app.get('/api/status')
def status():
    settings = get_settings()
    return {'version': '0.3.3', 'google_connected': connected(), 'google_client_configured': oauth.client_configured(), 'google_online': can_reach_google(),
            'local_storage': True,
            'last_sync': settings.get('last_sync', ''), 'last_error': settings.get('last_error', '')}



@app.post('/api/google/start')
def google_authorize_start():
    """Return Google authorization URL; front end opens it top-level in Chromium."""
    try:
        port = int(os.environ.get('FAMILY_CALENDAR_PORT', '8080'))
        url = oauth.start_authorization(port)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {'authorization_url': url}


@app.post('/api/google/disconnect')
def google_disconnect(request: Request):
    """Remove tokens and downloaded Google events; retain all local data."""
    origin = request.headers.get('origin')
    expected = f"http://127.0.0.1:{os.environ.get('FAMILY_CALENDAR_PORT', '8080')}"
    if origin and origin != expected:
        raise HTTPException(403, 'Use the local PiCalendar interface.')
    disconnect_google()
    return {'connected': False}


@app.get('/api/google/callback')
async def google_authorize_callback(request: Request, state: str = '', error: str = ''):
    if error:
        set_settings({'last_error': 'Google authorization was not approved.'})
        return RedirectResponse('/?google=error', status_code=303)
    try:
        # Credential exchange makes an outbound HTTPS request to Google.
        if request.url.hostname != '127.0.0.1':
            raise ValueError('Google OAuth redirect must use local loopback.')
        await asyncio.to_thread(oauth.complete_authorization, state, str(request.url))
        set_settings({'last_error': ''})
        # The browser performs the first Google sync after redirect.
        # Avoid overlapping sync jobs so the first calendar refresh is complete.
    except Exception as exc:
        set_settings({'last_error': f'Google login: {type(exc).__name__}: {str(exc)[:180]}'})
        return RedirectResponse('/?google=error', status_code=303)
    return RedirectResponse('/?google=connected', status_code=303)

@app.get('/api/display/status')
def display_status():
    """Whether physical screen backlight switching is configured on this Pi."""
    return backlight.status()


@app.post('/api/display/sleep')
def display_sleep():
    """Blank backlight where supported; web overlay still covers the screen."""
    return backlight.power(asleep=True)


@app.post('/api/display/wake')
def display_wake():
    """Restore backlight after a double tap on the overlay."""
    return backlight.power(asleep=False)


@app.get('/api/settings')
def settings_get():
    return get_settings()


@app.put('/api/settings')
def settings_put(value: SettingsInput):
    values = value.model_dump()
    for key, limits in (('weather_latitude', (-90, 90)), ('weather_longitude', (-180, 180))):
        if values[key]:
            try:
                n = float(values[key])
            except ValueError:
                raise HTTPException(422, f'{key} must be numeric')
            if not limits[0] <= n <= limits[1]:
                raise HTTPException(422, f'{key} out of range')
    set_settings(values)
    WEATHER_CACHE['key'] = None
    return get_settings()


@app.get('/api/calendars')
def calendars_get():
    return get_calendars()


@app.patch('/api/calendars/{calendar_id:path}')
def calendar_patch(calendar_id: str, selected: bool):
    if calendar_id == 'local' and not selected:
        raise HTTPException(422, 'The local calendar must remain visible')
    with db() as con:
        cursor = con.execute('UPDATE calendars SET selected=? WHERE id=?', (int(selected), calendar_id))
        if not cursor.rowcount:
            raise HTTPException(404, 'Calendar not found')
    return {'ok': True}


@app.get('/api/events')
def events_get(start: str = Query(...), end: str = Query(...)):
    try:
        date.fromisoformat(start[:10]); date.fromisoformat(end[:10])
    except ValueError:
        raise HTTPException(422, 'Invalid date range')
    return event_list(start, end)


@app.post('/api/events', status_code=201)
def event_create(event: EventInput):
    validate_event(event)
    check_calendar(event.calendar_id)
    item_id = str(uuid.uuid4())
    source = 'local' if event.calendar_id == 'local' else 'google'
    pending = None if source == 'local' else 'create'
    with db() as con:
        con.execute('''INSERT INTO events(id,calendar_id,title,start,end,all_day,description,source,pending,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    (item_id, event.calendar_id, event.title.strip(), event.start, event.end,
                     int(event.all_day), event.description, source, pending, utc_now()))
    return {'id': item_id, 'pending': pending}


@app.put('/api/events/{item_id}')
def event_update(item_id: str, event: EventInput):
    original = fetch_one('events', item_id)
    if original['calendar_id'] != event.calendar_id:
        raise HTTPException(422, 'Changing calendars is not yet supported; create a new event instead')
    validate_event(event)
    pending = original['pending']
    if original['source'] == 'google' and pending != 'create':
        pending = 'update'
    with db() as con:
        con.execute('''UPDATE events SET title=?,start=?,end=?,all_day=?,description=?,pending=?,updated_at=?
                       WHERE id=?''', (event.title.strip(), event.start, event.end,
                                      int(event.all_day), event.description, pending, utc_now(), item_id))
    return {'ok': True, 'pending': pending}


@app.delete('/api/events/{item_id}')
def event_delete(item_id: str):
    original = fetch_one('events', item_id)
    with db() as con:
        if original['source'] == 'local' or original['pending'] == 'create':
            con.execute('DELETE FROM events WHERE id=?', (item_id,))
        else:
            con.execute("UPDATE events SET pending='delete',updated_at=? WHERE id=?", (utc_now(), item_id))
    return {'ok': True}


@app.post('/api/sync')
async def sync_now():
    result = await asyncio.to_thread(sync_google)
    if result.get('error'):
        raise HTTPException(502, result['error'])
    return result


@app.get('/api/chores')
def chores_get():
    with db() as con:
        return [dict(row) for row in con.execute('SELECT * FROM chores ORDER BY created_at DESC')]


@app.post('/api/chores', status_code=201)
def chore_create(value: ChoreInput):
    if value.repeat not in ('once', 'daily', 'weekly'):
        raise HTTPException(422, 'Repeat must be once, daily, or weekly')
    if value.due_on:
        try:
            date.fromisoformat(value.due_on)
        except ValueError:
            raise HTTPException(422, 'Invalid due date')
    item_id = str(uuid.uuid4())
    with db() as con:
        con.execute('INSERT INTO chores VALUES(?,?,?,?,?,?,?)',
                    (item_id, value.title.strip(), value.assignee.strip(), value.repeat,
                     value.due_on, '', utc_now()))
    return {'id': item_id}


@app.patch('/api/chores/{item_id}')
def chore_complete(item_id: str, done: bool):
    fetch_one('chores', item_id)
    with db() as con:
        con.execute('UPDATE chores SET done_on=? WHERE id=?',
                    (local_today().isoformat() if done else '', item_id))
    return {'ok': True}


@app.delete('/api/chores/{item_id}')
def chore_delete(item_id: str):
    fetch_one('chores', item_id)
    with db() as con:
        con.execute('DELETE FROM chores WHERE id=?', (item_id,))
    return {'ok': True}


@app.get('/api/groceries')
def groceries_get():
    with db() as con:
        return [dict(row) for row in con.execute('SELECT * FROM groceries ORDER BY checked,created_at DESC')]


@app.post('/api/groceries', status_code=201)
def grocery_create(value: GroceryInput):
    item_id = str(uuid.uuid4())
    with db() as con:
        con.execute('INSERT INTO groceries VALUES(?,?,0,?)', (item_id, value.title.strip(), utc_now()))
    return {'id': item_id}


@app.patch('/api/groceries/{item_id}')
def grocery_check(item_id: str, checked: bool):
    fetch_one('groceries', item_id)
    with db() as con:
        con.execute('UPDATE groceries SET checked=? WHERE id=?', (int(checked), item_id))
    return {'ok': True}


@app.delete('/api/groceries/{item_id}')
def grocery_delete(item_id: str):
    fetch_one('groceries', item_id)
    with db() as con:
        con.execute('DELETE FROM groceries WHERE id=?', (item_id,))
    return {'ok': True}


@app.get('/api/meals')
def meals_get(start: date, end: date):
    with db() as con:
        return [dict(row) for row in con.execute('SELECT * FROM meals WHERE day>=? AND day<? ORDER BY day',
                                                 (start.isoformat(), end.isoformat()))]


@app.put('/api/meals')
def meals_put(value: MealInput):
    with db() as con:
        if value.label.strip():
            con.execute('INSERT INTO meals(day,label) VALUES(?,?) ON CONFLICT(day) DO UPDATE SET label=excluded.label',
                        (value.day.isoformat(), value.label.strip()))
        else:
            con.execute('DELETE FROM meals WHERE day=?', (value.day.isoformat(),))
    return {'ok': True}


@app.get('/api/photos')
def photo_list():
    files = sorted((p for p in PHOTOS_DIR.glob('*.jpg') if p.is_file()),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return [{'filename': p.name, 'url': '/photos/' + p.name} for p in files]


@app.post('/api/photos', status_code=201)
async def photo_upload(file: UploadFile = File(...)):
    raw = await file.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, 'Photo must be smaller than 8MB')
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.thumbnail((2048, 2048))
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        name = uuid.uuid4().hex + '.jpg'
        image.save(PHOTOS_DIR / name, format='JPEG', quality=85, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(422, 'Unsupported or damaged image')
    return {'filename': name, 'url': '/photos/' + name}


@app.delete('/api/photos/{name}')
def photo_delete(name: str):
    if not name.endswith('.jpg') or len(name) != 36 or not name[:32].isalnum():
        raise HTTPException(422, 'Invalid photo name')
    path = PHOTOS_DIR / name
    if not path.exists():
        raise HTTPException(404, 'Photo not found')
    path.unlink()
    return {'ok': True}


@app.get('/api/weather')
def weather_get():
    import time
    settings = get_settings()
    lat, lon = settings.get('weather_latitude'), settings.get('weather_longitude')
    if not lat or not lon:
        return {'configured': False}
    key = f'{lat},{lon}'
    if WEATHER_CACHE['key'] == key and time.monotonic() - WEATHER_CACHE['at'] < 900:
        return WEATHER_CACHE['data']
    try:
        params = urlencode({'latitude': lat, 'longitude': lon,
                            'current': 'temperature_2m,weather_code,apparent_temperature',
                            'temperature_unit': 'fahrenheit', 'timezone': 'auto'})
        with urlopen('https://api.open-meteo.com/v1/forecast?' + params, timeout=5) as response:
            value = json.loads(response.read(65536))
        current = value['current']
        result = {'configured': True, 'temperature': round(current['temperature_2m']),
                  'feels_like': round(current['apparent_temperature']),
                  'code': current['weather_code'], 'location': settings.get('weather_location', '')}
        WEATHER_CACHE.update({'key': key, 'at': time.monotonic(), 'data': result})
        return result
    except Exception:
        return {'configured': True, 'error': 'Weather temporarily unavailable'}
