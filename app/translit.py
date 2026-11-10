"""Show a customer's name in the reader's own script.

Indian scripts share one layout in Unicode, so each letter has a "twin" at the same spot in
every script block. That lets us turn "रमेश" into "ரமேஷ்" (Tamil), "রমেশ" (Bengali) and so on.
For English we spell it out in Latin letters: "रमेश" -> "Ramesh".

This is only for showing and speaking names. The name is always saved the way it was said.
"""

from __future__ import annotations

import re
import unicodedata

BLOCKS = {"hi": 0x0900, "mr": 0x0900, "bn": 0x0980, "gu": 0x0A80, "ta": 0x0B80, "te": 0x0C00, "kn": 0x0C80}

# Tamil has no separate letters for these sounds; use the letter Tamil names normally use.
_TAMIL_FIX = str.maketrans({"ख": "क", "ग": "क", "घ": "क", "छ": "च", "झ": "ज", "ठ": "ट", "ड": "ट", "ढ": "ट",
                            "थ": "त", "द": "त", "ध": "त", "फ": "प", "ब": "प", "भ": "प", "स": "च", "श": "ष",
                            "ं": "न्", "ृ": "्रु", "ँ": "", "़": ""})
# Tamil-only letters -> nearest common Devanagari letter
_FROM_TAMIL = {0x0BA9: "न", 0x0BB1: "र", 0x0BB4: "ळ", 0x0BB7: "श", 0x0B9A: "स"}
_BENGALI_FIX = str.maketrans({"व": "ब"})


def to_devanagari(text: str) -> str:
    """Any Indian script -> Devanagari (letter by letter)."""
    out = []
    for ch in text:
        o = ord(ch)
        if o in _FROM_TAMIL:     # e.g. Tamil ச is usually an "s" sound in names (சுனிதா = Sunita)
            out.append(_FROM_TAMIL[o])
        elif 0x0980 <= o < 0x0D80:
            out.append(chr(0x0900 + (o - 0x0900) % 0x80))
        else:
            out.append(ch)
    return "".join(out)


def from_devanagari(text: str, lang: str) -> str:
    base = BLOCKS.get(lang, 0x0900)
    if base == 0x0900:
        return text
    s = unicodedata.normalize("NFD", text)
    if lang == "ta":
        s = s.translate(_TAMIL_FIX)
    elif lang == "bn":
        s = s.translate(_BENGALI_FIX)
    out = []
    for ch in s:
        o = ord(ch)
        if 0x0900 <= o < 0x0980 and not (0x0964 <= o <= 0x096F):
            twin = chr(base + (o - 0x0900))
            if unicodedata.name(twin, ""):   # skip letters the script doesn't have
                out.append(twin)
        else:
            out.append(ch)
    result = unicodedata.normalize("NFC", "".join(out))
    if lang == "ta":  # Tamil: ந starts a word, ன is used inside or at the end
        result = re.sub(r"(?<=[\u0B80-\u0BFF])ந", "ன", result)
    return result


def _to_dev_words(text: str) -> str:
    """Like to_devanagari, but also fixes how words end.
    In Tamil/Telugu/Kannada a final letter without ் / ్ / ್ keeps its "a" sound
    (సునీత = Suneeta), while Hindi drops it, so it becomes सुनीता there."""
    def fix(m: re.Match) -> str:
        word = m.group(0)
        south = any(0x0B80 <= ord(c) < 0x0D00 for c in word)
        dev = unicodedata.normalize("NFD", to_devanagari(word))
        if south and dev:
            if dev.endswith("्"):
                dev = dev[:-1]
            elif dev[-1] in _CONS:
                dev += "ा"
        return dev
    return re.sub(r"[\u0900-\u0D7F]+", fix, text)


def _final_consonant(text: str, lang: str) -> str:
    """Tamil, Telugu and Kannada mark a word that ends in a consonant (ரமேஷ்);
    Hindi, Marathi, Gujarati and Bengali don't (रमेश)."""
    def fix(word: str) -> str:
        if lang in ("ta", "te", "kn"):
            return word + "्" if word and word[-1] in _CONS else word
        return word[:-1] if len(word) > 1 and word.endswith("्") else word
    return re.sub(r"[\u0900-\u097F]+", lambda m: fix(m.group(0)), unicodedata.normalize("NFD", text))


_CONS = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
         "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
         "ऩ": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ऱ": "r", "ल": "l",
         "ळ": "l", "ऴ": "zh", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h"}
_NUKTA = {"क": "q", "ख": "kh", "ग": "gh", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f", "य": "y"}
_VOWEL = {"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri", "ए": "e", "ऐ": "ai",
          "ओ": "o", "औ": "au", "ऍ": "e", "ऑ": "o", "ऎ": "e", "ऒ": "o"}
_MATRA = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
          "ॅ": "e", "ॉ": "o", "ॆ": "e", "ॊ": "o"}


def _is_dev(ch: str) -> bool:
    return "ऀ" <= ch <= "ॣ"


def to_latin(text: str) -> str:
    """'रमेश' -> 'Ramesh', 'सुनीता' -> 'Sunita', 'ரமேஷ்' -> 'Ramesh'."""
    chars = list(unicodedata.normalize("NFD", _to_dev_words(text)))
    out = []
    i = 0
    while i < len(chars):
        ch = chars[i]
        if ch in _CONS:
            c, j = _CONS[ch], i + 1
            if j < len(chars) and chars[j] == "़":
                c, j = _NUKTA.get(ch, c), j + 1
            nxt = chars[j] if j < len(chars) else ""
            if nxt in _MATRA:
                out.append(c + _MATRA[nxt])
                j += 1
            elif nxt == "्":
                out.append(c)
                j += 1
            else:
                out.append(c if not _is_dev(nxt) else c + "a")  # no "a" at the end of a word
            i = j
            continue
        if ch in _VOWEL:
            out.append(_VOWEL[ch])
        elif ch in "ंँ":
            out.append("n")
        elif ch == "ः":
            out.append("h")
        elif ch != "़":
            out.append(ch)
        i += 1
    s = "".join(out)
    return re.sub(r"[a-z]+", lambda m: m.group(0)[0].upper() + m.group(0)[1:], s)


def _has_indic(s: str) -> bool:
    return any(0x0900 <= ord(c) < 0x0D80 for c in s)


def name_for(name: str | None, lang: str) -> str | None:
    """The customer's name written for a reader of `lang`."""
    if not name or not _has_indic(name):
        return name  # Latin names stay as they are
    if lang == "en":
        return to_latin(name)
    base = BLOCKS.get(lang)
    if base is None:
        return name
    if all(base <= ord(c) < base + 0x80 for c in name if 0x0900 <= ord(c) < 0x0D80):
        return name  # already in this script
    return from_devanagari(_final_consonant(_to_dev_words(name), lang), lang)
