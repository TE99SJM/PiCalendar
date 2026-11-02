"""Run locally: python -m pytest -q (after requirements installation)."""
from __future__ import annotations

import io
import os
import tempfile
from datetime import date, timedelta

os.environ['FAMILY_CALENDAR_DATA'] = tempfile.mkdtemp(prefix='family-calendar-test-')
os.environ['FAMILY_CALENDAR_DISABLE_SYNC'] = '1'

from fastapi.testclient import TestClient
from PIL import Image
from family_calendar.main import app
from family_calendar.storage import db


def test_local_calendar_crud():
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert client.get('/api/calendars').json()[0]['id'] == 'local'
        body = {'title':'Hockey practice','calendar_id':'local','start':'2026-11-02T17:00:00+00:00',
                'end':'2026-11-02T18:00:00+00:00','all_day':False,'description':'Bring skates'}
        created=client.post('/api/events',json=body)
        assert created.status_code==201, created.text
        event_id=created.json()['id']
        assert len(client.get('/api/events?start=2026-11-01&end=2026-11-04').json())==1
        body['title']='Rescheduled practice'
        updated=client.put('/api/events/'+event_id,json=body)
        assert updated.status_code == 200
        assert client.get('/api/events?start=2026-11-01&end=2026-11-04').json()[0]['title']=='Rescheduled practice'
        assert client.delete('/api/events/'+event_id).status_code==200
        assert client.get('/api/events?start=2026-11-01&end=2026-11-04').json()==[]
        assert client.post('/api/events',json={**body,'end':body['start']}).status_code==422


def test_google_queue_without_connection():
    with TestClient(app) as client:
        with db() as con:
            con.execute('INSERT OR REPLACE INTO calendars(id,name,color) VALUES(?,?,?)',
                        ('test@example.com','Google test','#beddaf'))
        body={'title':'Dad appointment','calendar_id':'test@example.com',
              'start':'2026-11-02','end':'2026-11-03','all_day':True}
        r=client.post('/api/events',json=body)
        assert r.status_code==201 and r.json()['pending']=='create'
        uid=r.json()['id']
        assert client.put('/api/events/'+uid,json={**body,'title':'Changed'}).json()['pending']=='create'
        assert client.delete('/api/events/'+uid).status_code==200
        with db() as con:
            assert con.execute('SELECT COUNT(*) FROM events WHERE id=?',(uid,)).fetchone()[0]==0
        assert client.post('/api/sync').json()['connected'] is False


def test_chores_shopping_meals_and_photos():
    with TestClient(app) as client:
        r=client.post('/api/chores',json={'title':'Feed chickens','repeat':'daily','assignee':'Everyone'})
        assert r.status_code==201
        cid=r.json()['id']
        assert client.patch(f'/api/chores/{cid}?done=true').status_code==200
        assert client.get('/api/chores').json()[0]['done_on']
        rid=client.post('/api/groceries',json={'title':'Milk'}).json()['id']
        assert client.patch(f'/api/groceries/{rid}?checked=true').status_code==200
        assert client.get('/api/groceries').json()[0]['checked']==1
        assert client.put('/api/meals',json={'day':'2026-11-04','label':'Tacos'}).status_code==200
        assert client.get('/api/meals?start=2026-11-01&end=2026-11-09').json()[0]['label']=='Tacos'
        photo=Image.new('RGB',(64,64),'blue')
        buf=io.BytesIO();photo.save(buf,format='PNG')
        uploaded=client.post('/api/photos',files={'file':('picture.png',buf.getvalue(),'image/png')})
        assert uploaded.status_code==201, uploaded.text
        path=uploaded.json()['url']
        assert client.get(path).status_code==200
        assert client.delete('/api/photos/'+uploaded.json()['filename']).status_code==200
        assert client.post('/api/photos',files={'file':('bad.png',b'not an image','image/png')}).status_code==422


def test_settings_and_filtering():
    with TestClient(app) as client:
        settings={'family_name':'The Family','weather_location':'Minnesota','weather_latitude':'', 'weather_longitude':''}
        assert client.put('/api/settings',json=settings).status_code==200
        assert client.get('/api/settings').json()['family_name']=='The Family'
        assert client.get('/api/weather').json()['configured'] is False
        assert client.put('/api/settings',json={**settings,'weather_latitude':'999'}).status_code==422
        assert client.patch('/api/calendars/local?selected=false').status_code==422
