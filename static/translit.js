// Show a customer's name in the reader's own script (same rules as app/translit.py).
// "रमेश" -> "Ramesh" (English), "ரமேஷ்" (Tamil), "রমেশ" (Bengali) ...
// Only for showing: the name is always saved the way it was said.

const BLOCKS = { hi: 0x0900, mr: 0x0900, bn: 0x0980, gu: 0x0A80, ta: 0x0B80, te: 0x0C00, kn: 0x0C80 };
const FROM_TAMIL = { 0x0BA9: "न", 0x0BB1: "र", 0x0BB4: "ळ", 0x0BB7: "श", 0x0B9A: "स" };
const TAMIL_FIX = {
  "ख": "क", "ग": "क", "घ": "क", "छ": "च", "झ": "ज", "ठ": "ट", "ड": "ट", "ढ": "ट", "थ": "त", "द": "त", "ध": "त",
  "फ": "प", "ब": "प", "भ": "प", "स": "च", "श": "ष", "ं": "न्", "ृ": "्रु", "ँ": "", "़": "",
};
const BENGALI_FIX = { "व": "ब" };
const CONS = {
  "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
  "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
  "ऩ": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ऱ": "r", "ल": "l",
  "ळ": "l", "ऴ": "zh", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h",
};
const NUKTA = { "क": "q", "ख": "kh", "ग": "gh", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f", "य": "y" };
const VOWEL = { "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऍ": "e", "ऑ": "o", "ऎ": "e", "ऒ": "o" };
const MATRA = { "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॅ": "e", "ॉ": "o", "ॆ": "e", "ॊ": "o" };
const VIRAMA = "्";

const cp = (c) => c.codePointAt(0);
const hasIndic = (s) => [...s].some((c) => cp(c) >= 0x0900 && cp(c) < 0x0D80);

function toDevanagari(text) {
  return [...text].map((c) => {
    const o = cp(c);
    if (FROM_TAMIL[o]) return FROM_TAMIL[o];
    if (o >= 0x0980 && o < 0x0D80) return String.fromCodePoint(0x0900 + ((o - 0x0900) % 0x80));
    return c;
  }).join("");
}

function toDevWords(text) {
  return text.replace(/[ऀ-ൿ]+/g, (word) => {
    const south = [...word].some((c) => cp(c) >= 0x0B80 && cp(c) < 0x0D00);
    let dev = toDevanagari(word).normalize("NFD");
    if (south && dev) {
      if (dev.endsWith(VIRAMA)) dev = dev.slice(0, -1);
      else if (CONS[dev.at(-1)]) dev += "ा";
    }
    return dev;
  });
}

function finalConsonant(text, lang) {
  return text.normalize("NFD").replace(/[ऀ-ॿ]+/g, (w) => {
    if (["ta", "te", "kn"].includes(lang)) return CONS[w.at(-1)] ? w + VIRAMA : w;
    return w.length > 1 && w.endsWith(VIRAMA) ? w.slice(0, -1) : w;
  });
}

function fromDevanagari(text, lang) {
  const base = BLOCKS[lang] ?? 0x0900;
  if (base === 0x0900) return text.normalize("NFC");
  let s = text.normalize("NFD");
  const fix = lang === "ta" ? TAMIL_FIX : lang === "bn" ? BENGALI_FIX : null;
  if (fix) s = [...s].map((c) => fix[c] ?? c).join("");
  let out = [...s].map((c) => {
    const o = cp(c);
    if (o >= 0x0900 && o < 0x0980 && !(o >= 0x0964 && o <= 0x096F)) {
      const twin = String.fromCodePoint(base + (o - 0x0900));
      return /\p{Assigned}/u.test(twin) ? twin : "";
    }
    return c;
  }).join("").normalize("NFC");
  if (lang === "ta") out = out.replace(/(?<=[஀-௿])ந/g, "ன");
  return out;
}

function toLatin(text) {
  const chars = [...toDevWords(text).normalize("NFD")];
  const isDev = (c) => c >= "ऀ" && c <= "ॣ";
  let out = "";
  for (let i = 0; i < chars.length;) {
    const ch = chars[i];
    if (CONS[ch]) {
      let c = CONS[ch], j = i + 1;
      if (chars[j] === "़") { c = NUKTA[ch] ?? c; j++; }
      const nxt = chars[j] ?? "";
      if (MATRA[nxt]) { out += c + MATRA[nxt]; j++; }
      else if (nxt === VIRAMA) { out += c; j++; }
      else out += isDev(nxt) ? c + "a" : c; // no "a" at the end of a word
      i = j;
      continue;
    }
    if (VOWEL[ch]) out += VOWEL[ch];
    else if (ch === "ं" || ch === "ँ") out += "n";
    else if (ch === "ः") out += "h";
    else if (ch !== "़") out += ch;
    i++;
  }
  return out.replace(/[a-z]+/g, (w) => w[0].toUpperCase() + w.slice(1));
}

export function nameFor(name, lang) {
  if (!name || !hasIndic(name)) return name;
  if (lang === "en") return toLatin(name);
  const base = BLOCKS[lang];
  if (base === undefined) return name;
  const indic = [...name].filter((c) => cp(c) >= 0x0900 && cp(c) < 0x0D80);
  if (indic.every((c) => cp(c) >= base && cp(c) < base + 0x80)) return name; // already in this script
  return fromDevanagari(finalConsonant(toDevWords(name), lang), lang);
}
