"""Accounts: every Gmail that signs in gets its own, separate khata.

data/accounts.db  - who has signed up (Google id, Gmail, name, photo, shop name)
data/users/<id>/  - that person's own khata.db, nobody else's requests ever open it

Sign-up is simply the first "Continue with Google": the account and an empty khata are made then.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from . import ledger
from .config import settings

_lock = threading.RLock()  # re-entrant: sign_in() holds it while reading the account back
_conns: dict[str, ledger.SafeConnection] = {}


def _data_dir() -> Path:
    return settings.db_path.parent


def _db() -> ledger.SafeConnection:
    path = _data_dir() / "accounts.db"
    key = str(path.resolve())
    with _lock:
        if key not in _conns:
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id         TEXT PRIMARY KEY,
                    email      TEXT NOT NULL UNIQUE,
                    name       TEXT,
                    picture    TEXT,
                    shop_name  TEXT,
                    created_at TEXT NOT NULL,
                    last_login TEXT NOT NULL
                )""")
            conn.commit()
            _conns[key] = ledger.SafeConnection(conn)  # many requests at once, one statement at a time
        return _conns[key]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _account_id(google_sub: str | None, email: str) -> str:
    """Google's permanent id for the person ("sub"), safe to use as a folder name."""
    sub = re.sub(r"[^0-9A-Za-z]", "", google_sub or "")[:40]
    return f"g{sub}" if sub else "e" + hashlib.sha256(email.encode()).hexdigest()[:24]


def get(account_id: str | None) -> dict | None:
    if not account_id:
        return None
    row = _db().execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def count() -> int:
    return _db().execute("SELECT COUNT(*) AS n FROM accounts").fetchone()["n"]


def sign_in(google_sub: str | None, email: str, name: str | None, picture: str | None) -> tuple[dict, bool]:
    """Find this person's account, or make one (sign-up). Returns (account, just_created)."""
    email = email.strip().lower()
    db = _db()
    with _lock:
        row = db.execute("SELECT * FROM accounts WHERE id = ? OR email = ?",
                         (_account_id(google_sub, email), email)).fetchone()
        if row:
            db.execute("UPDATE accounts SET name = ?, picture = ?, last_login = ? WHERE id = ?",
                       (name or row["name"], picture, _now(), row["id"]))
            db.commit()
            return get(row["id"]), False
        account_id = _account_id(google_sub, email)
        first = db.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()["n"] == 0
        db.execute("INSERT INTO accounts (id, email, name, picture, shop_name, created_at, last_login) "
                   "VALUES (?, ?, ?, ?, NULL, ?, ?)", (account_id, email, name, picture, _now(), _now()))
        db.commit()
    if first:
        _adopt_old_khata(account_id, email)
    path = khata_path(account_id)
    ledger.open_khata(path)  # creates the empty khata
    (path.parent / "email.txt").write_text(email + "\n", encoding="utf-8")  # so you can tell the folders apart
    return get(account_id), True


def update(account_id: str, shop_name: str | None = None) -> dict | None:
    if shop_name is not None:
        _db().execute("UPDATE accounts SET shop_name = ? WHERE id = ?", (shop_name.strip()[:80] or None, account_id))
        _db().commit()
    return get(account_id)


def khata_path(account_id: str) -> Path:
    safe = re.sub(r"[^0-9A-Za-z]", "", account_id)
    return _data_dir() / "users" / safe / "khata.db"


def shop_name(account: dict | None) -> str:
    """The name used in reminder messages and at the top of the page."""
    if account is None:
        return settings.shop_name
    return account.get("shop_name") or account.get("name") or settings.shop_name


def _adopt_old_khata(account_id: str, email: str) -> None:
    """Entries made before sign-in was turned on (data/khata.db) move into the first account,
    unless an older version had named a different owner in data/owner.txt."""
    old = settings.db_path
    owner_file = _data_dir() / "owner.txt"
    if owner_file.exists() and owner_file.read_text(encoding="utf-8").strip().lower() not in ("", email):
        return
    new = khata_path(account_id)
    if not old.exists() or new.exists():
        return
    ledger.close_khata(old)
    new.parent.mkdir(parents=True, exist_ok=True)
    old.replace(new)
