"""Sign-in and separate accounts, with a fake Google check. Run with:  python -m pytest -q"""
import pytest
from fastapi.testclient import TestClient

from app import auth, ledger, main
from app.config import settings

FAKE_TOKENS = {
    "asha-token": {"sub": "1001", "email": "asha@gmail.com", "email_verified": True, "name": "Asha Patel", "picture": None},
    "ravi-token": {"sub": "2002", "email": "ravi@gmail.com", "email_verified": True, "name": "Ravi Kumar"},
    "unverified-token": {"sub": "3003", "email": "x@gmail.com", "email_verified": False},
}


@pytest.fixture
def signin_on(monkeypatch, tmp_path):
    """Sign-in turned on, with an empty data folder just for this test."""
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "allowed_emails", "")
    monkeypatch.setattr(settings, "llm_key", "")
    monkeypatch.setattr(settings, "db_path", tmp_path / "khata.db")

    def fake_verify(token):
        if token not in FAKE_TOKENS:
            raise ValueError("Token used too late / wrong audience")
        return FAKE_TOKENS[token]

    monkeypatch.setattr(auth, "verify_google_token", fake_verify)
    return tmp_path


def browser(token=None):
    """A separate browser (its own cookies), signed in with `token` if given."""
    c = TestClient(main.app)
    if token:
        r = c.post("/api/auth/google", json={"credential": token})
        assert r.status_code == 200, r.text
    return c


def names(c):
    return sorted(x["name"] for x in c.get("/api/ledger").json()["customers"])


def test_data_is_locked_without_sign_in(signin_on):
    c = browser()
    assert c.get("/api/ledger").status_code == 401
    assert c.post("/api/text", json={"text": "रमेश 300 उधार"}).status_code == 401
    assert c.get("/api/export.csv").status_code == 401
    assert "login.js" in c.get("/").text          # the login page is shown instead


def test_sign_up_then_log_in(signin_on):
    c = TestClient(main.app)
    first = c.post("/api/auth/google", json={"credential": "asha-token"}).json()
    assert first["created"] is True and first["user"]["email"] == "asha@gmail.com"   # sign-up
    assert "app.js" in c.get("/").text                                               # the khata itself
    me = c.get("/api/me").json()
    assert me["account"]["shop_name"] is None and me["shop_name"] == "Asha Patel"   # asks for a shop name
    c.post("/api/auth/logout")
    assert c.get("/api/ledger").status_code == 401
    again = c.post("/api/auth/google", json={"credential": "asha-token"}).json()
    assert again["created"] is False                                                 # login, same account


def test_every_gmail_has_its_own_khata(signin_on):
    asha, ravi = browser("asha-token"), browser("ravi-token")
    asha.post("/api/text", json={"text": "रमेश 300 उधार"})
    asha.post("/api/text", json={"text": "सुनीता 500 उधार"})
    ravi.post("/api/text", json={"text": "इमरान 700 उधार"})
    assert names(asha) == ["रमेश", "सुनीता"]
    assert names(ravi) == ["इमरान"]
    assert "इमरान" not in asha.get("/api/export.csv").text
    # Ravi can't open Asha's 2nd customer by guessing its number
    asha_ids = [x["id"] for x in asha.get("/api/ledger").json()["customers"]]
    assert ravi.get(f"/api/customers/{max(asha_ids)}").status_code == 404
    # Ravi's undo only touches Ravi's khata
    ravi.post("/api/undo")
    assert names(asha) == ["रमेश", "सुनीता"] and names(ravi) == []
    # separate files on disk
    assert (signin_on / "users" / "g1001" / "khata.db").exists()
    assert (signin_on / "users" / "g2002" / "khata.db").exists()
    assert (signin_on / "users" / "g2002" / "email.txt").read_text().strip() == "ravi@gmail.com"


def test_shop_name_is_per_account(signin_on):
    asha, ravi = browser("asha-token"), browser("ravi-token")
    asha.patch("/api/me", json={"shop_name": "Patel Kirana"})
    assert asha.get("/api/status").json()["shop_name"] == "Patel Kirana"
    assert ravi.get("/api/status").json()["shop_name"] == "Ravi Kumar"


def test_invite_only_list(signin_on, monkeypatch):
    monkeypatch.setattr(settings, "allowed_emails", "asha@gmail.com,ravi@gmail.com")
    asha, ravi = browser("asha-token"), browser("ravi-token")
    assert TestClient(main.app).get("/api/auth/config").json()["open_signup"] is False
    # Ravi is removed from the list: locked out on his very next request, Asha is not
    monkeypatch.setattr(settings, "allowed_emails", "asha@gmail.com")
    assert ravi.get("/api/ledger").status_code == 401
    assert asha.get("/api/ledger").status_code == 200
    r = TestClient(main.app).post("/api/auth/google", json={"credential": "ravi-token"})
    assert r.status_code == 403 and r.json()["detail"] == "not_allowed"


def test_bad_tokens_are_refused(signin_on):
    c = TestClient(main.app)
    assert c.post("/api/auth/google", json={"credential": "unverified-token"}).status_code == 403
    assert c.post("/api/auth/google", json={"credential": "forged"}).status_code == 401
    assert c.get("/api/ledger").status_code == 401


def test_old_entries_move_into_the_first_account(signin_on, monkeypatch):
    # entries made while sign-in was off
    monkeypatch.setattr(settings, "google_client_id", "")
    TestClient(main.app).post("/api/text", json={"text": "रमेश 300 उधार"})
    assert (signin_on / "khata.db").exists()
    # sign-in turned on: the first person to sign up keeps them, the next one starts empty
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    asha, ravi = browser("asha-token"), browser("ravi-token")
    assert names(asha) == ["रमेश"]
    assert names(ravi) == []
    assert not (signin_on / "khata.db").exists()


def test_open_when_sign_in_is_off(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "google_client_id", "")
    monkeypatch.setattr(settings, "db_path", tmp_path / "khata.db")
    c = TestClient(main.app)
    assert c.get("/api/ledger").status_code == 200
    assert "app.js" in c.get("/").text
    assert c.get("/api/me").json()["account"] is None


def test_no_khata_without_a_request():
    """Outside a request nothing is chosen, so the code refuses instead of guessing a shared file."""
    import contextvars
    with pytest.raises(RuntimeError):
        contextvars.Context().run(ledger.list_customers)
