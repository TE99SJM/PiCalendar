#!/usr/bin/env python3
"""Authorize Google Calendar from the Pi desktop (browser opens on the Pi)."""
from family_calendar.google_sync import SCOPES, save_credentials
from family_calendar.storage import SECRETS_FILE, init_db
from google_auth_oauthlib.flow import InstalledAppFlow


def main():
    init_db()
    if not SECRETS_FILE.exists():
        print('\nNo Google OAuth client file found.\n')
        print(f'Put your Google Cloud OAuth Desktop client JSON here:\n  {SECRETS_FILE}')
        print('See README.md > Connect Google Calendar for setup instructions.')
        raise SystemExit(1)
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), scopes=SCOPES)
    print('A Google authorization page will open on this Raspberry Pi.')
    credentials = flow.run_local_server(host='127.0.0.1', port=8766,
                                        open_browser=True, access_type='offline',
                                        prompt='consent', authorization_prompt_message='Open: {url}')
    save_credentials(credentials)
    print('\nConnected. Return to the calendar and tap Sync Now.')


if __name__ == '__main__':
    main()
