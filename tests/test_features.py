"""Talk-back, promises, limits, trust score, UPI and your real sentences. Run with:  python -m pytest -q"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.understand import parse_due, rules_understand, tokenize

C = [{"id": 1, "name": "रमेश"}, {"id": 2, "name": "सीता"}, {"id": 3, "name": "मनीष"}, {"id": 4, "name": "रामू"}]


def acts(text):
    out = rules_understand(text, C)
    if out["intent"] == "correct":
        out = out["then"]
    return [(a["intent"], a["customer"], a["amount"]) for a in (out.get("actions") or [out])]


# ---------------------------------------------------------------- sentences recorded on a real laptop
@pytest.mark.parametrize("text,expected", [
    ("सीता जी 600 रुपये देकर गई हैं।", [("payment", "सीता", 600)]),
    ("सीता 1000 रुपये का सामान लेकर गई है, लेकिन... 600 रुपये जमा करके गई है।",
     [("credit", "सीता", 1000), ("payment", "सीता", 600)]),
    ("रामू 2000 का सामान लेकर गया है और jama बस 1000 करके गया है।", [("credit", "रामू", 2000), ("payment", "रामू", 1000)]),
    ("मनीष जी 2000 रुपये का सामान लेके गए हैं और जमा सिर्फ 1000 करके गए हैं।",
     [("credit", "मनीष", 2000), ("payment", "मनीष", 1000)]),
    ("मनीष भी 1000 रुपये का उधार लेकर गए हैं।", [("credit", "मनीष", 1000)]),
    ("मनीष जी 600 रुपये जमा कर गए हैं।", [("payment", "मनीष", 600)]),
    # "हटाओ, गलत सुना" + the right sentence = correction
    ("हटाओ, आपने गलत सुन लिया है। मनीष जी 2000 का सामान लेके गए हैं और सिर्फ... 1000 रुपये दे के गए हैं",
     [("credit", "मनीष", 2000), ("payment", "मनीष", 1000)]),
    ("रमेश 500 नहीं 400 उधार", [("credit", "रमेश", 400)]),
])
def test_real_sentences(text, expected):
    assert acts(text) == expected


def test_correction_is_marked():
    assert rules_understand("हटाओ, गलत सुना। रमेश 300 उधार", C)["intent"] == "correct"
    assert rules_understand("रमेश के 500 गलत हैं", C)["intent"] == "undo"


# ---------------------------------------------------------------- promises, limits, questions
def test_promises():
    p = rules_understand("रमेश कल 500 देगा", C)
    assert (p["intent"], p["customer"], p["amount"]) == ("promise", "रमेश", 500)
    assert p["due"] == (date.today() + timedelta(days=1)).isoformat()
    m = rules_understand("रमेश ने 500 दिए और बाकी शुक्रवार को देगा", C)
    assert [a["intent"] for a in m["actions"]] == ["payment", "promise"]
    assert m["actions"][1]["amount"] is None and m["actions"][1]["customer"] == "रमेश"
    assert rules_understand("Ramesh will pay 500 on Friday", C)["intent"] == "promise"
    assert rules_understand("रमेश देगा", C)["due"] is None  # the app will ask "कब तक?"


def test_dates():
    today = date(2026, 11, 8)  # a Sunday
    due = lambda s: parse_due(tokenize(s), today).isoformat()  # noqa: E731
    assert due("कल") == "2026-11-09"
    assert due("परसों") == "2026-11-10"
    assert due("शुक्रवार को") == "2026-11-13"
    assert due("रविवार") == "2026-11-15"          # next Sunday, not today
    assert due("5 तारीख") == "2026-12-05"         # already past this month
    assert due("15 तारीख को") == "2026-11-15"
    assert due("3 दिन में") == "2026-11-11"
    assert due("महीने के आखिर में") == "2026-11-30"


@pytest.mark.parametrize("text,intent", [
    ("रमेश की लिमिट 2000 रखो", "set_limit"), ("आज किससे पैसा आना है?", "due_today"), ("Who pays today?", "due_today"),
    ("बस धन्यवाद", "bye"), ("आज का हिसाब बताओ", "today"), ("रमेश को उधार लिखो", "credit"),
])
def test_other_intents(text, intent):
    assert rules_understand(text, C)["intent"] == intent


# ---------------------------------------------------------------- through the server
@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "google_client_id", "")
    monkeypatch.setattr(settings, "llm_key", "")
    monkeypatch.setattr(settings, "db_path", tmp_path / "khata.db")
    return TestClient(main.app)


def say(c, text, pending=None, lang="hi"):
    return c.post("/api/text", json={"text": text, "reply_lang": lang, "pending": pending}).json()


def test_talk_back_asks_for_the_amount_then_saves(client):
    r = say(client, "रमेश को उधार लिखो")
    assert r["pending"]["need"] == "amount" and "कितने रुपये" in r["reply"]["text"]
    r = say(client, "तीन सौ", r["pending"])
    assert r["entry"]["amount"] == 300 and r["entry"]["customer"] == "रमेश" and r["pending"] is None


def test_talk_back_asks_for_the_name_and_can_be_cancelled(client):
    r = say(client, "500 उधार लिखो")
    assert r["pending"]["need"] == "customer"
    r2 = say(client, "मनीष", r["pending"])
    assert r2["entry"]["customer"] == "मनीष" and r2["entry"]["amount"] == 500
    r = say(client, "सीता को उधार लिखो")
    r = say(client, "रहने दो", r["pending"])
    assert r["understood"]["intent"] == "cancelled" and r["pending"] is None


def test_talk_back_gives_up_after_two_tries(client):
    r = say(client, "रमेश को उधार लिखो")
    r = say(client, "हम्म", r["pending"])
    assert r["pending"] and r["pending"]["asked"] == 2
    r = say(client, "पता नहीं", r["pending"])
    assert r["pending"] is None


def test_promise_kept_and_due_list(client):
    say(client, "रमेश 500 उधार")
    r = say(client, "रमेश आज 300 देगा")
    assert r["promise"]["amount"] == 300
    due = client.get("/api/due").json()
    assert [p["name"] for p in due["today"]] == ["रमेश"] and "रमेश" in due["reply"]["text"]
    r = say(client, "रमेश ने 300 दिए")
    assert any(w["kind"] == "kept" for w in r["warnings"]) and "वादा निभाया" in r["reply"]["text"]
    ramesh = next(c for c in r["ledger"]["customers"] if c["name"] == "रमेश")
    assert ramesh["promise"] is None and ramesh["trust"]["kept"] == 1


def test_promise_asks_for_a_date(client):
    say(client, "सीता 400 उधार")
    r = say(client, "सीता देगी")
    assert r["pending"]["need"] == "date"
    r = say(client, "परसों", r["pending"])
    assert r["promise"]["due_date"] == (date.today() + timedelta(days=2)).isoformat()
    assert say(client, "हटाओ")["removed"]["kind"] == "promise"  # undo removes the promise


def test_limit_warning(client):
    say(client, "रमेश 500 उधार")
    r = say(client, "रमेश की लिमिट 600 रखो")
    assert "सीमा" in r["reply"]["text"]
    r = say(client, "रमेश 200 का सामान ले गया")
    assert r["warnings"][0]["kind"] == "limit" and r["warnings"][0]["balance"] == 700
    assert "ध्यान दें" in r["reply"]["text"]


def test_correction_replaces_the_wrong_entry(client):
    say(client, "मनीष 2000 जमा")  # heard wrong
    r = say(client, "हटाओ, गलत सुना। मनीष जी 2000 का सामान ले गए और 1000 जमा किए")
    assert r["removed"]["amount"] == 2000
    manish = next(c for c in r["ledger"]["customers"] if c["name"] == "मनीष")
    assert manish["balance"] == 1000


def test_trust_scores_on_sample_data(client):
    data = client.post("/api/demo?lang=hi").json()
    labels = {c["name"]: c["trust"]["label"] for c in data["customers"]}
    assert labels["शर्मा"] == "good" and labels["सुनीता"] == "risk"
    s = data["stats"]
    assert s["over_limit_count"] == 1 and s["due_today_count"] == 2 and sum(s["aging"]) == s["total_due"]


def test_upi_and_reminder(client):
    assert client.patch("/api/profile", json={"upi_id": "not a upi"}).status_code == 400
    r = client.patch("/api/profile", json={"upi_id": "sharmastore@okaxis", "shop_name": "Sharma Store"}).json()
    assert r["upi_id"] == "sharmastore@okaxis"
    cid = say(client, "रमेश 500 उधार")["entry"]["customer_id"]
    rem = client.get(f"/api/reminder/{cid}?lang=hi").json()
    assert "sharmastore@okaxis" in rem["text"] and "sharmastore" not in rem["speech"] and "Sharma Store" in rem["text"]
    assert client.get("/api/status").json()["version"] == main.APP_VERSION
