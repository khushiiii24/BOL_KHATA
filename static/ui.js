// Small helpers shared by every screen: text, money, dates, avatars, sound, toasts.
import { getLang, locale, t } from "/static/i18n.js";
import { nameFor } from "/static/translit.js";

export const $ = (id) => document.getElementById(id);
export const rupee = (n) => "₹" + Math.round(Math.abs(Number(n) || 0)).toLocaleString("en-IN");
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
export const lang = () => getLang();
// a customer's name written in the reader's script (the saved name never changes)
export const show = (name) => nameFor(name, getLang());

export const APP_VERSION = "3.0"; // must match APP_VERSION in app/main.py

// Everything the screens share
export const state = {
  ledger: null, status: null, me: null, profile: null,
  tab: "home", filter: "all", sort: "recent", search: "",
  openCustomer: null, audio: null, ttsWarned: false,
};
// Screens register their render functions here (avoids import loops)
export const hooks = {};

// remembered choices (this browser only)
export const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};

export async function api(path, options = {}) {
  let res;
  try { res = await fetch(path, options); } catch { throw new Error(t("serverDown")); }
  const type = res.headers.get("content-type") || "";
  const body = type.includes("json") ? await res.json() : null;
  if (res.status === 401 && !path.startsWith("/api/auth/")) { location.reload(); throw new Error("Please sign in again."); }
  if (!res.ok) throw new Error((body && body.detail) || `Request failed (${res.status})`);
  return body;
}
export const send = (path, method, data) => api(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data ?? {}) });

let toastTimer;
export function toast(msg, ms = 5000) {
  const el = $("toast");
  (document.querySelector("dialog[open]") || document.body).appendChild(el); // stay above open windows
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), ms);
}

// ------------------------------------------------------------ dates
export function dayDiff(iso) { // days from that day until today (positive = in the past)
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const day = new Date(iso.length <= 10 ? iso + "T00:00:00" : iso); day.setHours(0, 0, 0, 0);
  return Math.round((today - day) / 86400000);
}
export function whenText(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = dayDiff(iso);
  const time = d.toLocaleTimeString(locale(), { hour: "numeric", minute: "2-digit" });
  if (diff <= 0) return t("today", { t: time });
  if (diff === 1) return t("yesterday");
  if (diff < 7) return t("daysAgo", { n: diff });
  return d.toLocaleDateString(locale(), { day: "numeric", month: "short", year: diff > 300 ? "numeric" : undefined });
}
export function shortDate(iso) {
  return new Date(iso + "T00:00:00").toLocaleDateString(locale(), { weekday: "short", day: "numeric", month: "short" });
}
// a promise's day in words: "today", "tomorrow", "Fri, 13 Nov", "3 days late"
export function dueWords(p) {
  if (p.days === 0) return t("promiseTodayW");
  if (p.days === 1) return t("promiseTomorrow");
  if (p.days < 0) return t("promiseLate", { n: -p.days });
  return shortDate(p.due_date);
}
export function ageWords(c) {
  if (!(c.balance > 0.5) || !c.due_since) return "";
  const d = Math.max(0, dayDiff(c.due_since));
  return d === 0 ? t("dueToday") : d === 1 ? t("dueDay1") : t("dueDays", { n: d });
}

// ------------------------------------------------------------ people
const AVATAR_COLORS = [
  ["#F6E3B4", "#7A4E00"], ["#DCEBD8", "#1D6B3F"], ["#DDE3F3", "#263A85"],
  ["#F5D9D6", "#9E1B22"], ["#EADDF0", "#5B3A7A"], ["#D8ECEA", "#0F6466"],
];
export function avatar(name, { big = false, trust = null } = {}) {
  const saved = String(name || "?").trim();
  const chars = [...String(show(saved) || "?").trim()];
  let h = 0;
  for (const ch of saved) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  const [bg, fg] = AVATAR_COLORS[h % AVATAR_COLORS.length];
  // keep a vowel sign with its letter in Indian scripts (e.g. "सु", "சு")
  const initial = chars[1] && /\p{M}/u.test(chars[1]) ? chars[0] + chars[1] : (chars[0] || "?");
  const ring = trust && trust !== "new" ? ` t-${trust}` : "";
  return `<span class="avatar${big ? " big" : ""}${ring}" style="--av-bg:${bg};--av-fg:${fg}" aria-hidden="true">${esc(initial.toUpperCase())}</span>`;
}
export const TRUST_KEYS = { good: "trustGood", ok: "trustOk", risk: "trustRisk", new: "trustNew" };
export function trustBadge(trust, withScore = true) {
  if (!trust) return "";
  const score = withScore && trust.score != null ? ` ${trust.score}` : "";
  return `<span class="tbadge ${trust.label}">${esc(t(TRUST_KEYS[trust.label]))}${score}</span>`;
}

// ------------------------------------------------------------ items
const ITEM_EMOJI = [
  [/आटा|aata|atta|गेहूँ|गेहूं|लोट|લોટ|আটা|மாவு|పిండి|ಹಿಟ್ಟು/i, "🌾"],
  [/चावल|chawal|rice|तांदूळ|ચોખા|চাল|அரிசி|బియ్యం|ಅಕ್ಕಿ/i, "🍚"],
  [/दाल|डाळ|daal|dal\b|દાળ|ডাল|பருப்பு|పప్పు|ಬೇಳೆ/i, "🥣"],
  [/तेल|\btel\b|oil|તેલ|তেল|எண்ணெய்|నూనె|ಎಣ್ಣೆ/i, "🛢️"],
  [/चीनी|शक्कर|साखर|cheeni|chini|sugar|ખાંડ|চিনি|சர்க்கரை|చక్కెర|ಸಕ್ಕರೆ/i, "🍬"],
  [/नमक|मीठ|namak|salt|મીઠું|লবণ|உப்பு|ఉప్పు|ಉಪ್ಪು/i, "🧂"],
  [/दूध|doodh|milk|दही|dahi|દૂધ|দুধ|பால்|పాలు|ಹಾಲು/i, "🥛"],
  [/ब्रेड|bread|पाव|પાઉં|পাউরুটি|ரொட்டி|బ్రెడ్|ಬ್ರೆಡ್|બ્રેડ/i, "🍞"],
  [/अंड|\bande\b|anda|egg|ઈંડા|ডিম|முட்டை|గుడ్డు|ಮೊಟ್ಟೆ/i, "🥚"],
  [/चाय|चहा|chai|tea|ચા|চা|டீ|టీ|ಚಹಾ|ಟೀ/i, "☕"], [/बिस्कुट|biscuit/i, "🍪"], [/मैगी|maggi|noodle/i, "🍜"],
  [/साबुन|साबण|sabun|soap|सर्फ|surf|शैम्पू|shampoo|સાબુ|সাবান|சோப்பு|సబ్బు|ಸೋಪು/i, "🧼"],
  [/सब्ज|भाजी|sabzi|sabji|प्याज|आलू|टमाटर/i, "🥬"],
  [/घी|ghee|मक्खन|butter|ঘি|நெய்|నెయ్యి|ತುಪ್ಪ/i, "🧈"], [/मसाला|masala|हल्दी|मिर्च|haldi|mirch/i, "🌶️"],
  [/पानी|water|कोल्ड|cold ?drink|पेप्सी|कोक/i, "🥤"],
  [/राशन|किराणा|ration|सामान|saman|saamaan|કરિયાણું|রেশন|மளிகை|సరుకులు|ದಿನಸಿ/i, "🛒"],
];
export const emojiFor = (text) => (ITEM_EMOJI.find(([re]) => re.test(text || "")) || [null, "🛍️"])[1];
export function itemChips(note) {
  if (!note) return "";
  const qty = /\s+(?=(?:\d|एक |दो |तीन |चार |पाँच |पांच |छह |आधा |डेढ़ |ढाई |ek |do |teen |char |paanch |aadha |dedh |dhai ))/i;
  const parts = note.split(/[,،]| और | aur | and | आणि | અને | এবং | மற்றும் | మరియు | ಮತ್ತು /).flatMap((s) => s.split(qty)).map((s) => s.trim()).filter(Boolean);
  return `<div class="items">${parts.map((p) => `<span class="item"><span class="e">${emojiFor(p)}</span>${esc(p)}</span>`).join("")}</div>`;
}

// ------------------------------------------------------------ voice out (Gnani Timbre)
export async function speechBlob(text, l) {
  const res = await fetch("/api/speak", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang: l }),
  });
  if (!res.ok) {
    let detail = `Voice failed (${res.status})`;
    try { detail = (await res.json()).detail || detail; } catch { /* not json */ }
    throw new Error(detail);
  }
  return res.blob();
}
export function stopAudio() { if (state.audio) { state.audio.pause(); state.audio.onended?.(); } }
export function play(blob, btn) {
  return new Promise((resolve) => {
    stopAudio();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    state.audio = audio;
    btn && btn.classList.add("speaking");
    let finished = false;
    const done = () => {
      if (finished) return;
      finished = true;
      if (state.audio === audio) state.audio = null;
      btn && btn.classList.remove("speaking");
      URL.revokeObjectURL(url);
      resolve();
    };
    audio.onended = done;
    audio.onerror = done;
    audio.play().catch(done);
  });
}
// Speak a reply ({speech, lang}); resolves when it has finished playing
export async function say(reply, btn = null) {
  if (!reply || !reply.speech) return;
  try {
    await play(await speechBlob(reply.speech, reply.lang), btn);
  } catch (err) {
    if (!state.ttsWarned) { state.ttsWarned = true; toast(`${t("voiceFailed")} ${err.message}`); }
  }
}

// wa.me needs the number with country code; add 91 for a plain 10-digit Indian number
export function whatsappLink(phone, text) {
  const digits = (phone || "").replace(/\D/g, "");
  const num = digits.length === 10 ? "91" + digits : digits;
  return `https://wa.me/${num}?text=${encodeURIComponent(text)}`;
}
export function upiLink(upi, shop, amount, note) {
  const q = new URLSearchParams({ pa: upi, pn: shop || "Shop", cu: "INR", tn: note || "Udhaar" });
  if (amount > 0) q.set("am", (Math.round(amount * 100) / 100).toFixed(2));
  return `upi://pay?${q.toString()}`;
}

// coins fall when an account is settled
export function coins() {
  if (reducedMotion()) return;
  const box = $("confetti");
  for (let i = 0; i < 26; i++) {
    const p = document.createElement("i");
    p.className = i % 3 ? "coin" : "note";
    if (p.className === "coin") p.textContent = "₹";
    p.style.left = `${8 + Math.random() * 84}%`;
    p.style.setProperty("--dx", `${(Math.random() - 0.5) * 220}px`);
    p.style.setProperty("--rot", `${Math.random() * 720 - 360}deg`);
    p.style.animationDelay = `${Math.random() * 350}ms`;
    box.appendChild(p);
    setTimeout(() => p.remove(), 2300);
  }
}

// ------------------------------------------------------------ full-screen sheets inside the phone
const openSheets = [];
export function openSheet(el, focusEl) {
  if (!el.hidden) return;
  el.hidden = false;
  el.classList.remove("closing");
  openSheets.push(el);
  $("scrim").hidden = false;
  setTimeout(() => (focusEl || el.querySelector("button"))?.focus(), 30);
}
export function closeSheet(el) {
  if (el.hidden) return;
  el.classList.add("closing");
  const i = openSheets.indexOf(el);
  if (i >= 0) openSheets.splice(i, 1);
  if (!openSheets.length) $("scrim").hidden = true;
  setTimeout(() => { el.hidden = true; el.classList.remove("closing"); }, reducedMotion() ? 0 : 190);
}
export const topSheet = () => openSheets[openSheets.length - 1] || null;

export const ICON = {
  play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>',
  chevron: '<svg viewBox="0 0 24 24" aria-hidden="true" style="width:18px;height:18px;color:#A89E86"><path d="M9 5l7 7-7 7"/></svg>',
};
