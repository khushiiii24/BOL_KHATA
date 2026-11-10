"""Sign in with Google (Gmail). Every Gmail gets its own, private khata.

How it works:
  1. The login page shows Google's "Continue with Google" button.
  2. Google gives the browser a signed ID token for the person's Gmail account.
  3. We check that token with Google's public keys (google-auth library) and read the email.
  4. First time for this Gmail = sign-up: an account and an empty khata are made (app/accounts.py).
     Every later time = login. Either way the browser gets a signed session cookie (12 hours).
  5. Every /api/... request opens only the khata of the account in that cookie.
     Without a valid cookie it is refused with 401.

Who may sign up?
  - ALLOWED_EMAILS empty (default): anyone with a Google account (and, while your Google app is in
    "Testing" mode, only the test users you listed in Google Cloud).
  - ALLOWED_EMAILS=a@gmail.com,b@gmail.com : only these Gmails. Removing one locks it out at once.

If GOOGLE_CLIENT_ID is not set in .env, sign-in is off and the app opens directly with one
shared khata (handy while you are still testing on your own laptop).
"""

from __future__ import annotations

import secrets
from pathlib import Path

from . import accounts
from .config import settings

SESSION_HOURS = 12


def secret_key() -> str:
    """A random key that signs the session cookie: SESSION_SECRET if set, else created once in data/secret.key."""
    if settings.session_secret:
        return settings.session_secret
    path: Path = settings.db_path.parent / "secret.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def enabled() -> bool:
    return bool(settings.google_client_id)


def allowed_emails() -> set[str]:
    """Empty set = open sign-up for any Google account."""
    return {e.strip().lower() for e in settings.allowed_emails.split(",") if e.strip()}


def may_use(email: str) -> bool:
    allowed = allowed_emails()
    return not allowed or email.strip().lower() in allowed


def verify_google_token(credential: str) -> dict:
    """Check the ID token with Google. Returns its claims (sub, email, name, picture...)."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(credential, google_requests.Request(), settings.google_client_id,
                                        clock_skew_in_seconds=10)


class NotAllowed(Exception):
    pass


def sign_in(credential: str) -> tuple[dict, bool]:
    """Verify the Google token, then log in or sign up. Returns (session user, is_new_account)."""
    claims = verify_google_token(credential)
    if not claims.get("email_verified"):
        raise NotAllowed("This Google account's email is not verified.")
    email = claims["email"].strip().lower()
    if not may_use(email):
        raise NotAllowed(email)
    account, created = accounts.sign_in(claims.get("sub"), email, claims.get("name"), claims.get("picture"))
    user = {"id": account["id"], "email": email,
            "name": claims.get("name") or email.split("@")[0], "picture": claims.get("picture")}
    return user, created


def current_account(user: dict | None) -> dict | None:
    """The account behind a session cookie, checked again on every request."""
    if not user:
        return None
    account = accounts.get(user.get("id"))
    if not account or account["email"] != str(user.get("email", "")).lower() or not may_use(account["email"]):
        return None
    return account
