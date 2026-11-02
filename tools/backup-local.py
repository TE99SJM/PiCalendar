#!/usr/bin/env python3
"""Consistent local SQLite snapshots, safely excluding OAuth keys and photo files."""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('FAMILY_CALENDAR_DATA', ROOT / 'data')).expanduser()
BACKUP = ROOT / 'backups'
SOURCE = DATA / 'calendar.sqlite3'


def backup():
    if not SOURCE.exists():
        raise FileNotFoundError(f'No calendar database at {SOURCE}')
    BACKUP.mkdir(mode=0o700, exist_ok=True)
    os.chmod(BACKUP, 0o700)
    stamp = datetime.now(ZoneInfo('America/Chicago')).strftime('%Y%m%d-%H%M%S')
    path = BACKUP / f'calendar-{stamp}.sqlite3'
    src = sqlite3.connect(f'file:{SOURCE}?mode=ro', uri=True)
    dst = sqlite3.connect(path)
    try:
        src.backup(dst)
        if dst.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup verification failed')
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        dst.close()
        src.close()
    os.chmod(path, 0o600)
    # Rolling 7 snapshots, all kept privately on the same Pi.
    for older in sorted(BACKUP.glob('calendar-*.sqlite3'), reverse=True)[7:]:
        older.unlink()
    print('Offline backup saved:', path)
    print('Photos remain locally in', DATA / 'photos')


if __name__ == '__main__':
    backup()
