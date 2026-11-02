"""SQLite storage for the self-contained family dashboard."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get('FAMILY_CALENDAR_DATA', str(PROJECT_ROOT / 'data'))).expanduser()
DB_PATH = DATA_DIR / 'calendar.sqlite3'
PHOTOS_DIR = DATA_DIR / 'photos'
TOKEN_FILE = DATA_DIR / 'google-token.json'
SECRETS_FILE = DATA_DIR / 'google-client-secret.json'


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    connection.execute('PRAGMA journal_mode = WAL')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS calendars (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#4a88e8',
            editable INTEGER NOT NULL DEFAULT 1, selected INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            google_event_id TEXT,
            calendar_id TEXT NOT NULL DEFAULT 'local',
            title TEXT NOT NULL,
            start TEXT NOT NULL,
            end TEXT NOT NULL,
            all_day INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'local',
            pending TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ix_remote_event
            ON events(calendar_id, google_event_id) WHERE google_event_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS ix_event_range ON events(start, end);
        CREATE TABLE IF NOT EXISTS chores (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, assignee TEXT NOT NULL DEFAULT '',
            repeat TEXT NOT NULL DEFAULT 'once', due_on TEXT NOT NULL DEFAULT '',
            done_on TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS groceries (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, checked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meals (
            day TEXT PRIMARY KEY, label TEXT NOT NULL
        );
        ''')
        con.execute("INSERT OR IGNORE INTO calendars(id,name,color) VALUES('local','Family (local)','#8a72e8')")
        defaults = {
            'family_name': 'Our Family',
            'weather_location': '',
            'weather_latitude': '',
            'weather_longitude': '',
            'last_sync': '',
            'last_history_sync': '',
            'last_error': '',
        }
        con.executemany('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)', defaults.items())


def get_settings() -> dict[str, str]:
    with db() as con:
        return {row['key']: row['value'] for row in con.execute('SELECT * FROM settings')}


def set_settings(values: dict[str, str]) -> None:
    with db() as con:
        con.executemany('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', values.items())


def get_calendars() -> list[dict]:
    with db() as con:
        return [dict(r) for r in con.execute('SELECT * FROM calendars ORDER BY CASE WHEN id="local" THEN 0 ELSE 1 END, name')]


def event_list(start: str, end: str) -> list[dict]:
    with db() as con:
        rows = con.execute('''
            SELECT e.*, COALESCE(c.color,'#4a88e8') AS color,
            COALESCE(c.name,'Google Calendar') AS calendar_name
            FROM events e LEFT JOIN calendars c ON c.id=e.calendar_id
            WHERE e.start < ? AND e.end > ? AND COALESCE(e.pending,'')!='delete'
            AND (c.selected=1 OR c.id IS NULL)
            ORDER BY e.start
        ''', (end, start)).fetchall()
        return [dict(row) for row in rows]
