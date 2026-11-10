"""Run with:  python -m pytest -q"""
import pytest

from app.numbers import hindi_words, inr, english_words
from app.understand import rules_understand, skeleton, tokenize

CUSTOMERS = [{"id": 1, "name": "रमेश"}, {"id": 2, "name": "सुनीता"}, {"id": 3, "name": "शर्मा"},
             {"id": 4, "name": "पप्पू"}, {"id": 5, "name": "इमरान"}]


@pytest.mark.parametrize("text,intent,customer,amount", [
    ("रमेश भैया दो किलो आटा, एक तेल, 340 रुपये उधार", "credit", "रमेश", 340),
    ("Ramesh bhaiya 2 kilo aata 340 rupaye udhaar", "credit", "रमेश", 340),
    ("शर्मा जी ने 500 रुपये जमा किए", "payment", "शर्मा", 500),
    ("Sharma ji ne 500 diye", "payment", "शर्मा", 500),
    ("सुनीता दीदी का कितना बाकी है?", "balance", "सुनीता", None),
    ("sunita ka kitna baaki hai", "balance", "सुनीता", None),
    ("आज का हिसाब बताओ", "today", None, None),
    ("सबसे ज़्यादा किसका बाकी है", "all", None, None),
    ("गलत हो गया, हटाओ", "undo", None, None),
    ("पप्पू को ₹160 का दूध ब्रेड दिया", "credit", "पप्पू", 160),
    ("इमरान से 200 मिले", "payment", "इमरान", 200),
    ("मोहन जी के खाते में साढ़े तीन सौ लिख दो", "credit", "मोहन", 350),
    ("Vikram ne dedh sau lautaye", "payment", "Vikram", 150),
    ("नीतू को 1,240 रुपये का राशन उधार", "credit", "नीतू", 1240),
    ("एक लाख बीस हज़ार रुपये उधार अनिल", "credit", "अनिल", 120000),
    ("₹300 उधार", "credit", None, 300),
    # real sentences heard by Gnani Prisma
    ("सुनीता जी, 300 रुपये दे गए हैं।", "payment", "सुनीता", 300),
    ("सुनीता के उधार में हुए हैं 600 रुपये।", "credit", "सुनीता", 600),
    ("रमेश भैया, 2 किलो आटा, 340 रुपये उधार।", "credit", "रमेश", 340),
    ("रमेश ने उधार के 200 रुपये लौटाए", "payment", "रमेश", 200),
    ("Ramesh udhaar ke 500 jama kar gaye", "payment", "रमेश", 500),
    ("रमेश को 300 रुपये उधार दिए", "credit", "रमेश", 300),
    ("इमरान 150 रुपये दे गया", "payment", "इमरान", 150),
])
def test_rules(text, intent, customer, amount):
    out = rules_understand(text, CUSTOMERS)
    assert out["intent"] == intent, out
    assert out["customer"] == customer, out
    assert out["amount"] == amount, out


def test_items_note():
    out = rules_understand("रमेश भैया दो किलो आटा, एक तेल, 340 रुपये उधार", CUSTOMERS)
    assert out["items"] == "दो किलो आटा एक तेल"


def test_cross_script_names():
    assert skeleton("रमेश") == skeleton("Ramesh")
    assert skeleton("शर्मा") == skeleton("Sharma")
    assert skeleton("पप्पू") == skeleton("Pappu")
    assert skeleton("सुनीता") == skeleton("Sunita")
    assert skeleton("इमरान") == skeleton("Imran")


def test_numbers():
    assert hindi_words(340) == "तीन सौ चालीस"
    assert hindi_words(1240) == "एक हज़ार दो सौ चालीस"
    assert hindi_words(150000) == "एक लाख पचास हज़ार"
    assert english_words(124000) == "one lakh twenty-four thousand"
    assert inr(124000) == "₹1,24,000"
    assert inr(340) == "₹340"
    assert [t.num for t in tokenize("ढाई सौ") if t.num] == [250]
    assert [t.num for t in tokenize("सवा सौ") if t.num] == [125]
    assert [t.num for t in tokenize("पौने दो सौ") if t.num] == [175]


# ------------------------------------------------------------ other languages (basic mode)
REGIONAL = [
    # Marathi
    ("रमेश, 340 रुपये उधार", "credit", "रमेश", 340),
    ("शर्मा यांनी 500 रुपये जमा केले", "payment", "शर्मा", 500),
    ("सुनीताचे किती बाकी आहे?", "balance", "सुनीता", None),
    ("आजचा हिशोब सांगा", "today", None, None),
    ("चूक झाली, काढून टाका", "undo", None, None),
    # Gujarati
    ("રમેશ, 340 રૂપિયા ઉધાર", "credit", "रमेश", 340),
    ("શર્માએ 500 રૂપિયા જમા કર્યા", "payment", "शर्मा", 500),
    ("સુનીતાના કેટલા બાકી છે?", "balance", "सुनीता", None),
    ("આજનો હિસાબ કહો", "today", None, None),
    ("ભૂલ થઈ, કાઢી નાખો", "undo", None, None),
    # Bengali
    ("রমেশ, 340 টাকা ধার", "credit", "रमेश", 340),
    ("শর্মা 500 টাকা জমা দিলেন", "payment", "शर्मा", 500),
    ("সুনীতার কত বাকি?", "balance", "सुनीता", None),
    ("আজকের হিসাব বলো", "today", None, None),
    ("ভুল হয়েছে, মুছে দাও", "undo", None, None),
    # Tamil
    ("ரமேஷ், 340 ரூபாய் கடன்", "credit", "रमेश", 340),
    ("சர்மா 500 ரூபாய் கொடுத்தார்", "payment", "शर्मा", 500),
    ("சுனிதா எவ்வளவு பாக்கி?", "balance", "सुनीता", None),
    ("இன்றைய கணக்கு சொல்லு", "today", None, None),
    ("தவறு, நீக்கு", "undo", None, None),
    ("முருகன், 200 ரூபாய் கடன்", "credit", "முருகன்", 200),
    # Telugu
    ("రమేష్, 340 రూపాయలు అప్పు", "credit", "रमेश", 340),
    ("శర్మ గారు 500 రూపాయలు జమ చేశారు", "payment", "शर्मा", 500),
    ("సునీత ఎంత బాకీ?", "balance", "सुनीता", None),
    ("ఈరోజు లెక్క చెప్పు", "today", None, None),
    ("తప్పు అయింది, తీసేయి", "undo", None, None),
    # Kannada
    ("ರಮೇಶ್, 340 ರೂಪಾಯಿ ಸಾಲ", "credit", "रमेश", 340),
    ("ಶರ್ಮಾ ಅವರು 500 ರೂಪಾಯಿ ಜಮಾ ಮಾಡಿದರು", "payment", "शर्मा", 500),
    ("ಸುನೀತಾ ಎಷ್ಟು ಬಾಕಿ?", "balance", "सुनीता", None),
    ("ಇಂದಿನ ಲೆಕ್ಕ ಹೇಳು", "today", None, None),
    ("ತಪ್ಪಾಯಿತು, ತೆಗೆದುಹಾಕು", "undo", None, None),
    # English
    ("Ramesh, 340 rupees udhaar", "credit", "रमेश", 340),
    ("Sharma paid 500 rupees", "payment", "शर्मा", 500),
    ("How much does Sunita owe?", "balance", "सुनीता", None),
    ("Today's summary", "today", None, None),
    ("That was wrong, undo", "undo", None, None),
]


@pytest.mark.parametrize("text,intent,customer,amount", REGIONAL)
def test_regional(text, intent, customer, amount):
    out = rules_understand(text, CUSTOMERS)
    assert out["intent"] == intent, out
    assert out["customer"] == customer, out
    assert out["amount"] == amount, out


def test_new_name_does_not_prefix_match_through_llm_path():
    from app.understand import match_customer
    assert match_customer("Rameshwar", CUSTOMERS) is None


def test_replies_every_language():
    from app import replies
    for lang in replies.LANGS:
        r = replies.entry_saved("payment", "रमेश", 500, 0, False, lang)
        assert r["text"] and r["speech"] and r["lang"] == lang
        assert "₹500" in r["text"]
        replies.today_reply({"credit_count_today": 2, "credit_today": 500, "payment_today": 100}, lang)
        replies.all_reply({"top": {"name": "x", "balance": 5}, "owing_count": 1, "total_due": 5}, lang)
        replies.reminder("x", 100, "Shop", lang)
        replies.undo_reply({"kind": "credit", "customer": "x", "amount": 3}, lang)
        replies.not_understood(lang)


# ------------------------------------------------------------ names shown in the reader's script
@pytest.mark.parametrize("name,lang,expected", [
    ("रमेश", "en", "Ramesh"), ("सुनीता", "en", "Sunita"), ("शर्मा", "en", "Sharma"),
    ("रमेश", "ta", "ரமேஷ்"), ("सुनीता", "bn", "সুনীতা"), ("शर्मा", "gu", "શર્મા"),
    ("रमेश", "kn", "ರಮೇಶ್"), ("ரமேஷ்", "hi", "रमेश"), ("సునీత", "en", "Sunita"),
    ("Ramesh", "ta", "Ramesh"), ("रमेश", "hi", "रमेश"),
])
def test_name_for(name, lang, expected):
    from app.translit import name_for
    assert name_for(name, lang) == expected


def test_reply_uses_reader_script():
    from app import replies
    r = replies.entry_saved("credit", "रमेश", 340, 890, False, "en")
    assert "₹340" in r["text"] and "Ramesh" in r["text"] and "₹890" in r["text"]  # wording varies on purpose
    assert "ரமேஷ்" in replies.entry_saved("credit", "रमेश", 340, 890, False, "ta")["speech"]
