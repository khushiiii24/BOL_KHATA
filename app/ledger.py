"""The khata (ledger) itself, saved in a small SQLite file:
  data/khata.db                       when sign-in is off (one khata on this laptop)
  data/users/<account>/khata.db       when sign-in is on (every Gmail has its own)

Tables:
  customers : one row per customer
  entries   : every udhaar (credit) or jama (payment), with what was said
  archives  : old khatas that were saved when "Start a new khata" was used

Nothing is ever lost by starting a new khata: the old customers and entries just get an
archive_id, and they can be opened (and downloaded as CSV) from "Saved khatas".
Rows with archive_id = NULL are the current khata.

balance = all credit - all payment   (positive = customer owes the shop)
"""

from __future__ import annotations

import csv
import io
import sqlite3
import threading
from contextvars import ContextVar
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import settings

_lock = threading.Lock()


def _now(days_ago: int = 0, hour: int | None = None) -> str:
    t = datetime.now() - timedelta(days=days_ago)
    if hour is not None:
        t = t.replace(hour=hour, minute=15)
    return t.isoformat(timespec="seconds")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL CHECK (kind IN ('credit', 'payment')),
    amount       REAL NOT NULL,
    note         TEXT,
    said         TEXT,
    new_customer INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS promises (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    amount      REAL,                          -- NULL = "will clear everything"
    paid        REAL NOT NULL DEFAULT 0,       -- paid towards it so far
    due_date    TEXT NOT NULL,
    said        TEXT,
    status      TEXT NOT NULL DEFAULT 'open',  -- open / kept / late / missed / replaced
    created_at  TEXT NOT NULL,
    closed_at   TEXT,
    closed_by   INTEGER,                       -- the payment entry that kept it
    batch       TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS archives (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    reason         TEXT NOT NULL DEFAULT 'manual',
    created_at     TEXT NOT NULL,
    customer_count INTEGER NOT NULL DEFAULT 0,
    entry_count    INTEGER NOT NULL DEFAULT 0,
    total_due      REAL NOT NULL DEFAULT 0
);
"""


def _add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


class _Rows:
    """The full result of one statement, read while the connection was locked."""

    def __init__(self, cur: sqlite3.Cursor):
        self.rows = cur.fetchall() if cur.description else []
        self.rowcount = cur.rowcount
        self.lastrowid = cur.lastrowid

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def __iter__(self):
        return iter(self.rows)


class SafeConnection:
    """One SQLite connection shared by the web server's threads: one statement at a time,
    and each result is read completely before the next request can use the connection."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.RLock()

    def execute(self, sql: str, args=()) -> _Rows:
        with self._lock:
            return _Rows(self._conn.execute(sql, args))

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _connect(path: Path) -> SafeConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    # Older khata.db files (from the first versions) get the new columns automatically.
    _add_column(conn, "customers", "archive_id", "archive_id INTEGER")
    _add_column(conn, "entries", "archive_id", "archive_id INTEGER")
    _add_column(conn, "entries", "sample", "sample INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "customers", "phone", "phone TEXT")
    _add_column(conn, "entries", "batch", "batch TEXT")  # entries said in one sentence share a batch
    _add_column(conn, "customers", "credit_limit", "credit_limit REAL")  # warn when udhaar goes above this
    conn.commit()
    return SafeConnection(conn)


# --- which khata? -----------------------------------------------------------
# Sign-in off: one khata, data/khata.db.
# Sign-in on:  every account has its own file, data/users/<account>/khata.db. The web server calls
#              use(<that file>) at the start of each request, so the functions below only ever see
#              the signed-in person's data. With no khata chosen, they refuse to run (never a shared file).
_open: dict[str, SafeConnection] = {}
_open_lock = threading.Lock()
_current: ContextVar[SafeConnection | None] = ContextVar("khata", default=None)


def open_khata(path: Path) -> SafeConnection:
    key = str(Path(path).resolve())
    with _open_lock:
        if key not in _open:
            _open[key] = _connect(Path(path))
        return _open[key]


def close_khata(path: Path) -> None:
    with _open_lock:
        conn = _open.pop(str(Path(path).resolve()), None)
    if conn is not None:
        conn.close()


def use(path: Path) -> None:
    """Pick the khata for this request."""
    _current.set(open_khata(path))


def _c() -> SafeConnection:
    conn = _current.get()
    if conn is None:
        raise RuntimeError("No khata chosen for this request (sign-in needed).")
    return conn


def _due_since(entries: list[sqlite3.Row]) -> str | None:
    """Date of the oldest udhaar that is still unpaid.

    Payments pay off the oldest udhaar first (first in, first out), like a shopkeeper would.
    """
    open_credits: list[list] = []  # [created_at, amount_left]
    advance = 0.0
    for e in entries:
        amount = float(e["amount"])
        if e["kind"] == "credit":
            use = min(advance, amount)
            advance -= use
            amount -= use
            if amount > 0.005:
                open_credits.append([e["created_at"], amount])
        else:
            while amount > 0.005 and open_credits:
                take = min(amount, open_credits[0][1])
                open_credits[0][1] -= take
                amount -= take
                if open_credits[0][1] <= 0.005:
                    open_credits.pop(0)
            advance += amount
    return open_credits[0][0] if open_credits else None


def _day(ts: str) -> date:
    return date.fromisoformat(ts[:10])


def _trust(entries: list, promises: list[dict], today: date) -> dict:
    """A 0-100 "bharosa" score from how this customer repays, plus overdue buckets.

    35%  how fast past udhaar was repaid      (FIFO: payments clear the oldest udhaar first)
    30%  how old the oldest unpaid udhaar is
    20%  promises kept vs. missed
    15%  share of all udhaar that has been paid back
    """
    open_credits: list[list] = []  # [date, amount_left]
    advance, repaid = 0.0, []      # repaid: (days taken, amount)
    total_credit = total_paid = 0.0
    for e in entries:
        amount, d = float(e["amount"]), _day(e["created_at"])
        if e["kind"] == "credit":
            total_credit += amount
            use = min(advance, amount)
            advance -= use
            amount -= use
            if amount > 0.005:
                open_credits.append([d, amount])
        else:
            total_paid += amount
            while amount > 0.005 and open_credits:
                take = min(amount, open_credits[0][1])
                repaid.append(((d - open_credits[0][0]).days, take))
                open_credits[0][1] -= take
                amount -= take
                if open_credits[0][1] <= 0.005:
                    open_credits.pop(0)
            advance += amount
    aging = [0.0, 0.0, 0.0]  # unpaid udhaar that is 0-7, 8-30 and over 30 days old
    for d, left in open_credits:
        age = (today - d).days
        aging[0 if age <= 7 else 1 if age <= 30 else 2] += left
    oldest = (today - open_credits[0][0]).days if open_credits else 0
    kept = sum(1 for p in promises if p["status"] == "kept")
    late = sum(1 for p in promises if p["status"] == "late")
    missed = sum(1 for p in promises if p["status"] == "missed"
                 or (p["status"] == "open" and p["due_date"] < today.isoformat()))
    out = {"score": None, "label": "new", "avg_days": None, "oldest_days": oldest,
           "kept": kept + late, "missed": missed, "aging": [round(x, 2) for x in aging]}
    if total_credit <= 0 or (not repaid and not kept + late + missed and oldest < 15):
        return out  # not enough history yet
    avg = sum(dd * a for dd, a in repaid) / sum(a for _, a in repaid) if repaid else None
    speed = None if avg is None else 1.0 if avg <= 7 else 0.8 if avg <= 15 else 0.55 if avg <= 30 else 0.3
    age = 1.0 if oldest <= 7 else 0.75 if oldest <= 15 else 0.45 if oldest <= 30 else 0.15
    word = (kept + 0.6 * late) / (kept + late + missed) if kept + late + missed else None
    ratio = min(1.0, total_paid / total_credit)
    parts = [(v, w) for v, w in ((speed, 0.35), (age, 0.30), (word, 0.20), (ratio, 0.15)) if v is not None]
    score = round(100 * sum(v * w for v, w in parts) / sum(w for _, w in parts))
    out.update(score=score, label="good" if score >= 75 else "ok" if score >= 50 else "risk",
               avg_days=round(avg) if avg is not None else None)
    return out


def _customers(archive_id: int | None) -> list[dict]:
    where = "c.archive_id IS NULL" if archive_id is None else "c.archive_id = ?"
    args = () if archive_id is None else (archive_id,)
    customers = [dict(r) for r in _c().execute(f"""
        SELECT c.id, c.name, c.phone, c.created_at, c.credit_limit,
               COALESCE(SUM(CASE WHEN e.kind = 'credit' THEN e.amount ELSE -e.amount END), 0) AS balance,
               MAX(e.created_at) AS last_at,
               COUNT(e.id) AS entry_count
        FROM customers c LEFT JOIN entries e ON e.customer_id = c.id
        WHERE {where}
        GROUP BY c.id
        ORDER BY last_at DESC
    """, args)]
    by_id = {c["id"]: c for c in customers}
    rows: dict[int, list] = {}
    for e in _c().execute(f"""
        SELECT e.customer_id, e.kind, e.amount, e.created_at FROM entries e
        JOIN customers c ON c.id = e.customer_id WHERE {where}
        ORDER BY e.created_at, e.id""", args):
        rows.setdefault(e["customer_id"], []).append(e)
    promises: dict[int, list[dict]] = {}
    for p in _c().execute(f"""
        SELECT p.* FROM promises p JOIN customers c ON c.id = p.customer_id
        WHERE {where} AND p.status != 'replaced' ORDER BY p.id""", args):
        promises.setdefault(p["customer_id"], []).append(dict(p))
    today = datetime.now().date()
    for cid, c in by_id.items():
        es = rows.get(cid, [])
        ps = promises.get(cid, [])
        c["due_since"] = _due_since(es) if c["balance"] > 0.5 else None
        c["last_kind"] = es[-1]["kind"] if es else None
        c["last_amount"] = es[-1]["amount"] if es else None
        c["last_at"] = es[-1]["created_at"] if es else None
        c["trust"] = _trust(es, ps, today)
        open_ps = [p for p in ps if p["status"] == "open"]
        c["promise"] = _promise_view(open_ps[-1], c["balance"], today) if open_ps and c["balance"] > 0.5 else None
        c["over_limit"] = bool(c["credit_limit"]) and c["balance"] > c["credit_limit"] + 0.005
    return customers


def _promise_view(p: dict, balance: float, today: date) -> dict:
    left = balance if p["amount"] is None else max(0.0, min(balance, p["amount"] - p["paid"]))
    due = date.fromisoformat(p["due_date"])
    return {"id": p["id"], "amount": p["amount"], "left": round(left, 2), "due_date": p["due_date"],
            "days": (due - today).days, "said": p["said"], "created_at": p["created_at"]}


def list_customers() -> list[dict]:
    return _customers(None)


def get_customer(customer_id: int) -> dict | None:
    for c in list_customers():
        if c["id"] == customer_id:
            return c
    return None


def create_customer(name: str) -> dict:
    with _lock:
        cur = _c().execute("INSERT INTO customers (name, created_at) VALUES (?, ?)", (name, _now()))
        _c().commit()
    return {"id": cur.lastrowid, "name": name, "balance": 0}


def update_customer(customer_id: int, name: str | None = None, phone: str | None = None) -> dict | None:
    """Fix a name the speech-to-text got wrong, or save a phone number for WhatsApp."""
    with _lock:
        if name is not None and name.strip():
            _c().execute("UPDATE customers SET name = ? WHERE id = ? AND archive_id IS NULL", (name.strip(), customer_id))
        if phone is not None:
            digits = "".join(ch for ch in phone if ch.isdigit())[-13:]
            _c().execute("UPDATE customers SET phone = ? WHERE id = ? AND archive_id IS NULL", (digits or None, customer_id))
        _c().commit()
    return get_customer(customer_id)


def set_limit(customer_id: int, amount: float | None) -> dict | None:
    """Udhaar limit for one customer. None removes it."""
    with _lock:
        _c().execute("UPDATE customers SET credit_limit = ? WHERE id = ? AND archive_id IS NULL",
                     (round(float(amount), 2) if amount else None, customer_id))
        _c().commit()
    return get_customer(customer_id)


# ------------------------------------------------------------------ promises ("शुक्रवार को देगा")
def add_promise(customer_id: int, amount: float | None, due_date: str, said: str | None = None,
                batch: str | None = None, created_at: str | None = None, status: str = "open") -> dict:
    """A new promise replaces the customer's earlier open one (an overdue one counts as missed)."""
    today = datetime.now().date().isoformat()
    with _lock:
        _c().execute("""UPDATE promises SET status = CASE WHEN due_date < ? THEN 'missed' ELSE 'replaced' END,
                        closed_at = ? WHERE customer_id = ? AND status = 'open'""", (today, _now(), customer_id))
        cur = _c().execute(
            "INSERT INTO promises (customer_id, amount, due_date, said, status, created_at, batch) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (customer_id, round(float(amount), 2) if amount else None, due_date, said, status,
             created_at or _now(), batch))
        _c().commit()
    return get_promise(cur.lastrowid)


def get_promise(promise_id: int) -> dict | None:
    row = _c().execute("""SELECT p.*, c.name AS customer FROM promises p JOIN customers c ON c.id = p.customer_id
                          WHERE p.id = ?""", (promise_id,)).fetchone()
    return dict(row) if row else None


def cancel_promise(promise_id: int) -> bool:
    with _lock:
        n = _c().execute("DELETE FROM promises WHERE id = ? AND status = 'open'", (promise_id,)).rowcount
        _c().commit()
    return n > 0


def _settle_promise(entry: dict) -> dict | None:
    """A payment counts towards the customer's open promise. Returns the promise if this payment kept it."""
    p = _c().execute("SELECT * FROM promises WHERE customer_id = ? AND status = 'open' ORDER BY id DESC LIMIT 1",
                     (entry["customer_id"],)).fetchone()
    if not p:
        return None
    paid = p["paid"] + entry["amount"]
    done = balance(entry["customer_id"]) <= 0.5 or (p["amount"] is not None and paid >= p["amount"] - 0.5)
    status = ("kept" if entry["created_at"][:10] <= p["due_date"] else "late") if done else "open"
    _c().execute("UPDATE promises SET paid = ?, status = ?, closed_at = ?, closed_by = ? WHERE id = ?",
                 (paid, status, _now() if done else None, entry["id"] if done else None, p["id"]))
    return {**dict(p), "status": status, "paid": paid} if done else None


def _unsettle_promise(entry: dict) -> None:
    """Undo of a payment: take it back out of the promise it counted towards."""
    if entry["kind"] != "payment":
        return
    p = _c().execute("""SELECT * FROM promises WHERE customer_id = ? AND (closed_by = ? OR status = 'open')
                        ORDER BY (closed_by = ?) DESC, id DESC LIMIT 1""",
                     (entry["customer_id"], entry["id"], entry["id"])).fetchone()
    if p:
        _c().execute("UPDATE promises SET paid = MAX(0, paid - ?), status = 'open', closed_at = NULL, closed_by = NULL "
                     "WHERE id = ?", (entry["amount"], p["id"]))


def due_list() -> dict:
    """Who should pay: promises due today or already overdue, and the ones coming in the next 7 days."""
    today = datetime.now().date()
    out = {"today": [], "overdue": [], "upcoming": []}
    for c in list_customers():
        p = c.get("promise")
        if not p:
            continue
        item = {"customer_id": c["id"], "name": c["name"], "balance": c["balance"], **p}
        if p["days"] == 0:
            out["today"].append(item)
        elif p["days"] < 0:
            out["overdue"].append(item)
        elif p["days"] <= 7:
            out["upcoming"].append(item)
    for k in out:
        out[k].sort(key=lambda x: (x["days"], -x["left"]))
    return out


# ------------------------------------------------------------------ shop settings (UPI id, shop name)
def get_setting(key: str, default: str | None = None) -> str | None:
    row = _c().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row and row["value"] else default


def set_setting(key: str, value: str | None) -> None:
    with _lock:
        _c().execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, value))
        _c().commit()


# ------------------------------------------------------------------ entries
def add_entry(customer_id: int, kind: str, amount: float, note: str | None, said: str | None,
              new_customer: bool = False, created_at: str | None = None, sample: bool = False,
              batch: str | None = None) -> dict:
    with _lock:
        cur = _c().execute(
            "INSERT INTO entries (customer_id, kind, amount, note, said, new_customer, created_at, sample, batch) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (customer_id, kind, round(float(amount), 2), note, said, int(new_customer),
             created_at or _now(), int(sample), batch),
        )
        entry = get_entry(cur.lastrowid)
        if kind == "payment" and not sample:
            entry["promise_kept"] = _settle_promise(entry)
        _c().commit()
    return entry


def get_entry(entry_id: int) -> dict | None:
    row = _c().execute("""
        SELECT e.*, c.name AS customer FROM entries e JOIN customers c ON c.id = e.customer_id
        WHERE e.id = ?""", (entry_id,)).fetchone()
    return dict(row) if row else None


def balance(customer_id: int) -> float:
    row = _c().execute("""
        SELECT COALESCE(SUM(CASE WHEN kind = 'credit' THEN amount ELSE -amount END), 0) AS b
        FROM entries WHERE customer_id = ?""", (customer_id,)).fetchone()
    return float(row["b"])


def customer_entries(customer_id: int) -> list[dict]:
    """Newest first, each with the balance right after it ("balance_after")."""
    rows = [dict(r) for r in _c().execute(
        "SELECT * FROM entries WHERE customer_id = ? ORDER BY created_at, id", (customer_id,))]
    run = 0.0
    for r in rows:
        run += r["amount"] if r["kind"] == "credit" else -r["amount"]
        r["balance_after"] = round(run, 2)
    return list(reversed(rows))


def recent_entries(limit: int = 8) -> list[dict]:
    rows = _c().execute("""
        SELECT e.*, c.name AS customer FROM entries e JOIN customers c ON c.id = e.customer_id
        WHERE c.archive_id IS NULL ORDER BY e.id DESC LIMIT ?""", (limit,)).fetchall()
    return [dict(r) for r in rows]


def undo_last() -> dict | None:
    """Delete the most recent entry of the current khata. If it created the customer, remove them too.
    Entries said in one sentence ("2000 का सामान लिया और 1000 जमा किए") are removed together;
    they are listed in entry["batch_entries"], oldest first."""
    with _lock:
        row = _c().execute("""
            SELECT e.*, c.name AS customer FROM entries e JOIN customers c ON c.id = e.customer_id
            WHERE c.archive_id IS NULL AND e.sample = 0 ORDER BY e.id DESC LIMIT 1""").fetchone()
        prow = _c().execute("""
            SELECT p.*, c.name AS customer FROM promises p JOIN customers c ON c.id = p.customer_id
            WHERE c.archive_id IS NULL AND p.status = 'open' AND p.said IS NOT NULL
            ORDER BY p.id DESC LIMIT 1""").fetchone()
        # the newest thing said was a promise ("रमेश शुक्रवार को देगा") -> remove that
        if prow and (not row or (prow["created_at"], 1) > (row["created_at"], 0)) and \
                not (row and row["batch"] and row["batch"] == prow["batch"]):
            _c().execute("DELETE FROM promises WHERE id = ?", (prow["id"],))
            _c().commit()
            return {**dict(prow), "kind": "promise", "batch_entries": []}
        if not row:
            return None
        entry = dict(row)
        group = [dict(row)]  # a copy, so the reply never contains itself
        if entry.get("batch"):
            group = [dict(r) for r in _c().execute("""
                SELECT e.*, c.name AS customer FROM entries e JOIN customers c ON c.id = e.customer_id
                WHERE e.batch = ? AND c.archive_id IS NULL ORDER BY e.id""", (entry["batch"],))]
        for e in group:
            _unsettle_promise(e)
            _c().execute("DELETE FROM entries WHERE id = ?", (e["id"],))
        if entry.get("batch"):
            _c().execute("DELETE FROM promises WHERE batch = ?", (entry["batch"],))
        for e in group:
            if e["new_customer"]:
                left = _c().execute("SELECT COUNT(*) AS n FROM entries WHERE customer_id = ?",
                                   (e["customer_id"],)).fetchone()["n"]
                if left == 0:
                    _c().execute("DELETE FROM customers WHERE id = ?", (e["customer_id"],))
        _c().commit()
    entry["batch_entries"] = group
    return entry


def delete_entry(entry_id: int) -> dict | None:
    """Remove one entry of the current khata (any entry, not just the last one)."""
    with _lock:
        row = _c().execute("""
            SELECT e.*, c.name AS customer FROM entries e JOIN customers c ON c.id = e.customer_id
            WHERE e.id = ? AND c.archive_id IS NULL""", (entry_id,)).fetchone()
        if not row:
            return None
        _unsettle_promise(dict(row))
        _c().execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        _c().commit()
    return dict(row)


def week() -> list[dict]:
    """Udhaar given and money received on each of the last 7 days (for the small chart)."""
    days = [(datetime.now().date() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    rows = {r["d"]: r for r in _c().execute("""
        SELECT substr(e.created_at, 1, 10) AS d,
               COALESCE(SUM(CASE WHEN e.kind = 'credit' THEN e.amount END), 0)  AS credit,
               COALESCE(SUM(CASE WHEN e.kind = 'payment' THEN e.amount END), 0) AS payment
        FROM entries e JOIN customers c ON c.id = e.customer_id
        WHERE c.archive_id IS NULL AND substr(e.created_at, 1, 10) >= ?
        GROUP BY d""", (days[0],))}
    return [{"date": d, "credit": rows[d]["credit"] if d in rows else 0,
             "payment": rows[d]["payment"] if d in rows else 0} for d in days]


def stats() -> dict:
    today = datetime.now().date().isoformat()
    t = _c().execute("""
        SELECT
          COALESCE(SUM(CASE WHEN e.kind = 'credit' THEN e.amount END), 0)  AS credit_today,
          COALESCE(SUM(CASE WHEN e.kind = 'payment' THEN e.amount END), 0) AS payment_today,
          COALESCE(SUM(CASE WHEN e.kind = 'credit' THEN 1 END), 0)         AS credit_count_today,
          COALESCE(SUM(CASE WHEN e.kind = 'payment' THEN 1 END), 0)        AS payment_count_today
        FROM entries e JOIN customers c ON c.id = e.customer_id
        WHERE c.archive_id IS NULL AND substr(e.created_at, 1, 10) = ?""", (today,)).fetchone()
    customers = list_customers()
    owing = sorted([c for c in customers if c["balance"] > 0.005], key=lambda c: -c["balance"])
    since = (datetime.now().date() - timedelta(days=30)).isoformat()
    m = _c().execute("""
        SELECT COALESCE(SUM(CASE WHEN e.kind = 'credit' THEN e.amount END), 0)  AS given_30,
               COALESCE(SUM(CASE WHEN e.kind = 'payment' THEN e.amount END), 0) AS collected_30
        FROM entries e JOIN customers c ON c.id = e.customer_id
        WHERE c.archive_id IS NULL AND substr(e.created_at, 1, 10) >= ?""", (since,)).fetchone()
    aging = [round(sum(c["trust"]["aging"][i] for c in customers), 2) for i in range(3)]
    labels = [c["trust"]["label"] for c in customers if c["balance"] > 0.005]
    dl = due_list()
    return {
        **dict(t),
        **dict(m),
        "aging": aging,
        "trust_counts": {k: labels.count(k) for k in ("good", "ok", "risk", "new")},
        "over_limit_count": sum(1 for c in customers if c["over_limit"]),
        "due_today_count": len(dl["today"]) + len(dl["overdue"]),
        "total_due": sum(c["balance"] for c in owing),
        "owing_count": len(owing),
        "customer_count": len(customers),
        "top": owing[0] if owing else None,
        "archive_count": _c().execute("SELECT COUNT(*) AS n FROM archives").fetchone()["n"],
    }


# ------------------------------------------------------------------ saved khatas
def _current_counts() -> tuple[int, int, int]:
    row = _c().execute("""
        SELECT (SELECT COUNT(*) FROM customers WHERE archive_id IS NULL) AS customers,
               (SELECT COUNT(*) FROM entries e JOIN customers c ON c.id = e.customer_id
                WHERE c.archive_id IS NULL) AS entries,
               (SELECT COUNT(*) FROM entries e JOIN customers c ON c.id = e.customer_id
                WHERE c.archive_id IS NULL AND e.sample = 0) AS real_entries""").fetchone()
    return row["customers"], row["entries"], row["real_entries"]


def _discard_current() -> None:
    _c().execute("DELETE FROM entries WHERE customer_id IN (SELECT id FROM customers WHERE archive_id IS NULL)")
    _c().execute("DELETE FROM customers WHERE archive_id IS NULL")


def archive_current(reason: str = "manual") -> dict | None:
    """Save the current khata in 'Saved khatas' and start an empty one.

    If the current khata only has sample customers, it is simply cleared (no need to keep fake data).
    """
    with _lock:
        n_customers, n_entries, n_real = _current_counts()
        if n_customers == 0:
            return None
        if n_real == 0:
            _discard_current()
            _c().commit()
            return None
        total_due = sum(c["balance"] for c in list_customers() if c["balance"] > 0.005)
        cur = _c().execute(
            "INSERT INTO archives (reason, created_at, customer_count, entry_count, total_due) VALUES (?, ?, ?, ?, ?)",
            (reason, _now(), n_customers, n_entries, round(total_due, 2)))
        aid = cur.lastrowid
        _c().execute("UPDATE entries SET archive_id = ? WHERE customer_id IN "
                    "(SELECT id FROM customers WHERE archive_id IS NULL)", (aid,))
        _c().execute("UPDATE customers SET archive_id = ? WHERE archive_id IS NULL", (aid,))
        _c().commit()
    return get_archive(aid)


def list_archives() -> list[dict]:
    return [dict(r) for r in _c().execute("SELECT * FROM archives ORDER BY id DESC")]


def get_archive(archive_id: int) -> dict | None:
    row = _c().execute("SELECT * FROM archives WHERE id = ?", (archive_id,)).fetchone()
    return dict(row) if row else None


def archive_detail(archive_id: int) -> dict | None:
    archive = get_archive(archive_id)
    if not archive:
        return None
    customers = _customers(archive_id)
    for c in customers:
        c["entries"] = customer_entries(c["id"])
    customers.sort(key=lambda c: -c["balance"])
    return {"archive": archive, "customers": customers}


def current_detail() -> dict:
    customers = list_customers()
    for c in customers:
        c["entries"] = customer_entries(c["id"])
    return {"customers": customers}


def archive_csv(archive_id: int | None) -> str | None:
    """CSV for Excel. archive_id=None means the current khata."""
    detail = current_detail() if archive_id is None else archive_detail(archive_id)
    if not detail:
        return None
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Customer", "Type", "Amount (Rs)", "Items / note", "What was said", "Balance after (Rs)"])
    rows = []
    for c in detail["customers"]:
        for e in c["entries"]:
            rows.append((e["created_at"], c["name"], "Udhaar (credit)" if e["kind"] == "credit" else "Jama (payment)",
                         e["amount"], e["note"] or "", e["said"] or "", e["balance_after"]))
    for r in sorted(rows):
        w.writerow([r[0].replace("T", " "), *r[1:]])
    return out.getvalue()


def delete_archive(archive_id: int) -> bool:
    """Permanently delete one saved khata. This is the only way data is ever removed for good."""
    with _lock:
        if not get_archive(archive_id):
            return False
        _c().execute("DELETE FROM entries WHERE customer_id IN (SELECT id FROM customers WHERE archive_id = ?)", (archive_id,))
        _c().execute("DELETE FROM customers WHERE archive_id = ?", (archive_id,))
        _c().execute("DELETE FROM archives WHERE id = ?", (archive_id,))
        _c().commit()
    return True


# ------------------------------------------------------------------ sample data
# Made-up sample customers, written in each language's own script.
_SAMPLE_NAMES = {
    "hi": ["रमेश", "सुनीता", "इमरान", "पप्पू", "शर्मा", "गीता"],
    "mr": ["रमेश", "सुनीता", "इमरान", "पप्पू", "शर्मा", "गीता"],
    "en": ["Ramesh", "Sunita", "Imran", "Pappu", "Sharma", "Geeta"],
    "gu": ["રમેશ", "સુનીતા", "ઇમરાન", "પપ્પુ", "શર્મા", "ગીતા"],
    "bn": ["রমেশ", "সুনীতা", "ইমরান", "পাপ্পু", "শর্মা", "গীতা"],
    "ta": ["ரமேஷ்", "சுனிதா", "இம்ரான்", "பப்பு", "சர்மா", "கீதா"],
    "te": ["రమేష్", "సునీత", "ఇమ్రాన్", "పప్పు", "శర్మ", "గీత"],
    "kn": ["ರಮೇಶ್", "ಸುನೀತಾ", "ಇಮ್ರಾನ್", "ಪಪ್ಪು", "ಶರ್ಮಾ", "ಗೀತಾ"],
}
_SAMPLE_NOTES = {  # atta+oil, month's ration, sugar+tea, milk+bread, ration, dal+rice, soap
    "hi": ["5 किलो आटा, 1 लीटर तेल", "महीने का राशन", "चीनी, चायपत्ती", "दूध, ब्रेड", "राशन", "दाल, चावल", "साबुन"],
    "mr": ["5 किलो आटा, 1 लिटर तेल", "महिन्याचा किराणा", "साखर, चहापत्ती", "दूध, ब्रेड", "किराणा", "डाळ, तांदूळ", "साबण"],
    "en": ["5 kg atta, 1 litre oil", "monthly ration", "sugar, tea", "milk, bread", "ration", "dal, rice", "soap"],
    "gu": ["5 કિલો લોટ, 1 લીટર તેલ", "મહિનાનું કરિયાણું", "ખાંડ, ચા", "દૂધ, બ્રેડ", "કરિયાણું", "દાળ, ચોખા", "સાબુ"],
    "bn": ["5 কেজি আটা, 1 লিটার তেল", "মাসের রেশন", "চিনি, চা পাতা", "দুধ, পাউরুটি", "রেশন", "ডাল, চাল", "সাবান"],
    "ta": ["5 கிலோ மாவு, 1 லிட்டர் எண்ணெய்", "மாத மளிகை", "சர்க்கரை, டீத்தூள்", "பால், ரொட்டி", "மளிகை", "பருப்பு, அரிசி", "சோப்பு"],
    "te": ["5 కిలోల పిండి, 1 లీటర్ నూనె", "నెల సరుకులు", "చక్కెర, టీ పొడి", "పాలు, బ్రెడ్", "సరుకులు", "పప్పు, బియ్యం", "సబ్బు"],
    "kn": ["5 ಕೆಜಿ ಹಿಟ್ಟು, 1 ಲೀಟರ್ ಎಣ್ಣೆ", "ತಿಂಗಳ ದಿನಸಿ", "ಸಕ್ಕರೆ, ಟೀ ಪುಡಿ", "ಹಾಲು, ಬ್ರೆಡ್", "ದಿನಸಿ", "ಬೇಳೆ, ಅಕ್ಕಿ", "ಸೋಪು"],
}


def seed_demo(lang: str = "hi") -> dict | None:
    """Fill the khata with made-up (synthetic) customers for demos, in the chosen language.

    Your real entries are saved first in 'Saved khatas', so nothing is lost.
    """
    names = _SAMPLE_NAMES.get(lang, _SAMPLE_NAMES["hi"])
    notes = _SAMPLE_NOTES.get(lang, _SAMPLE_NOTES["hi"])
    saved = archive_current("sample")
    with _lock:
        _discard_current()  # only sample rows can be left here
        _c().commit()
    demo = [
        (names[0], [("credit", 850, notes[0], 12, 10), ("payment", 300, None, 4, 18)]),
        (names[1], [("credit", 1240, notes[1], 34, 11)]),
        (names[2], [("credit", 450, notes[2], 1, 9)]),
        (names[3], [("credit", 160, notes[3], 0, 8)]),
        (names[4], [("credit", 2000, notes[4], 20, 12), ("payment", 2000, None, 2, 19)]),
        (names[5], [("credit", 620, notes[5], 9, 16), ("credit", 180, notes[6], 6, 17), ("payment", 200, None, 3, 12)]),
    ]
    ids = []
    for name, rows in demo:
        c = create_customer(name)
        ids.append(c["id"])
        for kind, amount, note, days, hour in rows:
            add_entry(c["id"], kind, amount, note, None, created_at=_now(days, hour), sample=True)
    # promises and limits, so the trust score, "due today" and limit warnings have something to show
    today = datetime.now().date()
    day = lambda n: (today + timedelta(days=n)).isoformat()  # noqa: E731
    add_promise(ids[4], 2000, day(-3), created_at=_now(10, 12), status="kept")   # kept its word
    add_promise(ids[0], 550, day(1), created_at=_now(2, 18))                     # due tomorrow
    add_promise(ids[1], 1240, day(-5), created_at=_now(9, 11))                   # promise missed
    add_promise(ids[5], 300, day(0), created_at=_now(3, 12))                     # due today
    set_limit(ids[1], 1000)                                                      # over the limit
    set_limit(ids[2], 2000)
    return saved
