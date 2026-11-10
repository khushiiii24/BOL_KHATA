"""Understand what the shopkeeper said.

Input : a sentence like "रमेश भैया दो किलो आटा 340 रुपये उधार" or "Sharma ji ne 500 jama kiye"
Output: {"intent": "credit", "customer": "रमेश", "amount": 340, "items": "दो किलो आटा"}

Intents
  credit   - shop gave goods on udhaar        ("उधार", "likh do", "khate mein")
  payment  - customer paid money back         ("जमा", "diye", "lautaye", "paid")
  balance  - how much does one customer owe   ("रमेश का कितना बाकी है?")
  today    - today's summary                  ("आज का हिसाब")
  all      - everyone's dues / who owes most  ("सबका हिसाब", "sabse zyada kiska")
  undo     - remove the last entry            ("गलत हो गया", "undo")
  multi    - several entries in one sentence  ("मनीष ने 2000 का सामान लिया और 1000 जमा किए")
             -> {"intent": "multi", "actions": [{credit 2000}, {payment 1000}]}
  unknown  - could not understand

Two ways to understand:
  1. Smart mode: an LLM (optional, free Groq or Gemini key in .env).
  2. Basic mode: the rules below. No key needed, works for common Hindi/Hinglish sentences.
If the LLM fails for any reason, basic mode is used automatically.
"""

from __future__ import annotations

import json
import calendar
import re
from datetime import date, timedelta
import unicodedata
from dataclasses import dataclass

import requests

from .config import settings
from .numbers import word_number_kind
from .translit import to_devanagari as _to_devanagari


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _set(words: str) -> set[str]:
    return {nfc(w) for w in words.split()}


# --- word lists (Devanagari + Hinglish + English) ---------------------------
CREDIT_WORDS = _set("""
उधार उधारी लिख लिखो लिखना लिखिए लिखदो खाते खाता
udhaar udhar udhari udhaari likh likho likhdo likhna likhiye khate khaate khata
credit owe owes
""")
PAYMENT_WORDS = _set("""
जमा दिए दिये दिया लौटाए लौटाया लौटा वापस चुकाए चुकाया चुका भरे भरा मिले मिला देकर देके
jama diye diya lautaye lautaya lauta wapas vapas chukaye chukaya chuka bhare mile mila dekar deke
paid pay payment received returned upi gpay phonepe paytm online cash gave given
""")
# Clearly "money came back". These win even if "उधार" is also said:
# "उधार के 300 जमा किए" = paid back.
STRONG_PAYMENT_WORDS = _set("""
जमा लौटाए लौटाया लौटा वापस चुकाए चुकाया चुका मिले मिला
jama lautaye lautaya lauta wapas vapas chukaye chukaya chuka mile mila
paid payment received returned upi gpay phonepe paytm
""")
# "दे गए" / "de gaye" = (the customer) gave and left = paid
_GIVE = _set("दे de देकर देके dekar deke")
_WENT = _set("गए गई गया गये गयी gaye gayi gaya gae gai gye gyi gya")
_KE = _set("के कर ke kar")   # "दे के गए", "ले कर गए"
UNDO_WORDS = _set("""
गलत ग़लत हटाओ हटा हटादो मिटाओ मिटा कैंसल
galat hatao hata hatado mitao mita undo cancel delete remove wrong
""")
QUESTION_WORDS = _set("""
कितना कितने कितनी क्या बताओ बताइए बताना दिखाओ किसका किसकी किसके कौन
kitna kitne kitni kya batao bataiye batana dikhao kiska kiski kiske kaun
how much what show tell balance
""")
TODAY_WORDS = _set("आज aaj aj today")
ALL_WORDS = _set("""
सब सबका सबकी सबके सभी कुल सबसे टोटल
sab sabka sabki sabke sabhi kul sabse total everyone everybody all
""")
CURRENCY_WORDS = _set("""
₹ रुपये रुपए रुपया रूपये रूपए रुपयों रु रू
rupaye rupay rupaiye rupee rupees rupiya rupya rs inr
""")
UNIT_WORDS = _set("""
किलो केजी ग्राम लीटर पैकेट पैकेट्स दर्जन पीस बोतल डिब्बा डिब्बे बोरी कप प्लेट
kilo kg kgs gram grams gm litre liter litres ltr packet packets pkt dozen darjan
piece pieces pcs bottle bottles dibba dibbe bori cup plate
""")
ITEM_WORDS = _set("""
आटा चावल दाल तेल चीनी शक्कर नमक दूध दही ब्रेड अंडे अंडा मैगी साबुन चाय चायपत्ती बिस्कुट
घी मसाला हल्दी मिर्च सब्ज़ी सब्जी राशन सामान सर्फ़ शैम्पू पानी कोल्ड ड्रिंक
aata atta chawal rice daal dal tel oil cheeni chini sugar namak salt doodh milk dahi bread
ande anda eggs maggi sabun soap chai tea biscuit ghee masala sabzi sabji ration saamaan saman
surf shampoo water goods items stuff grocery groceries
""")
# Words that come right after a name: "Sharma JI ne", "Ramesh KO", "Sunita KA"
NAME_MARKERS = _set("""
जी भैया भइया भाई दीदी आंटी अंकल साहब चाचा चाची मौसी ने को का की के से
ji bhaiya bhaiyya bhai didi aunty auntie uncle sahab saab chacha chachi mausi
ne ko ka ki ke se
""")
# --- other Indian languages: basic support -----------------------------------
# Marathi, Gujarati, Bengali, Tamil, Telugu, Kannada. Smart mode (LLM) understands
# these much better; these words make the common sentences work without it.
_R_CREDIT = _set("""
लिहा लिहून खात्यात
ઉધાર ઉધારી લખો ખાતામાં
ধার ধারে লেখো লিখে খাতায়
கடன் கடனாக எழுது கணக்கில்
అప్పు అరువు రాయి రాయండి ఖాతాలో
ಸಾಲ ಉದ್ರಿ ಬರೆ ಬರೆಯಿರಿ ಖಾತೆಗೆ
""")
_R_STRONG_PAY = _set("""
परत भरले चुकते
જમા ચૂકવ્યા ચૂકવ્યું પાછા ભર્યા
জমা ফেরত শোধ পরিশোধ
வரவு செலுத்தினார் செலுத்தினாங்க திருப்பி கட்டினார்
జమ చెల్లించారు కట్టారు తిరిగి
ಜಮಾ ಪಾವತಿ ಕಟ್ಟಿದರು ವಾಪಸ್
""")
_R_WEAK_PAY = _set("""
दिले दिला दिली
આપ્યા આપ્યું આપી
দিলেন দিয়েছেন দিয়েছে দিল
கொடுத்தார் கொடுத்தாங்க கொடுத்தான் கொடுத்தாள்
ఇచ్చారు ఇచ్చాడు ఇచ్చింది
ಕೊಟ್ಟರು ಕೊಟ್ಟ ಕೊಟ್ಟಳು
""")
_R_UNDO = _set("""
चूक काढून काढा रद्द
ભૂલ કાઢી રદ
ভুল মুছে মুছো বাতিল
தவறு நீக்கு ரத்து
తప్పు తీసేయి తీసివేయి రద్దు
ತಪ್ಪು ತಪ್ಪಾಯಿತು ತೆಗೆದುಹಾಕು ತೆಗೆ ರದ್ದು
""")
_R_QUESTION = _set("""
किती काय सांगा
કેટલા કેટલું કેટલી કહો
কত কতো বলো বলুন
எவ்வளவு எத்தனை சொல்லு சொல்லுங்கள்
ఎంత చెప్పు చెప్పండి
ಎಷ್ಟು ಹೇಳು ಹೇಳಿ
""")
_R_TODAY = _set("""
आजचा आजचे आजची
આજે આજનો આજનું આજ
আজ আজকের
இன்று இன்றைய
ఈరోజు నేడు
ಇಂದು ಇಂದಿನ
""")
_R_ALL = _set("""
सगळ्यांचा सर्व सर्वांचा एकूण सर्वात
બધાનો બધા કુલ સૌથી
সবার সব মোট সবচেয়ে
எல்லாரும் எல்லோருடைய மொத்த மொத்தம் அதிகம்
అందరి అందరూ మొత్తం అత్యధికం
ಎಲ್ಲರ ಎಲ್ಲಾ ಒಟ್ಟು ಅತಿ
""")
_R_CURRENCY = _set("રૂપિયા રૂ টাকা টাকার ரூபாய் ரூ రూపాయలు రూపాయి రూ ರೂಪಾಯಿ ರೂ")
_R_MARKERS = _set("""
यांनी यांचे यांच्या यांच्याकडे यांच्याकडून भाऊ ताई साहेब काका मावशी ला कडून
ભાઈ બેન કાકા
দা দাদা দি দিদি বাবু
அண்ணா அக்கா சார் அவர்கள் கிட்ட
గారు అన్న అక్క
ಅವರು ಅಣ್ಣ ಅಕ್ಕ ಸಾರ್ ಅವರಿಂದ
""")
_R_STOP = _set("""
आहे आहेत होते केले केला केली झाले झाला हिशोब सांगा द्या टाका आणि
છે હતા કર્યા કર્યું થયા થઈ હિસાબ બાકી નાખો અને
হয়েছে আছে বাকি হিসাব দাও দিন এবং আর
பாக்கி கணக்கு உள்ளது செய்தார் மற்றும்
బాకీ లెక్క చేశారు ఉంది అయింది మరియు రోజు
ಬಾಕಿ ಲೆಕ್ಕ ಮಾಡಿದರು ಇದೆ ಮತ್ತು
""")
CREDIT_WORDS |= _R_CREDIT
STRONG_PAYMENT_WORDS |= _R_STRONG_PAY
PAYMENT_WORDS |= _R_STRONG_PAY | _R_WEAK_PAY
UNDO_WORDS |= _R_UNDO
QUESTION_WORDS |= _R_QUESTION
TODAY_WORDS |= _R_TODAY
ALL_WORDS |= _R_ALL
CURRENCY_WORDS |= _R_CURRENCY
NAME_MARKERS |= _R_MARKERS

# --- words for sentences that say two things at once -------------------------
# "मनीष जी ने 2000 का सामान लिया और वो 1000 जमा करके गए" = udhaar 2000 + jama 1000.
# "took goods" = udhaar. With "से" and no goods ("रमेश से 500 लिए") it means we took money = jama.
TAKE_WORDS = _set("""
लिया लिए लिये ली खरीदा खरीदे खरीदी ख़रीदा ख़रीदे उठाया उठाए लेकर लेके
liya liye liyaa lia kharida kharide khareeda kharidi uthaya uthaye lekar leke
took take takes taken bought buy buys purchased borrowed
घेतले घेतला घेतली
લીધું લીધા લીધી લીધો લઈ ગયા ખરીદ્યું ખરીદ્યો
নিলেন নিয়েছেন কিনলেন কিনেছেন
வாங்கினார் வாங்கினாங்க வாங்கிட்டு
తీసుకున్నారు తీసుకెళ్లారు కొన్నారు
ತೆಗೆದುಕೊಂಡರು ಖರೀದಿಸಿದರು
""")
_TAKE = _set("ले le लेकर लेके lekar leke")   # "ले गए" / "लेकर गई" = took away = udhaar
# "and", "then", "but": a new action often starts here
CONJ_WORDS = _set("""
और औऱ aur or and फिर फ़िर phir fir then तथा एवं लेकिन lekin magar मगर but
आणि અને এবং আর மற்றும் మరియు ಮತ್ತು
""")
# "he / she / they": the same customer as before
PRONOUNS = _set("""
वो वह वे ये यह उसने उन्होंने उन्हों इसने इन्होंने उसको उनको उन्हें उसे उनसे उससे उनकी उसकी उनका उसका इन्हें इनसे
wo woh vo voh ve ye yeh usne unhone unhonne inhone isne usko unko unhe unhen unhein use unse usse unki uski
he she they him her them
त्यांनी त्याने तिने
તેમણે તેણે એણે
উনি তিনি সে তারা
அவர் அவங்க அவன் அவள்
ఆయన ఆమె వాళ్ళు అతను
ಅವನು ಅವಳು
""")
FILLER_WORDS = _set("भी अभी अब साथ बाद तो bhi baad ab abhi to now so also again too more worth")
# "अब 1000 बाकी है" / "कुल 500" only describe the account; they are not new entries
BALANCE_WORDS = _set("""
बाकी बाक़ी बकाया बचे बचा बची baaki baki bakaya bache bacha remaining left due outstanding pending
બાકી বাকি பாக்கி బాకీ ಬಾಕಿ
""")
TOTAL_WORDS = _set("कुल टोटल मिलाकर kul total milakar overall एकूण કુલ মোট மொத்தம் మొత్తం ಒಟ್ಟು")
# numbers followed by these are not rupees: "15 तारीख", "2 दिन", "3 बार"
TIME_WORDS = _set("""
तारीख तारीख़ दिन दिनों महीने महीना साल बजे बार हफ्ते हफ़्ते घंटे मिनट
tarikh tareekh tarik date din dino days day mahine mahina month months saal year years baje baar times
hafte week weeks ghante hours minute minutes
""")
# "1240 में से 500": 1240 is the old total, 500 is the amount
_IN = _set("में मे mein me main")
_NOT = _set("नहीं नही नई nahi nahin nai not no")
_WRITE = _set("लिख लिखो लिखना लिखिए लिखदो लिख_दो likh likho likhdo likhna likhiye write add")
_GAVE = _set("दिए दिये दिया diye diya paid gave")
_FROM = _set("से se")
# English verbs come BEFORE the amount ("paid 500"); Hindi verbs come after ("500 दिए")
ENGLISH_ACTIONS = _set("""
paid pay pays gave give gives returned return deposited took take takes bought buy buys
purchased borrowed credit credited owes owe cleared settled received got
""")
# "2000 का सामान" = goods worth 2000 = udhaar
_WORTH = _set("का की के ka ki ke worth")

# Endings glued to a name in some languages: "रमेशला", "સુનીતાના", "সুনীতার", "ரமேஷுக்கு"
NAME_SUFFIXES = sorted(_set("""
यांनी यांचे यांच्या कडून कडे चे चा ची ला
ના નો ની નું ને એ ે
এর ের কে
ுக்கு க்கு கிட்ட
గారికి కి కు
ಅವರಿಗೆ ಅವರ ಗೆ
"""), key=len, reverse=True)

# --- promises, limits, "due today", "bye" ----------------------------------------
# "रमेश शुक्रवार को देगा" = a promise to pay, not a payment.
FUTURE_PAY = _set("""
देगा देंगे देगी दूँगा दूंगा दूँगी दूंगी देंगी देगें लौटाएगा लौटाएंगे लौटाएगी चुकाएगा चुकाएंगे चुकाएगी भरेगा भरेंगे भरेगी
वादा वायदा वादे
dega denge degi dungi dunga doonga deunga lautayega lautayenge chukayega chukayenge bharega bharenge
vada vaada waada promise promised promises
देईल देतील देणार આપશે આપીશ આપીશું দেবে দেবেন দেব
தருவார் தருவேன் கொடுப்பார் கொடுப்பேன் தருகிறேன் கொடுக்கிறேன்
ఇస్తారు ఇస్తాను ఇస్తాడు ಕೊಡುತ್ತಾರೆ ಕೊಡುತ್ತೇನೆ ಕೊಡ್ತಾರೆ
""")
_FUTURE_DO = _set("करेगा करेंगे करेगी करूँगा करूंगा karega karenge karegi karunga")
_WILL = _set("will shall gonna")
_WILL_PAY = _set("pay give return clear settle repay")
LIMIT_WORDS = _set("लिमिट सीमा हद limit मर्यादा મર્યાદા લિમિટ লিমিট সীমা வரம்பு லிமிட் పరిమితి లిమిట్ ಮಿತಿ ಲಿಮಿಟ್")
# "आज किससे पैसा आना है?"
DUE_Q_WORDS = _set("आना आने आएगा आएंगे आनी वादे aana aane aayega aayenge due promises pays collect येणे येणार આવવાના আসার வர வேண்டும் రావాలి ಬರಬೇಕು")
BYE_WORDS = _set("""
बस धन्यवाद शुक्रिया थैंक्यू थैंक्स bas dhanyavad dhanyawad shukriya thanks thank thankyou bye stop enough
पुरे બસ આભાર ধন্যবাদ ব্যস நன்றி போதும் ధన్యవాదాలు చాలు ಧನ್ಯವಾದ ಸಾಕು
""")
CANCEL_WORDS = _set("रहने छोड़ो छोड़ छोड़िए मत नहीं नही rehne rahne chhodo chhod mat nahi nahin cancel no nope leave")
# dates
_TOMORROW = _set("कल kal tomorrow उद्या કાલે આવતીકાલે কাল আগামীকাল நாளை நாளைக்கு రేపు ನಾಳೆ")
_DAY_AFTER = _set("परसों परसो parso parson parsoon परवा પરમદિવસે পরশু ఎల్లుండి ನಾಡಿದ್ದು")
_TODAY_D = _set("आज aaj aj today આજે আজ இன்று இன்னைக்கு ఈరోజు ಇಂದು")
_WEEK = _set("हफ्ते हफ़्ते हफ्ता सप्ताह hafte hafta week आठवड्यात અઠવાડિયામાં সপ্তাহে வாரத்தில் వారంలో ವಾರದಲ್ಲಿ")
_DATE_AFTER = _set("तारीख तारीख़ tarikh tareekh tarik date th st nd rd")
_DAYS_AFTER = _set("दिन दिनों din dino days day")
_MONTH_END = _set("आखिर आख़िर अंत end akhir aakhir")
WEEKDAYS = {}
for _i, _names in enumerate([
    "सोमवार सोमवारी somvar somwar monday સોમવાર સોમવારે সোমবার திங்கள் திங்கட்கிழமை సోమవారం ಸೋಮವಾರ",
    "मंगलवार मंगळवार मंगळवारी mangalvar mangalwar tuesday મંગળવાર મંગળવારે মঙ্গলবার செவ்வாய் మంగళవారం ಮಂಗಳವಾರ",
    "बुधवार बुधवारी budhvar budhwar wednesday બુધવાર બુધવારે বুধবার புதன் బుధవారం ಬುಧವಾರ",
    "गुरुवार गुरुवारी बृहस्पतिवार वीरवार guruvar guruwar brihaspativar veervar thursday ગુરુવાર ગુરુવારે বৃহস্পতিবার வியாழன் గురువారం ಗುರುವಾರ",
    "शुक्रवार शुक्रवारी shukravar shukrawar sukravar friday શુક્રવાર શુક્રવારે শুক্রবার வெள்ளி வெள்ளிக்கிழமை శుక్రవారం ಶುಕ್ರವಾರ",
    "शनिवार शनिवारी shanivar shaniwar saturday શનિવાર શનિવારે শনিবার சனி சனிக்கிழமை శనివారం ಶನಿವಾರ",
    "रविवार रविवारी इतवार ravivar raviwar itvar itwar sunday રવિવાર રવિવારે রবিবার ஞாயிறு ఆదివారం ಭಾನುವಾರ",
]):
    for _w in _set(_names):
        WEEKDAYS[_w] = _i
TIME_WORDS |= _set("th st nd rd")
_MONEY_WORDS = _set("पैसा पैसे पैसों paisa paise paisaa money")

STOP_WORDS = _set("""
है हैं था थे थी हो हुआ हुए हुई गया गए गई में मैं और भी अब अभी कल परसों
कर करो करदो करना करके किया किए किये लो ले लिया लिए दो दे देना दीजिए
मेरा मेरे मेरी उनका उनके उसका उसके इनका एक बार वाला वाले वाली ज़्यादा ज्यादा
पर पे तक हिसाब बाकी बाक़ी एंट्री आखिरी पिछली प्लीज़ नया नाम महीने महीना हफ्ते दुकान ग्राहक
mahine mahina hafte month week dukaan dukan shop customer
hai hain tha the thi ho hua hue hui gaya gaye gayi me mein main aur bhi ab abhi kal parson
kar karo kardo karna karke kiya kiye lo le liya liye de dena dijiye
mera mere meri unka unke uska uske inka baar wala wale wali zyada jyada
par pe tak hisaab hisab baaki baki entry aakhri aakhiri pichli please plz naya naam
the a an of for to from by with via through using and is was my his her their gave give given took
सिर्फ़ सिर्फ बस केवल आपने तुमने मैंने सुन सुना सुनी सुनाई गलती दोबारा फिर से ठीक सही करके
sirf bas keval kewal only just aapne apne tumne maine sun suna suni galti dobara theek thik sahi
""") | _R_STOP | CREDIT_WORDS | PAYMENT_WORDS | UNDO_WORDS | QUESTION_WORDS | TODAY_WORDS | ALL_WORDS \
    | CURRENCY_WORDS | UNIT_WORDS | ITEM_WORDS | NAME_MARKERS | TAKE_WORDS | CONJ_WORDS | PRONOUNS \
    | FILLER_WORDS | BALANCE_WORDS | TOTAL_WORDS | TIME_WORDS | FUTURE_PAY | _FUTURE_DO | _WILL | LIMIT_WORDS \
    | DUE_Q_WORDS | BYE_WORDS | CANCEL_WORDS | _TOMORROW | _DAY_AFTER | _TODAY_D | _WEEK | _DATE_AFTER \
    | _DAYS_AFTER | _MONTH_END | set(WEEKDAYS) | _MONEY_WORDS | _NOT
ACTION_WORDS = CREDIT_WORDS | PAYMENT_WORDS | TAKE_WORDS

INTENT_LABELS = {
    "credit": "उधार", "payment": "जमा", "balance": "बाकी पूछा", "today": "आज का हिसाब",
    "all": "सबका हिसाब", "undo": "हटाओ", "unknown": "समझ नहीं आया", "multi": "कई एंट्री",
    "promise": "वादा", "set_limit": "उधार सीमा", "due_today": "आज किससे आना है", "correct": "सुधार",
    "bye": "बस",
}

# Digits of every Indian script (०-९, ০-৯, ૦-૯, ௦-௯, ౦-౯, ೦-೯ ...) -> 0-9
_INDIC_DIGITS = {base + 0x66 + d: str(d) for base in range(0x0900, 0x0D80, 0x80) for d in range(10)}
_TOKEN_RE = re.compile(r"₹|\d+(?:,\d+)*(?:\.\d+)?|[\u0900-\u0963\u0970-\u0D7F]+|[A-Za-z]+")


@dataclass
class Tok:
    text: str             # as written
    low: str              # lowercase / normalized
    num: float | None = None
    from_words: bool = False  # number came from words like "दो", not digits


def tokenize(text: str) -> list[Tok]:
    t = nfc(text).translate(_INDIC_DIGITS).replace("।", " ").replace("॥", " ")
    toks = []
    for m in _TOKEN_RE.finditer(t):
        raw = m.group(0)
        if raw[0].isdigit():
            toks.append(Tok(raw, raw, float(raw.replace(",", ""))))
        else:
            toks.append(Tok(raw, raw.lower()))
    return _merge_number_words(toks)


def _merge_number_words(toks: list[Tok]) -> list[Tok]:
    """'साढ़े तीन सौ' -> one token with num=350. '3 हज़ार' -> 3000."""
    out: list[Tok] = []
    i = 0
    while i < len(toks):
        info = _num_info(toks[i])
        if info is None:
            out.append(toks[i])
            i += 1
            continue
        total = current = mod = 0.0
        last_kind = None
        has_value = False
        all_digits = True
        texts = []
        j = i
        while j < len(toks):
            info = _num_info(toks[j])
            if info is None:
                break
            kind, val = info
            # "340 500" or "2 340" are two separate numbers, not one.
            if kind in ("num", "mod") and last_kind == "num":
                break
            if kind == "num":
                current += val + mod
                mod = 0.0
                has_value = True
            elif kind == "mod":
                mod = val
            else:  # multiplier
                if current == 0:
                    current = 1 + mod
                    mod = 0.0
                if val == 100:
                    current *= 100
                else:
                    total += current * val
                    current = 0.0
                has_value = True
            if toks[j].num is None:
                all_digits = False
            last_kind = kind
            texts.append(toks[j].text)
            j += 1
        if not has_value:
            out.append(toks[i])
            i += 1
            continue
        value = total + current
        out.append(Tok(" ".join(texts), " ".join(texts).lower(), value, from_words=not all_digits))
        i = j
    return out


def _num_info(tok: Tok):
    if tok.num is not None:
        return ("num", tok.num)
    return word_number_kind(tok.low)


# --- name matching across scripts ------------------------------------------
# "रमेश" and "Ramesh" should be the same customer. We compare a rough
# "consonant skeleton": both become "rmsh".
_DEV_MAP = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "ch", "ज": "j", "झ": "jh",
    "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
    "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "", "र": "r",
    "ल": "l", "ळ": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ं": "n", "ऋ": "r", "ृ": "r",
    "ऱ": "r", "ऴ": "l", "ऩ": "n",
}


def skeleton(name: str) -> str:
    s = unicodedata.normalize("NFD", _to_devanagari(nfc(name).lower()))
    raw = []
    for ch in s:
        if ch in _DEV_MAP:
            raw.append(_DEV_MAP[ch])
        elif "a" <= ch <= "z":
            raw.append(ch)
    s = "".join(raw)
    s = s.replace("chh", "ch").replace("ck", "k").replace("ph", "f")
    s = re.sub(r"c(?!h)", "k", s)
    s = s.replace("f", "ph").replace("w", "v").replace("z", "j").replace("q", "k").replace("x", "ks")
    s = re.sub(r"[aeiouy]", "", s)
    out = []
    for ch in s:
        if ch == "h" and out and out[-1] != "h":
            continue  # 'bh' -> 'b', 'sh' -> 's' : forgive aspiration spelling
        if out and out[-1] == ch:
            continue  # 'Sunny' == 'सनी'
        out.append(ch)
    return "".join(out)


def match_customer(name: str, customers: list[dict], allow_prefix: bool = False) -> dict | None:
    """Find an existing customer. allow_prefix also matches "रमेशला" to "रमेश"."""
    if not name:
        return None
    low = nfc(name.strip().lower())
    for c in customers:
        if nfc(c["name"].lower()) == low:
            return c
    sk = skeleton(name)
    if not sk:
        return None
    hits = [c for c in customers if skeleton(c["name"]) == sk
            or skeleton(c["name"].split()[0]) == sk]
    if not hits and allow_prefix and len(sk) >= 3:
        hits = sorted((c for c in customers if len(skeleton(c["name"])) >= 3 and sk.startswith(skeleton(c["name"]))),
                      key=lambda c: -len(skeleton(c["name"])))
    return hits[0] if hits else None


def _name_like(tok: Tok) -> bool:
    return tok.num is None and tok.low not in STOP_WORDS and len(tok.low) >= 2 and tok.low != "₹"


def _clean_name(words: list[str]) -> str:
    name = " ".join(words)
    if name.isascii():
        return name.title()
    for suf in NAME_SUFFIXES:
        if name.endswith(suf) and len(name) - len(suf) >= 2:
            return name[: -len(suf)]
    return name


def find_customer_tokens(toks: list[Tok], customers: list[dict], guess: bool = True):
    """Returns (existing_customer | None, new_name | None, token_indexes).
    guess=False skips rule 3, for the second half of a sentence ("...और 1000 जमा")."""
    # 1) someone already in the khata (check two-word names first)
    for i in range(len(toks)):
        if not _name_like(toks[i]):
            continue
        if i + 1 < len(toks) and _name_like(toks[i + 1]):
            c = match_customer(f"{toks[i].text} {toks[i + 1].text}", customers)
            if c and len(c["name"].split()) > 1:
                return c, None, [i, i + 1]
        c = match_customer(toks[i].text, customers, allow_prefix=True)
        if c:
            return c, None, [i]
    # 2) a new name: the word(s) just before "ji / bhaiya / ne / ko / ka ..."
    for m in range(1, len(toks)):
        if toks[m].low in NAME_MARKERS and _name_like(toks[m - 1]):
            idx = [m - 1]
            if m - 2 >= 0 and _name_like(toks[m - 2]):
                idx = [m - 2, m - 1]
            return None, _clean_name([toks[k].text for k in idx]), idx
    # 3) otherwise the first word that looks like a name
    for i, t in enumerate(toks if guess else []):
        if _name_like(t):
            return None, _clean_name([t.text]), [i]
    return None, None, []


_BREAK_RE = re.compile(r"[;!?।॥|\n]+|(?<!\d)[,.]+|[,.]+(?!\d)")
_ABBR_DOT = re.compile(r"\b(rs|inr|no)\.", re.I)


def tokenize_clauses(text: str) -> tuple[list[Tok], set[int]]:
    """Tokens, plus the token indexes where a new clause starts (after , . ? ।)."""
    toks: list[Tok] = []
    breaks: set[int] = set()
    for piece in _BREAK_RE.split(_ABBR_DOT.sub(r"\1 ", nfc(text))):
        part = tokenize(piece)
        if part and toks:
            breaks.add(len(toks))
        toks.extend(part)
    return toks, breaks


def _money_spots(toks: list[Tok]) -> list[tuple[int, bool]]:
    """Numbers that look like rupees, as (index, is_reference).
    "2 किलो", "15 तारीख" are skipped. In "1240 में से 500", 1240 is only a reference."""
    spots = []
    for k, t in enumerate(toks):
        if t.num is None or t.num <= 0:
            continue
        nxt = toks[k + 1].low if k + 1 < len(toks) else ""
        nxt2 = toks[k + 2].low if k + 2 < len(toks) else ""
        prv = toks[k - 1].low if k > 0 else ""
        prv2 = toks[k - 2].low if k > 1 else ""
        if nxt in UNIT_WORDS or nxt in TIME_WORDS:
            continue
        has_currency = nxt in CURRENCY_WORDS or prv in CURRENCY_WORDS
        if t.from_words and not has_currency and t.num < 20:
            continue  # "दो" alone is usually "give" or a quantity
        reference = (nxt in _IN and nxt2 in _FROM) or (prv == "of" and prv2 == "out") \
            or nxt in _NOT or (nxt in CURRENCY_WORDS and nxt2 in _NOT)   # "500 नहीं 400"
        weak = not has_currency and (t.num < 10 or (t.num < 100 and nxt in ITEM_WORDS))  # "5 अंडे"
        spots.append((k, reference, has_currency, weak))
    real = [x for x in spots if not x[1]]
    if len(real) > 1 and any(not x[3] for x in real):
        spots = [x for x in spots if x[1] or not x[3]]  # drop "5 अंडे" when real money is also said
    return [(k, ref, cur) for k, ref, cur, _ in spots]


def find_amount(toks: list[Tok]):
    spots = _money_spots(toks)
    real = [x for x in spots if not x[1]] or spots
    best = None  # (score, value, index): a number said with "रुपये" wins, then the bigger one
    for k, _, has_currency in real:
        score = (2 if has_currency else 1, toks[k].num)
        if best is None or score > best[0]:
            best = (score, toks[k].num, k)
    return (best[1], best[2]) if best else (None, None)


def _intent_of(toks: list[Tok], amount_idx: int | None, shop_speaks: bool = False) -> tuple[str | None, bool]:
    """('credit' | 'payment' | None, said_clearly). None = no hint at all in these words.
    shop_speaks: an earlier part was "रमेश को ... दिया", so a bare "1000 लिए" means the shop took money."""
    words = {t.low for t in toks}
    gave_to = words & _set("को ko to")         # shop gave TO the customer
    from_them = words & _set("ने से ne se")    # customer gave / received FROM them
    pairs = list(zip(toks, toks[1:]))
    trios = list(zip(toks, toks[1:], toks[2:]))
    gave_and_left = any(x.low in _GIVE and y.low in _WENT for x, y in pairs) or \
        any(x.low in _GIVE and y.low in _KE and z.low in _WENT for x, y, z in trios)   # "दे गए", "दे के गए" = paid
    took_away = any(x.low in _TAKE and y.low in _WENT for x, y in pairs) or \
        any(x.low in _TAKE and y.low in _KE and z.low in _WENT for x, y, z in trios)   # "ले गए", "ले के गए" = udhaar

    if (words & STRONG_PAYMENT_WORDS or gave_and_left) and not (gave_to and not from_them and words & CREDIT_WORDS):
        return "payment", True
    if words & CREDIT_WORDS:
        return "credit", True
    if words & TAKE_WORDS or took_away:
        # "रमेश से 500 लिए" = we took money from him. "रमेश ने 500 का सामान लिया" = he took goods.
        if (words & _FROM or shop_speaks) and not words & _set("ने ne") and not words & ITEM_WORDS:
            return "payment", True
        return "credit", True
    if words & PAYMENT_WORDS:
        return ("credit" if gave_to and not from_them else "payment"), True
    if amount_idx is not None:
        after = [t.low for t in toks[amount_idx + 1:amount_idx + 3] if t.low not in CURRENCY_WORDS]
        if after and after[0] in _WORTH:
            return "credit", False  # "2000 का सामान", "2000 रुपये का सामान" = goods worth 2000
    return None, False


def _lead_in(tok: Tok, english_ok: bool) -> bool:
    """Words that start a new part, before its amount: "और", "वो", "सुरेश ने", "₹", "paid"."""
    if tok.num is not None:
        return False
    low = tok.low
    if low in CONJ_WORDS or low in PRONOUNS or low in NAME_MARKERS or low in CURRENCY_WORDS or low in FILLER_WORDS \
            or low in TOTAL_WORDS:
        return True
    if english_ok and low in ENGLISH_ACTIONS:
        return True
    return _name_like(tok)


def _cut_points(toks: list[Tok], breaks: set[int], anchors: list[int]) -> list[int]:
    """Where one action ends and the next begins, between each pair of amounts."""
    cuts = []
    for a, b, stop in zip(anchors, anchors[1:], anchors[2:] + [len(toks)]):
        conj = [k for k in range(a + 1, b) if toks[k].low in CONJ_WORDS]
        if conj:  # "...सामान लिया | और वो 1000 जमा..."
            cuts.append(conj[-1])
            continue
        # Hindi puts the verb after the amount, English before it ("took 2000, paid 500")
        english_ok = not ({t.low for t in toks[b + 1:stop]} & ACTION_WORDS)
        s = b
        while s - 1 > a and _lead_in(toks[s - 1], english_ok):
            s -= 1
        later = sorted(p for p in breaks if s <= p <= b)
        cuts.append(later[0] if later else s)
    return cuts


def _several(toks: list[Tok], breaks: set[int], anchors: list[int], customers: list[dict]) -> list[dict]:
    """Split a sentence with several amounts into one action per amount."""
    bounds = [0] + _cut_points(toks, breaks, anchors) + [len(toks)]
    parts = []
    shop_speaks = False
    for n, (s, e) in enumerate(zip(bounds, bounds[1:])):
        seg = toks[s:e]
        amount, amount_idx = find_amount(seg)
        if amount is None:
            continue
        words = {t.low for t in seg}
        intent, clear = _intent_of(seg, amount_idx, shop_speaks)
        shop_speaks = shop_speaks or bool(words & _set("को ko") and not words & _set("ने ne"))
        existing, new_name, name_idx = find_customer_tokens(seg, customers, guess=(n == 0))
        parts.append({"intent": intent, "customer": existing["name"] if existing else new_name,
                      "amount": amount, "_clear": clear, "_seg": seg, "_skip": set(name_idx) | {amount_idx},
                      # "अब 1000 बाकी है", "कुल 500": a remark about the account, not a new entry
                      "_remark": not clear and bool(words & (BALANCE_WORDS | TOTAL_WORDS))})
    # "वो / उन्होंने / ..." or no name at all = the person named before
    last = next((p["customer"] for p in parts if p["customer"]), None)
    for p in parts:
        if p["customer"]:
            last = p["customer"]
        else:
            p["customer"] = last
    acts = [p for p in parts if not p["_remark"]]
    # "200 का आटा, 300 का तेल, 500 हुए": an unclear amount that is just the sum of the others
    if len(acts) > 2:
        for p in acts:
            others = sum(q["amount"] for q in acts if q is not p)
            if not p["_clear"] and abs(p["amount"] - others) < 0.01:
                acts = [q for q in acts if q is not p]
                break
    # a part without a verb takes the verb of the next part ("200 का आटा और 300 का तेल लिया")
    for i, a in enumerate(acts):
        if a["intent"] is None:
            later = [b["intent"] for b in acts[i + 1:] if b["intent"]]
            earlier = [b["intent"] for b in acts[:i] if b["intent"]]
            a["intent"] = (later or earlier[::-1] or ["credit"])[0]
    out = []
    for a in acts:
        items = _items_note(a["_seg"], a["_skip"]) if a["intent"] == "credit" else ""
        out.append({"intent": a["intent"], "customer": a["customer"], "amount": a["amount"], "items": items or None})
    return out


def _items_note(toks: list[Tok], skip: set[int]) -> str:
    keep = []
    for k, t in enumerate(toks):
        if k in skip or t.low in CURRENCY_WORDS:
            continue
        if t.num is None and t.low in (STOP_WORDS - UNIT_WORDS - ITEM_WORDS):
            continue
        keep.append(t.text)
    note = " ".join(keep).strip()
    return note[:80]


def parse_due(toks: list[Tok], today: date | None = None) -> date | None:
    """ "कल", "परसों", "शुक्रवार", "5 तारीख", "3 दिन में", "अगले हफ्ते", "महीने के आखिर" -> a date."""
    today = today or date.today()
    found: list[tuple[int, date]] = []  # (priority, date): a clear date beats a vague one
    lows = [t.low for t in toks]
    for k, t in enumerate(toks):
        nxt = lows[k + 1] if k + 1 < len(toks) else ""
        if t.num is not None and nxt in _DATE_AFTER and 1 <= t.num <= 31:
            day = int(t.num)
            year, month = today.year, today.month
            if day < today.day:
                year, month = (year + 1, 1) if month == 12 else (year, month + 1)
            found.append((0, date(year, month, min(day, calendar.monthrange(year, month)[1]))))
        elif t.num is not None and nxt in _DAYS_AFTER and t.num <= 365:
            found.append((1, today + timedelta(days=int(t.num))))
        elif t.low in WEEKDAYS:
            found.append((1, today + timedelta(days=(WEEKDAYS[t.low] - today.weekday()) % 7 or 7)))
        elif t.low in _DAY_AFTER:
            found.append((2, today + timedelta(days=2)))
        elif t.low in _TOMORROW:
            found.append((2, today + timedelta(days=1)))
        elif t.low in _TODAY_D:
            found.append((3, today))
        elif t.low in _WEEK:
            found.append((3, today + timedelta(days=7)))
        elif t.low in _MONTH_END:
            found.append((3, date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])))
    return min(found, key=lambda x: x[0])[1] if found else None


def _is_promise(toks: list[Tok]) -> bool:
    words = {t.low for t in toks}
    return bool(words & FUTURE_PAY) or bool(words & _WILL and words & (_WILL_PAY | PAYMENT_WORDS)) \
        or bool(words & _FUTURE_DO and words & (STRONG_PAYMENT_WORDS | _set("हिसाब hisaab hisab")))


def _as_text(toks: list[Tok], breaks: set[int]) -> str:
    return " ".join(("," if k in breaks and k else "") + t.text for k, t in enumerate(toks)).replace(" ,", ",")


def _promise(toks: list[Tok], breaks: set[int], anchors: list[int], customers: list[dict]) -> dict | None:
    """ "रमेश कल 500 देगा" -> a promise. "रमेश ने 500 दिए और बाकी शुक्रवार को देगा" -> payment + promise."""
    cuts = sorted(set(breaks) | {k for k, t in enumerate(toks) if t.low in CONJ_WORDS and k > 0})
    bounds = [0] + cuts + [len(toks)]
    spans = [(a, b) for a, b in zip(bounds, bounds[1:]) if b > a]
    promise_spans = [(a, b) for a, b in spans if _is_promise(toks[a:b])]
    if not promise_spans:
        return None
    inside = {k for a, b in promise_spans for k in range(a, b)}
    entries: list[dict] = []
    if any(k not in inside for k in anchors):  # money also changed hands in another part
        rest = [k for k in range(len(toks)) if k not in inside]
        rest_breaks = {i for i, k in enumerate(rest) if k in breaks or (i and rest[i - 1] + 1 != k)}
        done = rules_understand(_as_text([toks[k] for k in rest], rest_breaks), customers)
        entries = done["actions"] if done["intent"] == "multi" else [done] if done["intent"] in ("credit", "payment") else []
    part = [toks[k] for k in sorted(inside)] if entries else toks
    existing, new_name, _ = find_customer_tokens(part, customers, guess=not entries)
    customer = existing["name"] if existing else new_name or (entries[-1]["customer"] if entries else None)
    amount, _ = find_amount(part)
    due = parse_due(part) or parse_due(toks)
    promise = {"intent": "promise", "customer": customer, "amount": amount,
               "due": due.isoformat() if due else None, "items": None}
    if entries:
        return {"intent": "multi", "customer": entries[0]["customer"], "amount": None, "items": None,
                "actions": entries + [promise]}
    return promise


def is_cancel(text: str) -> bool:
    """ "रहने दो", "छोड़ो", "cancel": stop the question the app just asked."""
    toks = tokenize(text)
    return bool(toks) and len(toks) <= 4 and bool({t.low for t in toks} & (CANCEL_WORDS | UNDO_WORDS))


def rules_understand(text: str, customers: list[dict]) -> dict:
    toks, breaks = tokenize_clauses(text)
    words = {t.low for t in toks}
    is_question = "?" in text or bool(words & QUESTION_WORDS)

    anchors = [k for k, ref, _ in _money_spots(toks) if not ref]
    empty = {"intent": "unknown", "customer": None, "amount": None, "items": None}

    # "रमेश की लिमिट 2000 रखो" / "रमेश की लिमिट हटाओ"
    if words & LIMIT_WORDS:
        existing, new_name, _ = find_customer_tokens(toks, customers)
        if existing or new_name:
            amount = find_amount(toks)[0]
            return {**empty, "intent": "set_limit", "customer": existing["name"] if existing else new_name,
                    "amount": amount}

    # "बस", "धन्यवाद": end of a voice conversation
    if not anchors and words & BYE_WORDS and len(toks) <= 5 and not find_customer_tokens(toks, customers, False)[0]:
        return {**empty, "intent": "bye"}

    # "हटाओ, गलत सुना। मनीष जी 2000 का सामान ले गए..." = remove the last entry, then write this one
    undo_at = [k for k, t in enumerate(toks) if t.low in UNDO_WORDS]
    if undo_at and anchors:
        before = [k for k in undo_at if k < anchors[0]]
        if not before:
            return {**empty, "intent": "undo"}  # "रमेश के 500 गलत हैं"
        u = max(before)
        cut = next((p for p in sorted(breaks) if u < p <= anchors[0]), u + 1)
        rest_toks = toks[cut:]
        then = rules_understand(_as_text(rest_toks, {p - cut for p in breaks if p > cut}), customers)
        if then["intent"] in ("credit", "payment", "multi", "promise"):
            return {**empty, "intent": "correct", "customer": then.get("customer"), "then": then}
        return {**empty, "intent": "undo"}

    # "आज किससे पैसा आना है?" / "आज के वादे"
    if not anchors and words & DUE_Q_WORDS and (words & TODAY_WORDS or is_question):
        return {**empty, "intent": "due_today"}

    # "रमेश शुक्रवार को देगा"
    promise = _promise(toks, breaks, anchors, customers)
    if promise:
        return promise

    # Two or more amounts: maybe two things happened ("2000 का सामान लिया और 1000 जमा किए")
    if len(anchors) > 1:
        acts = _several(toks, breaks, anchors, customers)
        if len(acts) > 1:
            return {"intent": "multi", "customer": acts[0]["customer"], "amount": None, "items": None,
                    "actions": acts}
        if len(acts) == 1:
            return acts[0]

    amount, amount_idx = find_amount(toks)
    existing, new_name, name_idx = find_customer_tokens(toks, customers)
    customer = existing["name"] if existing else new_name

    result = {"intent": "unknown", "customer": None, "amount": None, "items": None}

    if words & UNDO_WORDS and amount is None:
        result["intent"] = "undo"
        return result

    if amount is None:
        # "रमेश को उधार लिखो" / "रमेश ने पैसे दिए": an entry whose amount is missing -> the app asks back
        if not is_question and words & (_WRITE | STRONG_PAYMENT_WORDS | TAKE_WORDS | _GAVE) and (existing or new_name):
            result.update(intent=_intent_of(toks, None)[0] or "credit",
                          customer=existing["name"] if existing else new_name)
            return result
        if existing:
            result.update(intent="balance", customer=existing["name"])
        elif words & TODAY_WORDS:
            result["intent"] = "today"
        elif words & ALL_WORDS:
            result["intent"] = "all"
        elif is_question and new_name:
            result.update(intent="balance", customer=new_name)
        elif is_question:
            result["intent"] = "all"
        return result

    intent = _intent_of(toks, amount_idx)[0] or "credit"  # "रमेश 300" -> udhaar is the most common entry
    skip = set(name_idx) | ({amount_idx} if amount_idx is not None else set())
    skip |= {k for k, ref, _ in _money_spots(toks) if ref and k + 1 < len(toks) and toks[k + 1].low in _NOT}
    items = _items_note(toks, skip) if intent == "credit" else ""
    result.update(intent=intent, customer=customer, amount=amount, items=items or None)
    return result


# --- smart mode (optional LLM) ---------------------------------------------
_LLM_PROMPT = """You turn a shopkeeper's sentence into JSON commands for a credit ledger (udhaar khata) of a small Indian kirana shop.
The sentence can be in any Indian language (Hindi, Marathi, Gujarati, Bengali, Tamil, Telugu, Kannada...), English or Hinglish, in any script. It came from speech-to-text, so expect small mistakes.

intents:
- "credit": shop gave goods/money on credit to a customer (udhaar, likh do, khaate mein, "X ne 300 ka saamaan liya", "X ko 300 ka saamaan diya", "X 200 ka doodh le gaye")
- "payment": customer paid money back (jama, diye, lautaye, paid, "X ne 500 diye", "X 300 de gaye", "udhaar ke 200 jama kiye", "X se 500 liye")
- "balance": asking how much ONE customer owes
- "today": asking for today's summary
- "all": asking for everyone's dues, total dues, or who owes the most
- "undo": cancel / delete the last entry
- "unknown": anything else

ONE sentence can contain SEVERAL entries. List every entry, in the order said:
  "Manish ji ne 2000 ka saman liya aur wo 1000 jama karke gaye" ->
  {"actions": [{"intent": "credit", "customer": "Manish", "amount": 2000, "items": "saman"},
               {"intent": "payment", "customer": "Manish", "amount": 1000, "items": null}]}
- Pronouns (wo, vo, unhone, usne, he, she, they) mean the person named before.
- A remark about the balance or a total ("ab 1000 baaki hai", "kul 500 hue", "1240 mein se") is NOT an entry. Never add it.
- Never add amounts together and never invent an amount that was not said.
- For balance / today / all / undo / unknown, return exactly one action.

Return ONLY a JSON object: {"actions": [{"intent": string, "customer": string or null, "amount": number or null, "items": string or null}]}
- customer: just the person's name, without ji / bhaiya / didi / sahab.
- amount: rupees as a plain number (2000, not "2,000" or "₹2000"). Quantities like "2 kilo" are NOT the amount.
- items: short note of goods mentioned, in the same language as the sentence, or null. Only for credit.
- Existing customers: %s. If the person is one of them (even in another script or spelling), return that exact existing name."""


def _to_amount(value) -> float | None:
    """2000, "2,000", "₹2000", "Rs 2000.50" -> number. Anything else -> None."""
    if value in (None, "", False):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    m = re.search(r"\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(m.group(0)) if m and float(m.group(0)) > 0 else None


def llm_understand(text: str, customers: list[dict]) -> dict:
    names = json.dumps([c["name"] for c in customers][:150], ensure_ascii=False)
    body = {
        "model": settings.llm_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _LLM_PROMPT % names},
            {"role": "user", "content": text},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.llm_key}"}
    url = f"{settings.llm_base}/chat/completions"
    r = requests.post(url, json=body, headers=headers, timeout=20)
    if r.status_code == 400:  # some providers don't support response_format
        body.pop("response_format")
        r = requests.post(url, json=body, headers=headers, timeout=20)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    match = re.search(r"\{.*\}", content, re.S)
    data = json.loads(match.group(0) if match else content)
    raw = data.get("actions") if isinstance(data.get("actions"), list) else [data]

    acts, last = [], None
    for a in raw:
        if not isinstance(a, dict):
            continue
        intent = a.get("intent") if a.get("intent") in INTENT_LABELS else "unknown"
        customer = (str(a.get("customer") or "")).strip() or None
        existing = match_customer(customer, customers) if customer else None
        customer = existing["name"] if existing else customer
        if intent in ("credit", "payment"):
            customer = customer or last  # "...aur wo 1000 jama" = same person
            last = customer
        acts.append({"intent": intent, "customer": customer, "amount": _to_amount(a.get("amount")),
                     "items": (a.get("items") or None) if intent == "credit" else None})
    entries = [a for a in acts if a["intent"] in ("credit", "payment")]
    if len(entries) > 1:
        return {"intent": "multi", "customer": entries[0]["customer"], "amount": None, "items": None,
                "actions": entries}
    if entries:
        return entries[0]
    return acts[0] if acts else {"intent": "unknown", "customer": None, "amount": None, "items": None}


def understand(text: str, customers: list[dict]) -> dict:
    rules = rules_understand(text, customers)
    special = rules["intent"] in ("promise", "set_limit", "due_today", "correct", "bye") or (
        rules["intent"] == "multi" and any(a["intent"] == "promise" for a in rules["actions"]))
    if special or not settings.llm_ready:
        rules["engine"] = "basic"
        return rules
    if settings.llm_ready:
        try:
            out = llm_understand(text, customers)
            out["engine"] = "smart"
            # the smart model sometimes keeps only one half of "...लिया और 1000 जमा किए"
            if out["intent"] in ("credit", "payment"):
                if rules["intent"] == "multi":
                    rules["engine"] = "smart+basic"
                    return rules
            return out
        except Exception as exc:  # network / key / parsing problem -> rules
            print(f"[understand] LLM failed, using basic rules: {exc}")
    rules["engine"] = "basic"
    return rules
