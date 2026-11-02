"""Expiring QR-code LAN photo transfer. Only the upload service is LAN-facing."""
from __future__ import annotations
import io
import ipaddress
import json
import os
import secrets
import subprocess
import time
from pathlib import Path
import qrcode
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from .photo_files import MAX_PHOTO_BYTES, save_photo
from .storage import DATA_DIR

SESSION_FILE = DATA_DIR / 'phone-transfer-session.json'
PORT = int(os.environ.get('FAMILY_CALENDAR_PHONE_PORT', '8787'))
TTL = 900
app = FastAPI(title='PiCalendar photo drop', docs_url=None, redoc_url=None, openapi_url=None)

def _current():
    try:
        return json.loads(SESSION_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return {}

def _valid(token):
    session = _current()
    return len(token)==48 and bool(session.get('token')) and secrets.compare_digest(token,str(session['token'])) and session.get('expires',0)>time.time()

def _ip():
    forced=os.environ.get('FAMILY_CALENDAR_TRANSFER_HOST','').strip()
    if forced:
        addr=ipaddress.ip_address(forced)
        if addr.version!=4 or not addr.is_private or addr.is_loopback or addr.is_link_local:
            raise ValueError('Transfer host must be a private LAN IPv4 address.')
        return forced
    try:
        addresses=subprocess.check_output(['hostname','-I'],text=True,timeout=2).split()
    except (OSError,subprocess.SubprocessError):
        addresses=[]
    selected=[]
    for value in addresses:
        try:
            addr=ipaddress.ip_address(value)
            if addr.version==4 and addr.is_private and not addr.is_loopback and not addr.is_link_local:
                selected.append(value)
        except ValueError:
            pass
    selected.sort(key=lambda v:(0 if v.startswith('192.168.') else 1 if v.startswith('10.') else 2,v))
    if not selected:
        raise ValueError('No LAN address available. Set FAMILY_CALENDAR_TRANSFER_HOST in .env.')
    return selected[0]

def begin_session():
    token=secrets.token_urlsafe(36)
    url=f'http://{_ip()}:{PORT}/p/{token}'
    expires=int(time.time())+TTL
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    temp=SESSION_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps({'token':token,'url':url,'expires':expires}),encoding='utf-8')
    os.chmod(temp,0o600)
    temp.replace(SESSION_FILE)
    return {'url':url,'expires_in':TTL}

def qr_png():
    session=_current()
    if not _valid(session.get('token','')):
        raise ValueError('Create a new QR code in Settings.')
    image=qrcode.make(session['url'])
    output=io.BytesIO()
    image.save(output,format='PNG')
    return output.getvalue()

def end_session():
    SESSION_FILE.unlink(missing_ok=True)

def _check(token):
    if not _valid(token):
        raise HTTPException(403,'This photo link expired. Generate a new QR code on PiCalendar.')

@app.middleware('http')
async def headers(request:Request,call_next):
    size=request.headers.get('content-length','')
    if size.isdigit() and int(size)>12*MAX_PHOTO_BYTES+2_000_000:
        return Response('Upload too large',status_code=413)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    return response

def _page(token,message=''):
    from html import escape
    msg='<p>'+escape(message)+'</p>' if message else ''
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>PiCalendar Photos</title><style>
body{{background:#101825;color:#eef4fc;font-family:system-ui,sans-serif;margin:0;padding:20px}}
main{{max-width:480px;margin:7vh auto;background:#1a2638;border-radius:20px;padding:24px}}
input{{display:block;margin:24px 0;width:100%;font-size:17px}}button{{background:#79bbef;color:#122336;border:0;border-radius:12px;min-height:56px;width:100%;font-size:18px;font-weight:bold}}
p{{line-height:1.5;color:#c2d6ea}}</style></head><body><main><h1>📷 Send to PiCalendar</h1>
<p>Choose up to 12 photos from your iPhone. Photos are saved locally on your Pi.</p>{msg}
<form action="/p/{token}/upload" method="post" enctype="multipart/form-data">
<input name="files" type="file" accept="image/*,.heic,.heif" multiple required>
<button type="submit">Upload photos</button></form><p>Private home Wi-Fi · link expires after 15 minutes · 30 MB per photo.</p></main></body></html>"""

@app.get('/p/{token}',response_class=HTMLResponse)
async def page(token:str):
    _check(token)
    return HTMLResponse(_page(token))

@app.post('/p/{token}/upload',response_class=HTMLResponse)
async def upload(token:str,files:list[UploadFile]=File(...)):
    _check(token)
    if not 1<=len(files)<=12:
        raise HTTPException(422,'Choose 1–12 photos.')
    count=0
    errors=[]
    for file in files:
        try:
            data=await file.read(MAX_PHOTO_BYTES+1)
            save_photo(data)
            count+=1
        except ValueError as exc:
            errors.append(str(exc))
        finally:
            await file.close()
    message=f'{count} photo(s) added to PiCalendar.'
    if errors:
        message+=f' {len(errors)} failed: '+errors[0]
    return HTMLResponse(_page(token,message))
