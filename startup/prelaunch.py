#!/usr/bin/env python3
"""PiCalendar kiosk pre-launch checker: real readiness checks, no simulated progress.

This local-only HTTP service serves a startup page and a status endpoint.  It does
not modify, reset, or depend on any Google credentials.  It shuts down when the
Chromium kiosk process closes.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import threading
import time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
STARTUP = ROOT / 'startup'
STEPS = [
    ('startup', 'Preparing PiCalendar startup'),
    ('assets', 'Checking touchscreen files'),
    ('database', 'Checking saved calendar data'),
    ('server', 'Connecting to local calendar service'),
    ('events', 'Loading saved events'),
    ('lists', 'Loading chores and shopping lists'),
    ('ready', 'Ready — opening PiCalendar'),
]


class Checks:
    def __init__(self, app_port=8080, data_dir=None):
        self.app_port = app_port
        self.data_dir = Path(data_dir) if data_dir else ROOT / 'data'
        self.lock = threading.Lock()
        self.completed = 0
        self.message = 'Starting checks'
        self.last_error = ''
        self.started = False
        self.done = False

    def snapshot(self):
        with self.lock:
            return {'done': self.done,
                    'completed': self.completed,
                    'total': len(STEPS),
                    'app_port': self.app_port,
                    'percent': round(100 * self.completed / len(STEPS)),
                    'message': self.message,
                    'detail': self.last_error}

    def _step(self, key, title, check):
        while True:
            try:
                check()
                with self.lock:
                    self.completed += 1
                    self.message = title
                    self.last_error = ''
                return
            except (OSError, ValueError, sqlite3.Error, URLError, TimeoutError,
                    json.JSONDecodeError, KeyError) as exc:
                with self.lock:
                    self.message = title + ' — waiting'
                    self.last_error = str(exc)[:180]
                time.sleep(0.65)

    def _url_json(self, path):
        with urlopen(f'http://127.0.0.1:{self.app_port}{path}', timeout=1.5) as resp:
            if resp.status != 200:
                raise ValueError(f'Calendar returned {resp.status}')
            return json.loads(resp.read(3_000_000))

    def _check_assets(self):
        for name in ('index.html', 'app.js', 'style.css', 'touch-gestures.js'):
            if not (ROOT / 'static' / name).is_file():
                raise FileNotFoundError('Missing ' + name)

    def _check_database(self):
        path = self.data_dir / 'calendar.sqlite3'
        if not path.is_file():
            raise FileNotFoundError('Waiting for local calendar database')
        con = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=2)
        try:
            if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Local database integrity check failed')
            for table in ('events', 'calendars', 'chores', 'groceries', 'meals'):
                con.execute(f'SELECT 1 FROM {table} LIMIT 1').fetchone()
        finally:
            con.close()

    def _check_server(self):
        response = self._url_json('/api/status')
        if not isinstance(response, dict) or 'google_connected' not in response:
            raise ValueError('Unexpected local server response')

    def _check_events(self):
        today = date.today()
        qs = urlencode({'start': (today-timedelta(days=45)).isoformat(),
                        'end': (today+timedelta(days=100)).isoformat()})
        data = self._url_json('/api/events?' + qs)
        if not isinstance(data, list):
            raise ValueError('Event storage response was invalid')

    def _check_lists(self):
        for endpoint in ('/api/chores', '/api/groceries', '/api/calendars', '/api/photos'):
            if not isinstance(self._url_json(endpoint), list):
                raise ValueError('Could not read local data from ' + endpoint)

    def run(self):
        funcs = [lambda: None, self._check_assets, self._check_database,
                 self._check_server, self._check_events, self._check_lists, lambda: None]
        for (key, title), func in zip(STEPS, funcs):
            self._step(key, title, func)
        with self.lock:
            self.done = True

    def start_once(self):
        with self.lock:
            if self.started:
                return
            self.started = True
        threading.Thread(target=self.run, name='picalendar-readiness', daemon=True).start()


def handler_factory(checks):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ('/', '/index.html'):
                self._serve(STARTUP / 'splash.html', 'text/html; charset=utf-8')
            elif self.path == '/logo.png':
                self._serve(STARTUP / 'picalendar-logo.png', 'image/png')
            elif self.path == '/api/progress':
                checks.start_once()
                body = json.dumps(checks.snapshot()).encode('utf-8')
                self._write(body, 'application/json; charset=utf-8')
            else:
                self.send_error(404)

        def _serve(self, p, content_type):
            try:
                self._write(p.read_bytes(), content_type)
            except FileNotFoundError:
                self.send_error(404)

        def _write(self, body, content_type):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--app-port', type=int, default=8080)
    parser.add_argument('--data-dir', default=None)
    args = parser.parse_args()
    checks = Checks(app_port=args.app_port, data_dir=args.data_dir)
    httpd = ThreadingHTTPServer(('127.0.0.1', args.port), handler_factory(checks))
    print(f'PiCalendar startup checker on 127.0.0.1:{args.port}', flush=True)
    httpd.serve_forever(poll_interval=0.2)


if __name__ == '__main__':
    main()
