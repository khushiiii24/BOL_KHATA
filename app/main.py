"""Bol Khata web server.

Run:  python -m uvicorn app.main:app --port 8000      then open http://localhost:8000

Flow for one voice command:
  1. Browser records the shopkeeper's voice (WAV)          -> POST /api/voice
  2. Gnani Prisma turns it into text                       (app/gnani.py  transcribe)
  3. We understand the sentence                             (app/understand.py)
  4. We update the khata                                    (app/ledger.py)
  5. We write a reply in the chosen language                (app/replies.py)
  6. Browser asks Gnani Timbre to speak the reply           -> POST /api/speak
"""

from __future__ import annotations

import json
import mimetypes
import re
import uuid

# Some Windows PCs have the wrong file types in the registry, which stops the
# page's JavaScript from loading. Set them explicitly.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("font/woff2", ".woff2")

from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from . import accounts, auth, gnani, ledger, replies
from .config import ROOT, settings
from .understand import (INTENT_LABELS, find_amount, find_customer_tokens, is_cancel, match_customer,
                         parse_due, tokenize, understand)

STATIC = ROOT / "static"
app = FastAPI(title="Bol Khata")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def open_the_right_khata(request: Request, call_next):
    """Sign-in off: everyone uses data/khata.db.
    Sign-in on: each request opens only the signed-in person's own khata; no account, no data."""
    request.state.account = None
    if not auth.enabled():
        ledger.use(settings.db_path)
        return await call_next(request)
    account = auth.current_account(request.session.get("user"))
    if account:
        request.state.account = account
        ledger.use(accounts.khata_path(account["id"]))
    else:
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/auth/"):
            request.session.clear()
            return JSONResponse({"detail": "Please sign in first."}, status_code=401)
    return await call_next(request)


# signed, HTTP-only session cookie (added last, so it runs first)
app.add_middleware(SessionMiddleware, secret_key=auth.secret_key(), session_cookie="bolkhata_session",
                   max_age=auth.SESSION_HOURS * 3600, same_site="lax",
                   https_only=settings.public_url.startswith("https://"))

_lang = replies.lang_of
APP_VERSION = "3.0"  # the page checks this, so an old server window can't hide an update


def _shop(request: Request) -> str:
    return ledger.get_setting("shop_name") or accounts.shop_name(request.state.account)


def ledger_snapshot() -> dict:
    return {"customers": ledger.list_customers(), "stats": ledger.stats(), "week": ledger.week(),
            "due": ledger.due_list(), "recent": ledger.recent_entries(6)}


def _customer_for(name: str) -> tuple[dict, bool]:
    """The existing customer with this name (any script or spelling), or a new one."""
    customer = match_customer(name, ledger.list_customers())  # fresh: may be new from a moment ago
    if customer:
        return customer, False
    return ledger.create_customer(name), True


def _after_entry(entry: dict, lang: str) -> tuple[list[dict], list[dict]]:
    """Extra sentences after an entry: limit crossed, promise kept. Returns (replies, warnings)."""
    out, warnings = [], []
    c = ledger.get_customer(entry["customer_id"])
    if entry["kind"] == "credit" and c and c["over_limit"]:
        out.append(replies.limit_over(c["name"], c["credit_limit"], c["balance"], lang))
        warnings.append({"kind": "limit", "customer": c["name"], "customer_id": c["id"],
                         "limit": c["credit_limit"], "balance": c["balance"]})
    if entry.get("promise_kept"):
        out.append(replies.promise_kept(entry["customer"], lang))
        warnings.append({"kind": "kept", "customer": entry["customer"], "customer_id": entry["customer_id"]})
    return out, warnings


def _save_entry(customer: dict | None, name: str, kind: str, amount: float, note: str | None,
                said: str | None, lang: str) -> dict:
    """Write one udhaar/jama and build the reply. Creates the customer if new."""
    is_new = customer is None
    if is_new:
        customer = ledger.create_customer(name)
    entry = ledger.add_entry(customer["id"], kind, amount, note, said, is_new)
    bal = ledger.balance(customer["id"])
    extra, warnings = _after_entry(entry, lang)
    return {
        "entry": entry,
        "new_customer": is_new,
        "customer_name": customer["name"],
        "reply": replies.join(replies.entry_saved(kind, customer["name"], amount, bal, is_new, lang), *extra),
        "warnings": warnings,
        "timeline": ledger.customer_entries(customer["id"]),
    }


def _ask(need: str, parsed: dict, lang: str) -> tuple[dict, dict | None]:
    """Talk-back: ask for the missing piece, and remember what we already know.
    After two tries we stop asking, so the app never gets stuck in a loop."""
    asked = parsed.get("asked", 0)
    if asked >= 2:
        return replies.not_understood(lang), None
    pending = {k: parsed.get(k) for k in ("intent", "customer", "amount", "items", "due")}
    pending.update(need=need, asked=asked + 1)
    return replies.ask(need, pending, lang), pending


def _fill(pending: dict, text: str, customers: list[dict]) -> dict:
    """The answer to a talk-back question: "300", "रमेश", "शुक्रवार"."""
    toks = tokenize(text)
    filled = {k: pending.get(k) for k in ("intent", "customer", "amount", "items", "due")}
    filled["asked"] = pending.get("asked", 1)
    amount = find_amount(toks)[0]
    existing, new_name, _ = find_customer_tokens(toks, customers)
    if pending.get("need") == "customer" and not (existing or new_name):
        words = [t.text for t in toks if t.num is None][:3]  # a bare name, e.g. "मनीष"
        new_name = " ".join(words) or None
    if existing or new_name:
        filled["customer"] = existing["name"] if existing else new_name if pending.get("need") == "customer" \
            else filled["customer"]
    if amount and (pending.get("need") == "amount" or not filled.get("amount")):
        filled["amount"] = amount
    due = parse_due(toks)
    if due:
        filled["due"] = due.isoformat()
    return filled


def _complete(parsed: dict) -> bool:
    """Is this a whole new command on its own (so it replaces the question we asked)?"""
    i = parsed["intent"]
    if i in ("multi", "correct", "due_today", "today", "all", "undo", "set_limit", "bye"):
        return True
    if i in ("credit", "payment"):
        return bool(parsed.get("amount") and parsed.get("customer"))
    if i == "promise":
        return bool(parsed.get("customer") and parsed.get("due"))
    return i == "balance"


def run_command(text: str, reply_lang: str, pending: dict | None = None) -> dict:
    """Understand one sentence (or the answer to our last question), update the khata, prepare the reply."""
    customers = ledger.list_customers()
    if pending and is_cancel(text):
        return _result(text, {"intent": "cancelled"}, replies.simple("cancelled", reply_lang))
    parsed = understand(text, customers)
    if pending and not _complete(parsed):
        parsed = _fill(pending, text, customers)
    return _act(parsed, text, reply_lang)


def _result(text: str, parsed: dict, reply: dict, **extra) -> dict:
    parsed["intent_label"] = INTENT_LABELS.get(parsed["intent"], parsed["intent"])
    out = {"said": text, "understood": parsed, "reply": reply, "entry": None, "entries": None, "timeline": None,
           "removed": None, "pending": None, "warnings": [], "promise": None, "end": False}
    out.update(extra)
    out["ledger"] = ledger_snapshot()
    return out


def _act(parsed: dict, text: str, lang: str) -> dict:
    intent, name, amount = parsed["intent"], parsed.get("customer"), parsed.get("amount")

    if intent == "bye":
        return _result(text, parsed, replies.simple("bye", lang), end=True)

    if intent == "correct":  # "हटाओ, गलत सुना... मनीष जी 2000 का सामान ले गए"
        removed = ledger.undo_last()
        res = _act(parsed["then"], text, lang)
        res["removed"] = removed
        res["reply"] = replies.join(replies.simple("corrected", lang) if removed else None, res["reply"])
        res["understood"] = {**parsed, "intent_label": INTENT_LABELS["correct"], "then": res["understood"]}
        return res

    if intent == "multi":
        acts = parsed["actions"]
        money = [a for a in acts if a["intent"] in ("credit", "payment")]
        promises = [a for a in acts if a["intent"] == "promise"]
        if any(not a.get("amount") or a["amount"] <= 0 for a in money):
            return _result(text, parsed, replies.need_amount(name, lang))
        if any(not a.get("customer") for a in acts):
            reply, pending = _ask("customer", {"intent": acts[0]["intent"], "amount": acts[0].get("amount")}, lang)
            return _result(text, parsed, reply, pending=pending)
        batch = uuid.uuid4().hex[:12]
        entries, extra, warnings = [], [], []
        for a in money:
            customer, is_new = _customer_for(a["customer"])
            e = ledger.add_entry(customer["id"], a["intent"], a["amount"], a.get("items"), text, is_new, batch=batch)
            entries.append(e)
            a["customer"], a["new_customer"] = e["customer"], is_new
        for e in entries:
            more, warn = _after_entry(e, lang)
            extra += more
            warnings += warn
        reply = replies.entries_saved(entries, {e["customer"]: ledger.balance(e["customer_id"]) for e in entries}, lang) \
            if len(entries) > 1 else None
        if len(entries) == 1:
            e = entries[0]
            reply = replies.entry_saved(e["kind"], e["customer"], e["amount"], ledger.balance(e["customer_id"]),
                                        bool(e["new_customer"]), lang)
        promise = None
        for a in promises:
            customer, _ = _customer_for(a["customer"])
            if not a.get("due"):
                continue
            promise = ledger.add_promise(customer["id"], a.get("amount"), a["due"], text, batch=batch)
            extra.append(replies.promise_saved(customer["name"], a.get("amount"), a["due"], lang))
        first = entries[0] if entries else None
        return _result(text, parsed, replies.join(reply, *extra), entries=entries if len(entries) > 1 else None,
                       entry=first if len(entries) == 1 else None, warnings=warnings, promise=promise,
                       timeline=ledger.customer_entries(first["customer_id"]) if first else None)

    if intent in ("credit", "payment"):
        if not amount or amount <= 0:
            reply, pending = _ask("amount", parsed, lang)
            return _result(text, parsed, reply, pending=pending)
        if not name:
            reply, pending = _ask("customer", parsed, lang)
            return _result(text, parsed, reply, pending=pending)
        saved = _save_entry(match_customer(name, ledger.list_customers()), name, intent, amount,
                            parsed.get("items"), text, lang)
        parsed["customer"] = saved["customer_name"]
        parsed["new_customer"] = saved["new_customer"]
        return _result(text, parsed, saved["reply"], entry=saved["entry"], timeline=saved["timeline"],
                       warnings=saved["warnings"])

    if intent == "promise":  # "रमेश शुक्रवार को देगा"
        if not name:
            reply, pending = _ask("customer", parsed, lang)
            return _result(text, parsed, reply, pending=pending)
        customer, _ = _customer_for(name)
        parsed["customer"] = customer["name"]
        if not parsed.get("due"):
            reply, pending = _ask("date", parsed, lang)
            return _result(text, parsed, reply, pending=pending)
        promise = ledger.add_promise(customer["id"], amount, parsed["due"], text)
        return _result(text, parsed, replies.promise_saved(customer["name"], amount, parsed["due"], lang),
                       promise=promise, timeline=ledger.customer_entries(customer["id"]))

    if intent == "set_limit":  # "रमेश की लिमिट 2000 रखो"
        customer = match_customer(name, ledger.list_customers()) if name else None
        if not customer:
            return _result(text, parsed, replies.need_customer(lang))
        c = ledger.set_limit(customer["id"], amount)
        parsed["customer"] = c["name"]
        out = [replies.limit_reply(c["name"], amount, lang)]
        if c["over_limit"]:
            out.append(replies.limit_over(c["name"], c["credit_limit"], c["balance"], lang))
        return _result(text, parsed, replies.join(*out))

    if intent == "due_today":  # "आज किससे पैसा आना है?"
        due = ledger.due_list()
        return _result(text, parsed, replies.due_reply(due, lang), due=due)

    if intent == "balance":
        customer = match_customer(name, ledger.list_customers()) if name else None
        reply = replies.balance_reply(customer["name"] if customer else (name or "?"),
                                      ledger.balance(customer["id"]) if customer else None, lang)
        if customer:
            parsed["customer"] = customer["name"]
            parsed["customer_id"] = customer["id"]
        return _result(text, parsed, reply)
    if intent == "today":
        return _result(text, parsed, replies.today_reply(ledger.stats(), lang))
    if intent == "all":
        return _result(text, parsed, replies.all_reply(ledger.stats(), lang))
    if intent == "undo":
        removed = ledger.undo_last()
        return _result(text, parsed, replies.undo_reply(removed, lang), removed=removed)
    return _result(text, parsed, replies.not_understood(lang))


# ---------------------------------------------------------------- pages ---
@app.get("/")
def home(request: Request):
    if auth.enabled() and not request.state.account:
        return FileResponse(STATIC / "login.html")
    return FileResponse(STATIC / "index.html")


# ------------------------------------------------------------ sign in ---
@app.get("/api/auth/config")
def auth_config():
    return {"enabled": auth.enabled(), "client_id": settings.google_client_id,
            "open_signup": not auth.allowed_emails()}


class GoogleIn(BaseModel):
    credential: str


@app.post("/api/auth/google")
def google_sign_in(body: GoogleIn, request: Request):
    if not auth.enabled():
        raise HTTPException(400, "Google sign-in is not turned on (GOOGLE_CLIENT_ID is empty).")
    try:
        user, created = auth.sign_in(body.credential)  # first time for this Gmail = sign-up
    except auth.NotAllowed as exc:
        return JSONResponse({"detail": "not_allowed", "email": str(exc)}, status_code=403)
    except ValueError as exc:  # bad, expired or wrong-app token
        raise HTTPException(401, f"Google sign-in could not be checked: {exc}")
    request.session.clear()
    request.session["user"] = user
    return {"user": user, "created": created}


@app.post("/api/auth/logout")
def sign_out(request: Request):
    request.session.clear()
    return {"ok": True}


def _account_info(account: dict | None) -> dict | None:
    if not account:
        return None
    return {"email": account["email"], "name": account["name"], "picture": account["picture"],
            "shop_name": account["shop_name"], "created_at": account["created_at"]}


@app.get("/api/me")
def me(request: Request):
    account = request.state.account
    return {"auth": auth.enabled(), "user": request.session.get("user") if account else None,
            "account": _account_info(account), "shop_name": _shop(request)}


class MeIn(BaseModel):
    shop_name: str


@app.patch("/api/me")
def update_me(body: MeIn, request: Request):
    if not request.state.account:
        raise HTTPException(400, "Shop name can be changed in .env (SHOP_NAME) while sign-in is off.")
    account = accounts.update(request.state.account["id"], shop_name=body.shop_name)
    ledger.set_setting("shop_name", body.shop_name.strip()[:80] or None)
    return {"account": _account_info(account), "shop_name": _shop(request)}


class ProfileIn(BaseModel):
    shop_name: str | None = None
    upi_id: str | None = None


@app.get("/api/profile")
def get_profile(request: Request):
    return {"shop_name": _shop(request), "upi_id": ledger.get_setting("upi_id"), "version": APP_VERSION}


@app.patch("/api/profile")
def update_profile(body: ProfileIn, request: Request):
    """Shop name (for reminders) and the shop's UPI id (for the pay QR)."""
    if body.shop_name is not None:
        name = body.shop_name.strip()[:80]
        ledger.set_setting("shop_name", name or None)
        if request.state.account:
            request.state.account = accounts.update(request.state.account["id"], shop_name=name)
    if body.upi_id is not None:
        upi = body.upi_id.strip().replace(" ", "")
        if upi and not re.fullmatch(r"[A-Za-z0-9._-]{2,64}@[A-Za-z0-9.-]{2,64}", upi):
            raise HTTPException(400, "That doesn't look like a UPI id (for example: sharmastore@okaxis).")
        ledger.set_setting("upi_id", upi or None)
    return {"shop_name": _shop(request), "upi_id": ledger.get_setting("upi_id"),
            "account": _account_info(request.state.account)}


@app.get("/api/status")
def status(request: Request):
    return {
        "version": APP_VERSION,
        "shop_name": _shop(request),
        "upi_id": ledger.get_setting("upi_id"),
        "gnani_ready": settings.gnani_ready,
        "understanding": "smart" if settings.llm_ready else "basic",
        "stt_model": settings.stt_model,
        "tts_model": settings.tts_model,
        "voices": settings.voices,
    }


# ------------------------------------------------------------- commands ---
@app.post("/api/voice")
async def voice_command(audio: UploadFile = File(...), language: str = Form("hi-IN"),
                        reply_lang: str = Form("hi"), pending: str = Form("")):
    data = await audio.read()
    if len(data) < 2000:
        raise HTTPException(400, "Recording was too short. Hold on a little longer and speak.")
    names = [c["name"] for c in ledger.list_customers()]
    try:
        stt = gnani.transcribe(data, audio.filename or "speech.wav", language, names)
    except gnani.GnaniError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:  # network down etc.
        raise HTTPException(502, f"Could not reach Gnani: {exc}")
    if not stt["transcript"]:
        raise HTTPException(422, "No speech was heard. Please speak a little louder and try again.")
    try:
        asked = json.loads(pending) if pending else None
    except ValueError:
        asked = None
    result = run_command(stt["transcript"], _lang(reply_lang), asked)
    result["stt"] = stt
    return result


class TextIn(BaseModel):
    text: str
    reply_lang: str = "hi"
    pending: dict | None = None  # the question the app asked a moment ago (talk-back)


@app.post("/api/text")
def text_command(body: TextIn):
    if not body.text.strip():
        raise HTTPException(400, "Please type something.")
    return run_command(body.text.strip(), _lang(body.reply_lang), body.pending)


class EntryIn(BaseModel):
    customer_id: int
    kind: str
    amount: float
    note: str | None = None
    reply_lang: str = "hi"


@app.post("/api/entry")
def quick_entry(body: EntryIn):
    """The amount form on a customer's page: add udhaar or jama without speaking."""
    if body.kind not in ("credit", "payment"):
        raise HTTPException(400, "kind must be credit or payment")
    if body.amount <= 0:
        raise HTTPException(400, "Please enter an amount above zero.")
    customer = ledger.get_customer(body.customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    saved = _save_entry(customer, customer["name"], body.kind, body.amount,
                        (body.note or "").strip() or None, None, _lang(body.reply_lang))
    return {"entry": saved["entry"], "reply": saved["reply"], "timeline": saved["timeline"],
            "warnings": saved["warnings"],
            "understood": {"intent": body.kind, "customer": customer["name"], "engine": "form",
                           "new_customer": False},
            "ledger": ledger_snapshot()}


class SpeakIn(BaseModel):
    text: str
    lang: str = "hi"


@app.post("/api/speak")
def speak(body: SpeakIn):
    try:
        audio, mime = gnani.speak(body.text[:600], _lang(body.lang))
    except gnani.GnaniError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)
    except Exception as exc:
        return JSONResponse({"detail": f"Could not reach Gnani: {exc}"}, status_code=502)
    return Response(audio, media_type=mime)


# ---------------------------------------------------------------- khata ---
@app.get("/api/ledger")
def get_ledger():
    return ledger_snapshot()


@app.get("/api/customers/{customer_id}")
def customer_detail(customer_id: int):
    customer = ledger.get_customer(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    return {"customer": customer, "entries": ledger.customer_entries(customer_id)}


class CustomerIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    credit_limit: float | None = None  # send null to remove the limit


@app.patch("/api/customers/{customer_id}")
def edit_customer(customer_id: int, body: CustomerIn):
    """Fix a customer's name, or save their phone number for WhatsApp reminders."""
    if not ledger.get_customer(customer_id):
        raise HTTPException(404, "Customer not found")
    customer = ledger.update_customer(customer_id, body.name, body.phone)
    if "credit_limit" in body.model_fields_set:
        customer = ledger.set_limit(customer_id, body.credit_limit if (body.credit_limit or 0) > 0 else None)
    return {"customer": customer, "entries": ledger.customer_entries(customer_id), "ledger": ledger_snapshot()}


class PromiseIn(BaseModel):
    due_date: str
    amount: float | None = None
    reply_lang: str = "hi"


@app.post("/api/customers/{customer_id}/promise")
def add_promise(customer_id: int, body: PromiseIn):
    customer = ledger.get_customer(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    try:
        datetime.fromisoformat(body.due_date)
    except ValueError:
        raise HTTPException(400, "due_date must look like 2026-11-13")
    ledger.add_promise(customer_id, body.amount if (body.amount or 0) > 0 else None, body.due_date[:10])
    return {"customer": ledger.get_customer(customer_id), "ledger": ledger_snapshot(),
            "reply": replies.promise_saved(customer["name"], body.amount, body.due_date[:10], _lang(body.reply_lang))}


@app.delete("/api/promises/{promise_id}")
def delete_promise(promise_id: int):
    p = ledger.get_promise(promise_id)
    if not p or not ledger.cancel_promise(promise_id):
        raise HTTPException(404, "Promise not found")
    return {"customer": ledger.get_customer(p["customer_id"]), "ledger": ledger_snapshot()}


@app.get("/api/due")
def due(lang: str = "hi"):
    d = ledger.due_list()
    return {**d, "reply": replies.due_reply(d, _lang(lang))}


@app.delete("/api/entries/{entry_id}")
def delete_entry(entry_id: int):
    removed = ledger.delete_entry(entry_id)
    if not removed:
        raise HTTPException(404, "Entry not found")
    return {"removed": removed, "entries": ledger.customer_entries(removed["customer_id"]),
            "customer": ledger.get_customer(removed["customer_id"]), "ledger": ledger_snapshot()}


@app.get("/api/export.csv")
def export_current():
    """Download the current khata for Excel."""
    day = datetime.now().strftime("%Y-%m-%d")
    return Response("\ufeff" + ledger.archive_csv(None), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="bol-khata-{day}.csv"'})


@app.get("/api/reminder/{customer_id}")
def reminder(customer_id: int, request: Request, lang: str = "hi"):
    customer = ledger.get_customer(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    return replies.reminder(customer["name"], max(customer["balance"], 0), _shop(request), _lang(lang),
                            ledger.get_setting("upi_id"))


@app.get("/api/summary")
def summary(kind: str = "both", lang: str = "hi"):
    s = ledger.stats()
    if kind == "all":
        return replies.all_reply(s, _lang(lang))
    if kind == "today":
        return replies.today_reply(s, _lang(lang))
    return replies.summary_reply(s, _lang(lang))


@app.post("/api/undo")
def undo(lang: str = "hi"):
    removed = ledger.undo_last()
    return {"reply": replies.undo_reply(removed, _lang(lang)), "removed": removed, "ledger": ledger_snapshot()}


@app.post("/api/demo")
def demo_data(lang: str = "hi"):
    saved = ledger.seed_demo(_lang(lang))  # your real entries are saved first, never deleted
    return {**ledger_snapshot(), "saved": saved}


# --------------------------------------------------------- saved khatas ---
@app.post("/api/archive")
def start_new_khata():
    """'Start a new khata': the current one is saved in Saved khatas, then the page is empty."""
    saved = ledger.archive_current("manual")
    return {**ledger_snapshot(), "saved": saved}


@app.get("/api/archives")
def archives():
    return {"archives": ledger.list_archives()}


@app.get("/api/archives/{archive_id}")
def archive_detail(archive_id: int):
    detail = ledger.archive_detail(archive_id)
    if not detail:
        raise HTTPException(404, "Saved khata not found")
    return detail


@app.get("/api/archives/{archive_id}/csv")
def archive_csv(archive_id: int):
    data = ledger.archive_csv(archive_id)
    if data is None:
        raise HTTPException(404, "Saved khata not found")
    archive = ledger.get_archive(archive_id)
    day = datetime.fromisoformat(archive["created_at"]).strftime("%Y-%m-%d")
    return Response("﻿" + data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="bol-khata-{day}-{archive_id}.csv"'})


@app.delete("/api/archives/{archive_id}")
def delete_archive(archive_id: int):
    if not ledger.delete_archive(archive_id):
        raise HTTPException(404, "Saved khata not found")
    return {"archives": ledger.list_archives(), "ledger": ledger_snapshot()}
