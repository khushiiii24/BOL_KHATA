"""Numbers <-> words, the Indian way (hazaar, lakh, crore).

Two jobs:
1. Turn amounts into spoken words for Gnani Timbre, e.g. 1240 -> "एक हज़ार दो सौ चालीस".
   (Gnani's docs recommend writing numbers and currency as words for the voice.)
2. Read number words a shopkeeper might say or type, e.g. "साढ़े तीन सौ" -> 350,
   "dedh sau" -> 150, as a backup in case the transcript has words instead of digits.
"""

import unicodedata


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# Hindi has a separate word for every number from 0 to 99.
HINDI_0_99 = [_nfc(w) for w in (
    "शून्य एक दो तीन चार पाँच छह सात आठ नौ "
    "दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस "
    "बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस "
    "तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस "
    "चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास "
    "पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ "
    "साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर "
    "सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी "
    "अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी "
    "नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे"
).split()]
assert len(HINDI_0_99) == 100

_EN_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
            "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def hindi_words(n: int) -> str:
    """1240 -> 'एक हज़ार दो सौ चालीस'"""
    n = int(round(n))
    if n < 0:
        return "माइनस " + hindi_words(-n)
    if n < 100:
        return HINDI_0_99[n]
    parts = []
    crore, n = divmod(n, 10_000_000)
    if crore:
        parts.append(hindi_words(crore) + " करोड़")
    lakh, n = divmod(n, 100_000)
    if lakh:
        parts.append(HINDI_0_99[lakh] + " लाख")
    thousand, n = divmod(n, 1000)
    if thousand:
        parts.append(HINDI_0_99[thousand] + " हज़ार")
    hundred, n = divmod(n, 100)
    if hundred:
        parts.append(HINDI_0_99[hundred] + " सौ")
    if n:
        parts.append(HINDI_0_99[n])
    return _nfc(" ".join(parts))


def _en_below_100(n: int) -> str:
    if n < 20:
        return _EN_ONES[n]
    tens, ones = divmod(n, 10)
    return _EN_TENS[tens] + ("-" + _EN_ONES[ones] if ones else "")


def english_words(n: int) -> str:
    """1240 -> 'one thousand two hundred forty' (uses lakh and crore)."""
    n = int(round(n))
    if n < 0:
        return "minus " + english_words(-n)
    if n < 100:
        return _en_below_100(n)
    parts = []
    crore, n = divmod(n, 10_000_000)
    if crore:
        parts.append(english_words(crore) + " crore")
    lakh, n = divmod(n, 100_000)
    if lakh:
        parts.append(_en_below_100(lakh) + " lakh")
    thousand, n = divmod(n, 1000)
    if thousand:
        parts.append(_en_below_100(thousand) + " thousand")
    hundred, n = divmod(n, 100)
    if hundred:
        parts.append(_EN_ONES[hundred] + " hundred")
    if n:
        parts.append(_en_below_100(n))
    return " ".join(parts)


def inr(n: float) -> str:
    """1240 -> '₹1,240' and 124000 -> '₹1,24,000' (Indian comma style)."""
    n = int(round(n))
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"{sign}₹{s}"


# ---------------------------------------------------------------------------
# Reading number words (backup for when digits are not in the transcript)
# ---------------------------------------------------------------------------

# kind: "num" = a number, "mult" = multiplier (sau/hazaar/lakh/crore),
#       "mod" = modifier that changes the next number (sava/saadhe/paune)
NUMBER_WORDS: dict[str, tuple[str, float]] = {}

for _value, _word in enumerate(HINDI_0_99):
    if _value:
        NUMBER_WORDS[_word] = ("num", _value)

for _word, _value in {
    "पांच": 5, "छः": 6, "छे": 6, "पन्द्रह": 15, "डेढ़": 1.5, "डेढ": 1.5, "ढाई": 2.5,
    # Hinglish (typed or transcribed in Latin letters). Words that also mean
    # something else in Hindi ("tera", "bara", "saath"...) are left out on purpose.
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "chhe": 6, "chhah": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "gyarah": 11, "barah": 12, "baarah": 12, "terah": 13, "chaudah": 14,
    "pandrah": 15, "solah": 16, "satrah": 17, "atharah": 18, "unnis": 19, "unees": 19,
    "bees": 20, "pachees": 25, "pachchis": 25, "tees": 30, "chalees": 40, "chalis": 40,
    "pachaas": 50, "pachas": 50, "sattar": 70, "assi": 80, "nabbe": 90,
    "dedh": 1.5, "dhai": 2.5, "dhaai": 2.5,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "fifty": 50,
}.items():
    NUMBER_WORDS[_nfc(_word)] = ("num", _value)

for _word, _value in {
    "सौ": 100, "हज़ार": 1000, "हजार": 1000, "लाख": 100_000, "करोड़": 10_000_000, "करोड": 10_000_000,
    "sau": 100, "hundred": 100, "hazaar": 1000, "hazar": 1000, "hajar": 1000, "hajaar": 1000,
    "thousand": 1000, "lakh": 100_000, "lac": 100_000, "laakh": 100_000,
    "crore": 10_000_000, "karod": 10_000_000, "karor": 10_000_000,
}.items():
    NUMBER_WORDS[_nfc(_word)] = ("mult", _value)

for _word, _value in {
    "सवा": 0.25, "साढ़े": 0.5, "साढे": 0.5, "पौने": -0.25,
    "sava": 0.25, "sawa": 0.25, "saadhe": 0.5, "sadhe": 0.5, "paune": -0.25,
}.items():
    NUMBER_WORDS[_nfc(_word)] = ("mod", _value)


def word_number_kind(word: str):
    """Returns ('num'|'mult'|'mod', value) or None."""
    return NUMBER_WORDS.get(_nfc(word.lower()))
