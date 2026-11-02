from __future__ import annotations
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from startup.prelaunch import Checks


class FakeApp(BaseHTTPRequestHandler):
    def do_GET(self):
        data = b'{"google_connected": false}' if self.path == '/api/status' else b'[]'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def test_progress_is_real_and_offline(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    con = sqlite3.connect(data / 'calendar.sqlite3')
    for tbl in ('events', 'calendars', 'chores', 'groceries', 'meals'):
        con.execute(f'CREATE TABLE {tbl} (x INTEGER)')
    con.commit()
    con.close()

    # Simulate a working local calendar API with no Google connection or Wi-Fi.
    app = ThreadingHTTPServer(('127.0.0.1', 0), FakeApp)
    background = threading.Thread(target=app.serve_forever, daemon=True)
    background.start()
    try:
        checker = Checks(app_port=app.server_port, data_dir=data)
        assert checker.snapshot()['percent'] == 0
        checker.start_once()
        end = time.monotonic()+5
        observed = []
        while time.monotonic() < end and not checker.snapshot()['done']:
            observed.append(checker.snapshot()['percent'])
            time.sleep(.03)
        progress = checker.snapshot()
        assert progress['done'] is True, progress
        assert progress['percent'] == 100, progress
        assert observed == sorted(observed)
    finally:
        app.shutdown()
        app.server_close()


def test_progress_waits_for_calendar_not_a_fake_timer(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    con = sqlite3.connect(data/'calendar.sqlite3')
    for table in ('events','calendars','chores','groceries','meals'):
        con.execute(f'CREATE TABLE {table} (x INTEGER)')
    con.commit();con.close()
    # Reserve then release a port before starting: no calendar service will respond.
    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeApp)
    port = server.server_port
    server.server_close()
    checker = Checks(app_port=port, data_dir=data)
    checker.start_once()
    time.sleep(1.5)
    progress = checker.snapshot()
    assert progress['done'] is False
    assert progress['percent'] < 100
    assert 'waiting' in progress['message'].lower()
