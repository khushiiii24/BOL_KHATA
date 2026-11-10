"""What Bol Khata says back, in 8 languages.

Every reply has two versions:
  text   - shown on screen, with ₹ and digits      "रमेश जी के खाते में ₹340 उधार लिख दिया।"
  speech - sent to Gnani Timbre                    "... तीन सौ चालीस रुपये उधार लिख दिया।"
For Hindi and English, numbers are spoken as words (Gnani's docs recommend this).
For the other languages, numbers are sent as digits with the local word for rupees.
"""

from __future__ import annotations

import random
from datetime import date

from .numbers import english_words, hindi_words, inr
from .translit import name_for

LANGS = ("hi", "en", "mr", "gu", "bn", "ta", "te", "kn")

CURRENCY = {"hi": "रुपये", "en": "rupees", "mr": "रुपये", "gu": "રૂપિયા", "bn": "টাকা",
            "ta": "ரூபாய்", "te": "రూపాయలు", "kn": "ರೂಪಾಯಿ"}

T = {
    "hi": {
        "new": "{name} जी का नया खाता खोल दिया।",
        "credit": "हो गया! {name} जी के खाते में {amt} उधार लिख दिया।",
        "payment": "बढ़िया! {name} जी ने {amt} जमा कर दिए।",
        "bal_due": "अब कुल {bal} बाकी है।", "bal_adv": "{name} जी के {bal} एडवांस में जमा हैं।", "bal_zero": "पूरा हिसाब बराबर हो गया।",
        "q_due": "{name} जी पर कुल {bal} बाकी है।", "q_zero": "{name} जी का हिसाब बराबर है, कुछ बाकी नहीं।",
        "q_none": "{name} नाम का कोई खाता अभी नहीं है।",
        "today_none": "आज अभी तक कोई एंट्री नहीं हुई।", "today_credit": "आज {n} बार उधार दिया, कुल {amt}।",
        "today_paid": "और {amt} जमा हुए।",
        "all_none": "अभी किसी पर कुछ बाकी नहीं है।",
        "all": "कुल {n} लोगों पर {total} बाकी है। सबसे ज़्यादा {name} जी पर, {bal}।",
        "undo": "पिछली एंट्री हटा दी: {name} जी, {amt} {kind}।", "undo_none": "हटाने के लिए कोई एंट्री नहीं है।",
        "k_credit": "उधार", "k_payment": "जमा",
        "multi": "हो गया! {n} एंट्री लिख दीं।", "m_line": "{name} जी: {list}।",
        "undo_many": "पिछली बार की {n} एंट्री एक साथ हटा दीं।",
        "need_amount": "रकम समझ नहीं आई। रकम के साथ दोबारा बोलिए।",
        "need_customer": "किसके खाते में लिखूँ? नाम के साथ दोबारा बोलिए।",
        "not_understood": "माफ़ कीजिए, समझ नहीं आया। ऐसे बोलिए: रमेश, {ex} उधार।",
        "reminder": "नमस्ते {name} जी, {shop} की तरफ़ से याद दिला रहे हैं कि आपके खाते में {bal} बाकी हैं। जब सुविधा हो, चुका दीजिए। धन्यवाद!",
    },
    "en": {
        "new": "I've opened a new account for {name}.",
        "credit": "Done! Wrote {amt} udhaar for {name}.",
        "payment": "Great, {name} paid {amt}.",
        "bal_due": "They now owe {bal} in total.", "bal_adv": "{name} has {bal} paid in advance.", "bal_zero": "The account is fully settled now.",
        "q_due": "{name} owes {bal} in total.", "q_zero": "{name}'s account is settled. Nothing is due.",
        "q_none": "There is no account named {name} yet.",
        "today_none": "No entries yet today.", "today_credit": "Today you gave udhaar {n} times, {amt} in total.",
        "today_paid": "You received {amt}.",
        "all_none": "Nobody owes anything right now.",
        "all": "{n} customers owe {total} in total. The highest is {name}, with {bal}.",
        "undo": "Removed the last entry: {name}, {amt} {kind}.", "undo_none": "There is no entry to remove.",
        "k_credit": "udhaar", "k_payment": "payment",
        "multi": "Done! Wrote {n} entries.", "m_line": "{name}: {list}.",
        "undo_many": "Removed the last {n} entries together.",
        "need_amount": "I didn't catch the amount. Please say it again with the amount.",
        "need_customer": "Whose account should I write this in? Please say it again with the name.",
        "not_understood": "Sorry, I didn't understand. Try: Ramesh, {ex} udhaar.",
        "reminder": "Namaste {name}. This is a gentle reminder from {shop}. {bal} is pending in your account. Please pay whenever convenient. Thank you!",
    },
    "mr": {
        "new": "{name} यांचे नवीन खाते उघडले.",
        "credit": "{name} यांच्या खात्यात {amt} उधार लिहिले.",
        "payment": "{name} यांच्याकडून {amt} जमा झाले.",
        "bal_due": "एकूण बाकी {bal}.", "bal_adv": "{name} यांचे {bal} आगाऊ जमा आहेत.", "bal_zero": "हिशोब पूर्ण झाला.",
        "q_due": "{name} यांच्याकडे एकूण {bal} बाकी आहे.", "q_zero": "{name} यांचा हिशोब पूर्ण आहे, काही बाकी नाही.",
        "q_none": "{name} नावाचे कोणतेही खाते अजून नाही.",
        "today_none": "आज अजून एकही नोंद झाली नाही.", "today_credit": "आज {n} वेळा उधार दिले, एकूण {amt}.",
        "today_paid": "आणि {amt} जमा झाले.",
        "all_none": "सध्या कोणाकडेही काही बाकी नाही.",
        "all": "एकूण {n} जणांकडे {total} बाकी आहे. सर्वात जास्त {name} यांच्याकडे, {bal}.",
        "undo": "मागील नोंद काढली: {name}, {amt} {kind}.", "undo_none": "काढण्यासाठी कोणतीही नोंद नाही.",
        "k_credit": "उधार", "k_payment": "जमा",
        "multi": "{n} नोंदी लिहिल्या.", "m_line": "{name}: {list}.",
        "undo_many": "मागील {n} नोंदी एकत्र काढल्या.",
        "need_amount": "रक्कम समजली नाही. रकमेसह पुन्हा सांगा.",
        "need_customer": "कोणाच्या खात्यात लिहू? नावासह पुन्हा सांगा.",
        "not_understood": "माफ करा, समजले नाही. असे बोला: रमेश, {ex} उधार.",
        "reminder": "नमस्कार {name}, {shop} कडून आठवण: तुमच्या खात्यात {bal} बाकी आहेत. सोयीनुसार भरा. धन्यवाद!",
    },
    "gu": {
        "new": "{name}નું નવું ખાતું ખોલ્યું.",
        "credit": "{name}ના ખાતામાં {amt} ઉધાર લખ્યા.",
        "payment": "{name} પાસેથી {amt} જમા થયા.",
        "bal_due": "કુલ બાકી {bal}.", "bal_adv": "{name}ના {bal} એડવાન્સ જમા છે.", "bal_zero": "હિસાબ સરભર થઈ ગયો.",
        "q_due": "{name} પાસે કુલ {bal} બાકી છે.", "q_zero": "{name}નો હિસાબ સરભર છે, કંઈ બાકી નથી.",
        "q_none": "{name} નામનું કોઈ ખાતું હજુ નથી.",
        "today_none": "આજે હજુ કોઈ એન્ટ્રી નથી થઈ.", "today_credit": "આજે {n} વખત ઉધાર આપ્યું, કુલ {amt}.",
        "today_paid": "અને {amt} જમા થયા.",
        "all_none": "હાલમાં કોઈ પાસે કંઈ બાકી નથી.",
        "all": "કુલ {n} લોકો પાસે {total} બાકી છે. સૌથી વધુ {name} પાસે, {bal}.",
        "undo": "છેલ્લી એન્ટ્રી કાઢી નાખી: {name}, {amt} {kind}.", "undo_none": "કાઢવા માટે કોઈ એન્ટ્રી નથી.",
        "k_credit": "ઉધાર", "k_payment": "જમા",
        "multi": "{n} એન્ટ્રી લખી.", "m_line": "{name}: {list}.",
        "undo_many": "છેલ્લી {n} એન્ટ્રી એકસાથે કાઢી નાખી.",
        "need_amount": "રકમ સમજાઈ નહીં. રકમ સાથે ફરી બોલો.",
        "need_customer": "કોના ખાતામાં લખું? નામ સાથે ફરી બોલો.",
        "not_understood": "માફ કરશો, સમજાયું નહીં. આમ બોલો: રમેશ, {ex} ઉધાર.",
        "reminder": "નમસ્તે {name}, {shop} તરફથી યાદ અપાવીએ છીએ કે તમારા ખાતામાં {bal} બાકી છે. અનુકૂળતાએ ચૂકવી દેજો. આભાર!",
    },
    "bn": {
        "new": "{name}-এর নতুন খাতা খোলা হলো।",
        "credit": "{name}-এর খাতায় {amt} ধার লেখা হলো।",
        "payment": "{name} {amt} জমা দিলেন।",
        "bal_due": "মোট বাকি {bal}।", "bal_adv": "{name}-এর {bal} অগ্রিম জমা আছে।", "bal_zero": "হিসাব মিটে গেছে।",
        "q_due": "{name}-এর মোট {bal} বাকি আছে।", "q_zero": "{name}-এর হিসাব মেটানো, কিছু বাকি নেই।",
        "q_none": "{name} নামে এখনও কোনো খাতা নেই।",
        "today_none": "আজ এখনও কোনো এন্ট্রি হয়নি।", "today_credit": "আজ {n} বার ধার দেওয়া হয়েছে, মোট {amt}।",
        "today_paid": "আর {amt} জমা হয়েছে।",
        "all_none": "এখন কারও কিছু বাকি নেই।",
        "all": "মোট {n} জনের কাছে {total} বাকি। সবচেয়ে বেশি {name}-এর, {bal}।",
        "undo": "শেষ এন্ট্রি মুছে দেওয়া হলো: {name}, {amt} {kind}।", "undo_none": "মোছার মতো কোনো এন্ট্রি নেই।",
        "k_credit": "ধার", "k_payment": "জমা",
        "multi": "{n}টি এন্ট্রি লেখা হলো।", "m_line": "{name}: {list}।",
        "undo_many": "শেষ {n}টি এন্ট্রি একসাথে মুছে দেওয়া হলো।",
        "need_amount": "টাকার পরিমাণ বোঝা গেল না। পরিমাণসহ আবার বলুন।",
        "need_customer": "কার খাতায় লিখব? নামসহ আবার বলুন।",
        "not_understood": "দুঃখিত, বুঝতে পারিনি। এভাবে বলুন: রমেশ, {ex} ধার।",
        "reminder": "নমস্কার {name}, {shop} থেকে মনে করিয়ে দিচ্ছি, আপনার খাতায় {bal} বাকি আছে। সুবিধামতো শোধ করে দেবেন। ধন্যবাদ!",
    },
    "ta": {
        "new": "{name} அவர்களுக்கு புதிய கணக்கு தொடங்கப்பட்டது.",
        "credit": "{name} கணக்கில் {amt} கடன் எழுதப்பட்டது.",
        "payment": "{name} அவர்களிடமிருந்து {amt} வரவு வந்தது.",
        "bal_due": "மொத்த பாக்கி {bal}.", "bal_adv": "{name} அவர்களின் {bal} முன்பணமாக உள்ளது.", "bal_zero": "கணக்கு சரியாகிவிட்டது.",
        "q_due": "{name} அவர்களுக்கு மொத்தம் {bal} பாக்கி உள்ளது.",
        "q_zero": "{name} அவர்களின் கணக்கு சரியாக உள்ளது, பாக்கி எதுவும் இல்லை.",
        "q_none": "{name} என்ற பெயரில் இன்னும் கணக்கு இல்லை.",
        "today_none": "இன்று இன்னும் எந்தப் பதிவும் இல்லை.", "today_credit": "இன்று {n} முறை கடன் கொடுக்கப்பட்டது, மொத்தம் {amt}.",
        "today_paid": "மேலும் {amt} வரவு வந்தது.",
        "all_none": "இப்போது யாருக்கும் பாக்கி இல்லை.",
        "all": "மொத்தம் {n} பேருக்கு {total} பாக்கி உள்ளது. அதிகபட்சம் {name} அவர்களுக்கு, {bal}.",
        "undo": "கடைசி பதிவு நீக்கப்பட்டது: {name}, {amt} {kind}.", "undo_none": "நீக்க எந்தப் பதிவும் இல்லை.",
        "k_credit": "கடன்", "k_payment": "வரவு",
        "multi": "{n} பதிவுகள் எழுதப்பட்டன.", "m_line": "{name}: {list}.",
        "undo_many": "கடைசி {n} பதிவுகள் ஒன்றாக நீக்கப்பட்டன.",
        "need_amount": "தொகை புரியவில்லை. தொகையுடன் மீண்டும் சொல்லுங்கள்.",
        "need_customer": "யாருடைய கணக்கில் எழுத வேண்டும்? பெயருடன் மீண்டும் சொல்லுங்கள்.",
        "not_understood": "மன்னிக்கவும், புரியவில்லை. இப்படிச் சொல்லுங்கள்: ரமேஷ், {ex} கடன்.",
        "reminder": "வணக்கம் {name}, {shop} சார்பாக நினைவூட்டுகிறோம்: உங்கள் கணக்கில் {bal} பாக்கி உள்ளது. வசதிப்படி செலுத்துங்கள். நன்றி!",
    },
    "te": {
        "new": "{name} గారికి కొత్త ఖాతా తెరిచాం.",
        "credit": "{name} గారి ఖాతాలో {amt} అప్పు రాశాం.",
        "payment": "{name} గారి నుంచి {amt} జమ అయ్యాయి.",
        "bal_due": "మొత్తం బాకీ {bal}.", "bal_adv": "{name} గారి {bal} అడ్వాన్స్ జమ ఉంది.", "bal_zero": "లెక్క సరిపోయింది.",
        "q_due": "{name} గారికి మొత్తం {bal} బాకీ ఉంది.", "q_zero": "{name} గారి లెక్క సరిపోయింది, బాకీ ఏమీ లేదు.",
        "q_none": "{name} పేరుతో ఇంకా ఖాతా లేదు.",
        "today_none": "ఈరోజు ఇంకా ఏ ఎంట్రీ లేదు.", "today_credit": "ఈరోజు {n} సార్లు అప్పు ఇచ్చాం, మొత్తం {amt}.",
        "today_paid": "ఇంకా {amt} జమ అయ్యాయి.",
        "all_none": "ప్రస్తుతం ఎవరికీ బాకీ లేదు.",
        "all": "మొత్తం {n} మందికి {total} బాకీ ఉంది. అత్యధికం {name} గారికి, {bal}.",
        "undo": "చివరి ఎంట్రీ తీసేశాం: {name}, {amt} {kind}.", "undo_none": "తీసేయడానికి ఏ ఎంట్రీ లేదు.",
        "k_credit": "అప్పు", "k_payment": "జమ",
        "multi": "{n} ఎంట్రీలు రాశాం.", "m_line": "{name} గారు: {list}.",
        "undo_many": "చివరి {n} ఎంట్రీలు కలిపి తీసేశాం.",
        "need_amount": "మొత్తం అర్థం కాలేదు. మొత్తంతో మళ్ళీ చెప్పండి.",
        "need_customer": "ఎవరి ఖాతాలో రాయాలి? పేరుతో మళ్ళీ చెప్పండి.",
        "not_understood": "క్షమించండి, అర్థం కాలేదు. ఇలా చెప్పండి: రమేష్, {ex} అప్పు.",
        "reminder": "నమస్తే {name} గారు, {shop} నుంచి గుర్తు చేస్తున్నాం: మీ ఖాతాలో {bal} బాకీ ఉంది. వీలైనప్పుడు చెల్లించండి. ధన్యవాదాలు!",
    },
    "kn": {
        "new": "{name} ಅವರ ಹೊಸ ಖಾತೆ ತೆರೆಯಲಾಗಿದೆ.",
        "credit": "{name} ಅವರ ಖಾತೆಗೆ {amt} ಸಾಲ ಬರೆಯಲಾಗಿದೆ.",
        "payment": "{name} ಅವರಿಂದ {amt} ಜಮಾ ಆಗಿದೆ.",
        "bal_due": "ಒಟ್ಟು ಬಾಕಿ {bal}.", "bal_adv": "{name} ಅವರ {bal} ಮುಂಗಡ ಜಮಾ ಇದೆ.", "bal_zero": "ಲೆಕ್ಕ ಚುಕ್ತಾ ಆಯಿತು.",
        "q_due": "{name} ಅವರಿಂದ ಒಟ್ಟು {bal} ಬಾಕಿ ಇದೆ.", "q_zero": "{name} ಅವರ ಲೆಕ್ಕ ಚುಕ್ತಾ ಆಗಿದೆ, ಏನೂ ಬಾಕಿ ಇಲ್ಲ.",
        "q_none": "{name} ಹೆಸರಿನಲ್ಲಿ ಇನ್ನೂ ಯಾವುದೇ ಖಾತೆ ಇಲ್ಲ.",
        "today_none": "ಇಂದು ಇನ್ನೂ ಯಾವುದೇ ನಮೂದು ಆಗಿಲ್ಲ.", "today_credit": "ಇಂದು {n} ಬಾರಿ ಸಾಲ ಕೊಡಲಾಗಿದೆ, ಒಟ್ಟು {amt}.",
        "today_paid": "ಮತ್ತು {amt} ಜಮಾ ಆಗಿದೆ.",
        "all_none": "ಸದ್ಯ ಯಾರಿಂದಲೂ ಬಾಕಿ ಇಲ್ಲ.",
        "all": "ಒಟ್ಟು {n} ಜನರಿಂದ {total} ಬಾಕಿ ಇದೆ. ಅತಿ ಹೆಚ್ಚು {name} ಅವರಿಂದ, {bal}.",
        "undo": "ಕೊನೆಯ ನಮೂದು ತೆಗೆಯಲಾಗಿದೆ: {name}, {amt} {kind}.", "undo_none": "ತೆಗೆಯಲು ಯಾವುದೇ ನಮೂದು ಇಲ್ಲ.",
        "k_credit": "ಸಾಲ", "k_payment": "ಜಮಾ",
        "multi": "{n} ನಮೂದುಗಳನ್ನು ಬರೆಯಲಾಗಿದೆ.", "m_line": "{name}: {list}.",
        "undo_many": "ಕೊನೆಯ {n} ನಮೂದುಗಳನ್ನು ಒಟ್ಟಿಗೆ ತೆಗೆಯಲಾಗಿದೆ.",
        "need_amount": "ಮೊತ್ತ ಅರ್ಥವಾಗಲಿಲ್ಲ. ಮೊತ್ತದೊಂದಿಗೆ ಮತ್ತೆ ಹೇಳಿ.",
        "need_customer": "ಯಾರ ಖಾತೆಗೆ ಬರೆಯಲಿ? ಹೆಸರಿನೊಂದಿಗೆ ಮತ್ತೆ ಹೇಳಿ.",
        "not_understood": "ಕ್ಷಮಿಸಿ, ಅರ್ಥವಾಗಲಿಲ್ಲ. ಹೀಗೆ ಹೇಳಿ: ರಮೇಶ್, {ex} ಸಾಲ.",
        "reminder": "ನಮಸ್ಕಾರ {name}, {shop} ಕಡೆಯಿಂದ ನೆನಪಿಸುತ್ತಿದ್ದೇವೆ: ನಿಮ್ಮ ಖಾತೆಯಲ್ಲಿ {bal} ಬಾಕಿ ಇದೆ. ಅನುಕೂಲವಾದಾಗ ಪಾವತಿಸಿ. ಧನ್ಯವಾದಗಳು!",
    },
}


def lang_of(value: str | None) -> str:
    return value if value in LANGS else "hi"


from .phrases import MORE as _MORE  # noqa: E402  (talk-back, promises, limits, UPI)
from .phrases import VARIANTS as _VARIANTS  # noqa: E402  (other ways to say the same thing)

for _lang, _extra in _MORE.items():
    T[_lang].update(_extra)


def _money(lang: str, n: float, spoken: bool) -> str:
    if not spoken:
        return inr(n)
    n = abs(int(round(n)))
    if lang == "hi":
        return f"{hindi_words(n)} {'रुपया' if n == 1 else 'रुपये'}"
    if lang == "en":
        return f"{english_words(n)} rupee{'s' if n != 1 else ''}"
    return f"{n} {CURRENCY[lang]}"


_last_pick: dict[tuple[str, str], str] = {}


def _template(lang: str, key: str) -> str:
    """One way of saying it, picked at random, and never the same one twice in a row,
    so the shopkeeper hears a person, not a recording."""
    options = [T[lang][key], *_VARIANTS.get(lang, {}).get(key, [])]
    if len(options) > 1 and _last_pick.get((lang, key)) in options:
        options.remove(_last_pick[(lang, key)])
    choice = random.choice(options)
    _last_pick[(lang, key)] = choice
    return choice


def _say(lang: str, parts: list[tuple[str, dict]]) -> dict:
    """parts = [(template_key, values)]; money values are numbers and get formatted twice."""
    templates = [_template(lang, key) for key, _ in parts]  # same wording for the text and the voice

    def build(spoken: bool) -> str:
        out = []
        for tpl, (_, values) in zip(templates, parts):
            v = {k: (_money(lang, x, spoken) if k in ("amt", "bal", "total", "ex", "limit")
                     else name_for(x, lang) if k == "name" else x) for k, x in values.items()}
            out.append(tpl.format(**v))
        return " ".join(out)

    return {"text": build(False), "speech": build(True), "lang": lang}


def entry_saved(kind: str, name: str, amount: float, bal: float, new: bool, lang: str) -> dict:
    parts = [("new", {"name": name})] if new else []
    parts.append((kind, {"name": name, "amt": amount}))
    if bal > 0.5:
        parts.append(("bal_due", {"bal": bal}))
    elif bal < -0.5:
        parts.append(("bal_adv", {"name": name, "bal": -bal}))
    else:
        parts.append(("bal_zero", {}))
    return _say(lang, parts)


def balance_reply(name: str, bal: float | None, lang: str) -> dict:
    if bal is None:
        return _say(lang, [("q_none", {"name": name})])
    if bal > 0.5:
        return _say(lang, [("q_due", {"name": name, "bal": bal})])
    if bal < -0.5:
        return _say(lang, [("bal_adv", {"name": name, "bal": -bal})])
    return _say(lang, [("q_zero", {"name": name})])


def today_reply(s: dict, lang: str) -> dict:
    n, given, got = s["credit_count_today"], s["credit_today"], s["payment_today"]
    if not n and not got:
        return _say(lang, [("today_none", {})])
    parts = []
    if n:
        parts.append(("today_credit", {"n": n, "amt": given}))
    if got:
        parts.append(("today_paid", {"amt": got}))
    return _say(lang, parts)


def all_reply(s: dict, lang: str) -> dict:
    top = s["top"]
    if not top:
        return _say(lang, [("all_none", {})])
    return _say(lang, [("all", {"n": s["owing_count"], "total": s["total_due"], "name": top["name"], "bal": top["balance"]})])


def _groups(entries: list[dict]) -> list[dict]:
    """Entries -> one group per customer, in the order they were said."""
    groups: dict = {}
    for e in entries:
        g = groups.setdefault(e["customer"], {"name": e["customer"], "new": False, "items": []})
        g["new"] = g["new"] or bool(e.get("new_customer"))
        g["items"].append((e["kind"], e["amount"]))
    return list(groups.values())


def _lines(lang: str, groups: list[dict], balances: dict | None) -> dict:
    """ "मनीष जी: ₹2,000 उधार, ₹1,000 जमा। मनीष जी पर कुल ₹1,000 बाकी है।" (text and speech) """
    t = T[lang]

    def build(spoken: bool) -> list[str]:
        out = []
        for g in groups:
            name = name_for(g["name"], lang)
            if balances is not None and g["new"]:
                out.append(t["new"].format(name=name))
            items = ", ".join(f"{_money(lang, amt, spoken)} {t['k_' + kind]}" for kind, amt in g["items"])
            out.append(t["m_line"].format(name=name, list=items))
            if balances is None:
                continue
            bal = balances.get(g["name"], 0.0)
            if bal > 0.5:
                out.append(t["q_due"].format(name=name, bal=_money(lang, bal, spoken)))
            elif bal < -0.5:
                out.append(t["bal_adv"].format(name=name, bal=_money(lang, -bal, spoken)))
            else:
                out.append(t["q_zero"].format(name=name))
        return out

    return {"text": build(False), "speech": build(True)}


def entries_saved(entries: list[dict], balances: dict, lang: str) -> dict:
    """Reply for several entries said in one sentence. balances = {customer name: balance after}."""
    lines = _lines(lang, _groups(entries), balances)
    head = T[lang]["multi"].format(n=len(entries))
    return {"text": " ".join([head, *lines["text"]]), "speech": " ".join([head, *lines["speech"]]), "lang": lang}


def undo_reply(entry: dict | None, lang: str) -> dict:
    if not entry:
        return _say(lang, [("undo_none", {})])
    if entry.get("kind") == "promise":
        return _say(lang, [("undo_promise", {"name": entry["customer"]})])
    group = entry.get("batch_entries") or [entry]
    if len(group) > 1:
        lines = _lines(lang, _groups(group), None)
        head = T[lang]["undo_many"].format(n=len(group))
        return {"text": " ".join([head, *lines["text"]]), "speech": " ".join([head, *lines["speech"]]), "lang": lang}
    kind = T[lang]["k_credit" if entry["kind"] == "credit" else "k_payment"]
    return _say(lang, [("undo", {"name": entry["customer"], "amt": entry["amount"], "kind": kind})])


def need_amount(name: str | None, lang: str) -> dict:
    return _say(lang, [("need_amount", {})])


def need_customer(lang: str) -> dict:
    return _say(lang, [("need_customer", {})])


def not_understood(lang: str) -> dict:
    return _say(lang, [("not_understood", {"ex": 300})])


def reminder(name: str, bal: float, shop: str, lang: str, upi: str | None = None) -> dict:
    out = _say(lang, [("reminder", {"name": name, "bal": bal, "shop": shop})])
    if upi:  # written in the WhatsApp message, not read out in the voice note
        out["text"] += "\n" + T[lang]["reminder_upi"].format(upi=upi)
    return out


# ---------------------------------------------------------------- talk-back, promises, limits
def day_words(iso: str, lang: str) -> str:
    """ "2026-11-13" -> "शुक्रवार, 13 नवंबर को" / "कल" / "आज"."""
    t = T[lang]
    d = date.fromisoformat(iso)
    diff = (d - date.today()).days
    if diff == 0:
        return t["w_today"]
    if diff == 1:
        return t["w_tomorrow"]
    return t["date_fmt"].format(wd=t["days"][d.weekday()], d=d.day, m=t["months"][d.month - 1])


def simple(key: str, lang: str) -> dict:
    """cancelled / bye / corrected / due_none / ask_customer / ask_amount"""
    return _say(lang, [(key, {})])


def ask(need: str, pending: dict, lang: str) -> dict:
    """The question the app asks back when something is missing."""
    name = pending.get("customer")
    if need == "customer":
        return _say(lang, [("ask_customer", {})])
    if need == "date":
        return _say(lang, [("ask_date", {"name": name})])
    if name and pending.get("intent") in ("credit", "payment"):
        return _say(lang, [("ask_amount_" + pending["intent"], {"name": name})])
    return _say(lang, [("ask_amount", {})])


def promise_saved(name: str, amount: float | None, due: str, lang: str) -> dict:
    when = day_words(due, lang)
    if amount:
        return _say(lang, [("promise", {"name": name, "amt": amount, "date": when})])
    return _say(lang, [("promise_all", {"name": name, "date": when})])


def limit_reply(name: str, amount: float | None, lang: str) -> dict:
    if amount:
        return _say(lang, [("limit_set", {"name": name, "amt": amount})])
    return _say(lang, [("limit_removed", {"name": name})])


def limit_over(name: str, limit: float, bal: float, lang: str) -> dict:
    return _say(lang, [("limit_over", {"name": name, "limit": limit, "bal": bal})])


def promise_kept(name: str, lang: str) -> dict:
    return _say(lang, [("promise_kept", {"name": name})])


def due_reply(due: dict, lang: str) -> dict:
    people = due["overdue"] + due["today"]
    if not people:
        return _say(lang, [("due_none", {})])
    t = T[lang]

    def build(spoken: bool) -> str:
        items = ", ".join(t["due_item"].format(name=name_for(p["name"], lang), amt=_money(lang, p["left"], spoken))
                          for p in people[:6])
        return t["due_list"].format(n=len(people), list=items)

    return {"text": build(False), "speech": build(True), "lang": lang}


def join(*replies: dict) -> dict:
    """Several replies, said one after another."""
    parts = [r for r in replies if r]
    return {"text": " ".join(r["text"] for r in parts), "speech": " ".join(r["speech"] for r in parts),
            "lang": parts[0]["lang"] if parts else "hi"}


def summary_reply(s: dict, lang: str) -> dict:
    """Today's summary followed by everyone's dues, as one reply."""
    a, b = today_reply(s, lang), all_reply(s, lang)
    return {"text": f"{a['text']} {b['text']}", "speech": f"{a['speech']} {b['speech']}", "lang": lang}
