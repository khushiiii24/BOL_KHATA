"""One sentence, several entries. Run with:  python -m pytest -q"""
import pytest

from app.understand import rules_understand

CUSTOMERS = [{"id": 1, "name": "रमेश"}, {"id": 2, "name": "सुनीता"}, {"id": 3, "name": "शर्मा"},
             {"id": 4, "name": "पप्पू"}]


def actions(text):
    out = rules_understand(text, CUSTOMERS)
    acts = out.get("actions") or [out]
    return [(a["intent"], a["customer"], a["amount"]) for a in acts]


@pytest.mark.parametrize("text,expected", [
    # the sentence that was saved as "₹2,000 advance"
    ("मनीष जी ने 2000 का सामान लिया और वो 1000 जमा करके गए हैं",
     [("credit", "मनीष", 2000), ("payment", "मनीष", 1000)]),
    ("manish ji ne 2000 ka saman liya aur wo 1000 jama karke gye h",
     [("credit", "Manish", 2000), ("payment", "Manish", 1000)]),
    ("मनीष जी ने दो हज़ार का सामान लिया और एक हज़ार जमा करके गए",
     [("credit", "मनीष", 2000), ("payment", "मनीष", 1000)]),
    # speech-to-text often drops "और" or adds a comma
    ("मनीष जी ने 2000 का सामान लिया 1000 जमा करके गए",
     [("credit", "मनीष", 2000), ("payment", "मनीष", 1000)]),
    ("मनीष जी ने 2000 का सामान लिया, 1000 जमा करके गए",
     [("credit", "मनीष", 2000), ("payment", "मनीष", 1000)]),
    # two people
    ("रमेश ने 500 दिए और सुनीता ने 300 का सामान लिया",
     [("payment", "रमेश", 500), ("credit", "सुनीता", 300)]),
    ("रमेश 2000 उधार, सुनीता 500 जमा", [("credit", "रमेश", 2000), ("payment", "सुनीता", 500)]),
    # two items, one verb at the end
    ("रमेश ने 200 का आटा और 300 का तेल लिया", [("credit", "रमेश", 200), ("credit", "रमेश", 300)]),
    # a total or a balance remark is not a new entry
    ("रमेश ने 200 का आटा और 300 का तेल लिया, कुल 500", [("credit", "रमेश", 200), ("credit", "रमेश", 300)]),
    ("रमेश ने 2000 का सामान लिया और 1000 दे गए, अब 1000 बाकी है",
     [("credit", "रमेश", 2000), ("payment", "रमेश", 1000)]),
    ("रमेश के 1500 बाकी थे, उन्होंने 500 दिए, अब 1000 बाकी है", [("payment", "रमेश", 500)]),
    ("रमेश ने 1240 में से 500 जमा किए", [("payment", "रमेश", 500)]),
    ("Sunita paid 500 out of 1240", [("payment", "सुनीता", 500)]),
    # the shop is speaking: "gave goods, took 1000" = 1000 received
    ("रमेश को 2000 का सामान दिया और 1000 रुपये लिए", [("credit", "रमेश", 2000), ("payment", "रमेश", 1000)]),
    ("पप्पू को 500 का सामान दिया और उसने 200 दिए", [("credit", "पप्पू", 500), ("payment", "पप्पू", 200)]),
    ("शर्मा जी 700 रुपये दे गए और 250 का दूध ले गए", [("payment", "शर्मा", 700), ("credit", "शर्मा", 250)]),
    # English
    ("Ramesh took 2000 worth of goods and paid 1000", [("credit", "रमेश", 2000), ("payment", "रमेश", 1000)]),
    ("Ramesh took 2000, paid 500", [("credit", "रमेश", 2000), ("payment", "रमेश", 500)]),
    # other languages
    ("मनीष यांनी 2000 रुपयांचे सामान घेतले आणि 1000 रुपये जमा केले",
     [("credit", "मनीष", 2000), ("payment", "मनीष", 1000)]),
    ("મનીષે 2000 રૂપિયાનો સામાન લીધો અને 1000 રૂપિયા જમા કર્યા",
     [("credit", "મનીષ", 2000), ("payment", "મનીષ", 1000)]),
    ("মনীষ 2000 টাকার জিনিস নিলেন এবং 1000 টাকা জমা দিলেন",
     [("credit", "মনীষ", 2000), ("payment", "মনীষ", 1000)]),
    ("మనీష్ 2000 రూపాయలు అప్పు తీసుకున్నారు మరియు 1000 రూపాయలు జమ చేశారు",
     [("credit", "మనీష్", 2000), ("payment", "మనీష్", 1000)]),
    ("ಮನೀಷ್ 2000 ರೂಪಾಯಿ ಸಾಲ ತೆಗೆದುಕೊಂಡರು ಮತ್ತು 1000 ರೂಪಾಯಿ ಜಮಾ ಮಾಡಿದರು",
     [("credit", "ಮನೀಷ್", 2000), ("payment", "ಮನೀಷ್", 1000)]),
])
def test_several_entries(text, expected):
    assert actions(text) == expected


@pytest.mark.parametrize("text,expected", [
    # quantities, dates and "from" are not amounts
    ("रमेश ने 5 अंडे और 2 ब्रेड लिए 120 रुपये के", [("credit", "रमेश", 120)]),
    ("15 तारीख को रमेश ने 500 दिए", [("payment", "रमेश", 500)]),
    ("रमेश 80 दूध", [("credit", "रमेश", 80)]),
    # "took" words
    ("रमेश से 500 लिए", [("payment", "रमेश", 500)]),
    ("रमेश 500 का सामान ले गए", [("credit", "रमेश", 500)]),
])
def test_single_entry_words(text, expected):
    assert actions(text) == expected


def test_items_go_with_their_own_amount():
    out = rules_understand("रमेश ने 200 का आटा और 300 का तेल लिया", CUSTOMERS)
    assert [a["items"] for a in out["actions"]] == ["आटा", "तेल"]


def test_save_and_undo_together(tmp_path, monkeypatch):
    """Both entries are saved, the balance is right, and one undo removes both."""
    from fastapi.testclient import TestClient

    import app.main
    from app.config import settings

    monkeypatch.setattr(settings, "google_client_id", "")
    monkeypatch.setattr(settings, "llm_key", "")
    monkeypatch.setattr(settings, "db_path", tmp_path / "khata.db")  # an empty khata just for this test

    c = TestClient(app.main.app)
    res = c.post("/api/text", json={"text": "मनीष जी ने 2000 का सामान लिया और वो 1000 जमा करके गए हैं",
                                    "reply_lang": "hi"}).json()
    assert [(e["kind"], e["amount"]) for e in res["entries"]] == [("credit", 2000), ("payment", 1000)]
    manish = next(x for x in res["ledger"]["customers"] if x["name"] == "मनीष")
    assert manish["balance"] == 1000
    assert "₹1,000 बाकी" in res["reply"]["text"]

    res = c.post("/api/text", json={"text": "manish ne 300 ka doodh liya", "reply_lang": "en"}).json()
    assert res["entry"]["amount"] == 300

    first = c.post("/api/undo?lang=en").json()   # removes only the ₹300
    assert first["removed"]["amount"] == 300
    second = c.post("/api/undo?lang=en").json()  # removes the 2000 + 1000 together
    assert len(second["removed"]["batch_entries"]) == 2
    assert "2 entries" in second["reply"]["text"]
    assert second["ledger"]["customers"] == []
