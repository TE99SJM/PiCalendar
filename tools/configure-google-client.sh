#!/usr/bin/env bash
# Publisher-only setup: Google Desktop OAuth app client JSON.
# This is never shown to the person who signs in on the Pi touchscreen.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "Usage: bash tools/configure-google-client.sh /path/to/downloaded-desktop-oauth.json" >&2
  exit 2
fi

python3 - "$1" "config/google-oauth-desktop.json" <<'PYTHON'
import json
import os
import sys
import tempfile
from pathlib import Path

source, dest = Path(sys.argv[1]), Path(sys.argv[2])
try:
    if source.stat().st_size > 32768:
        raise ValueError('OAuth client JSON exceeds 32 KB')
    payload = json.loads(source.read_text(encoding='utf-8'))
    info = payload.get('installed', {})
    if not isinstance(info, dict) or not all(info.get(k) for k in ('client_id', 'auth_uri', 'token_uri')):
        raise ValueError('Expected Google Desktop app OAuth JSON, not Web app credentials or an API key')
    if info['auth_uri'] not in ('https://accounts.google.com/o/oauth2/auth', 'https://accounts.google.com/o/oauth2/v2/auth'):
        raise ValueError('Invalid Google authorization endpoint')
    if info['token_uri'] not in ('https://oauth2.googleapis.com/token', 'https://www.googleapis.com/oauth2/v4/token'):
        raise ValueError('Invalid Google token endpoint')
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.google-client-', dir=str(dest.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(payload, output)
        os.chmod(temp, 0o600)
        os.replace(temp, dest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
except (ValueError, KeyError, OSError, json.JSONDecodeError) as e:
    sys.exit('Setup failed: ' + str(e))
print('Google application client configured locally; no user tokens were created.')
PYTHON
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl restart family-calendar.service
fi
printf '%s\n' 'On the Pi: Settings → Google Calendar → Sign in with Google.'
