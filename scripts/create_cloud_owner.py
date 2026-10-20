"""Claim a fresh cloud database from its private server shell, never a public URL."""
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def main():
    from starlette.requests import Request
    from starlette.responses import Response
    from app.database import migrate, Session, Account
    from app.accounts import register
    from fastapi import HTTPException

    migrate()
    with Session() as db:
        if db.query(Account).count():
            raise SystemExit('An owner already exists. This command never resets an existing account.')
    name = input('Owner display name: ').strip()
    email = input('Owner email: ').strip()
    password = getpass.getpass('New password (12–128 characters): ')
    if not name or len(name) > 80:
        raise SystemExit('Use a display name with 1–80 characters.')
    if password != getpass.getpass('Confirm new password: '):
        raise SystemExit('Passwords did not match. No account created.')
    request = Request({'type': 'http', 'method': 'POST', 'scheme': 'http',
                       'path': '/api/auth/register', 'headers': [(b'host', b'localhost')],
                       'query_string': b'', 'client': ('127.0.0.1', 0), 'server': ('localhost', 80)})
    try:
        register(request, Response(), name, email, password)
    except HTTPException as exc:
        raise SystemExit(str(exc.detail)) from None
    print('Owner created. Sign in through the public HTTPS app. Registration remains private.')


if __name__ == '__main__':
    main()
