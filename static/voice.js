// The voice screen: speak -> Gnani Prisma hears -> Bol Khata writes -> Gnani Timbre answers.
// Talk-back: if something is missing ("कितने रुपये?") the app asks and listens again by itself.
// With conversation mode on, it keeps listening after every reply until you say "बस" or stay quiet.
import { WavRecorder } from "/static/recorder.js";
import { SPEAK_FOR, getLang, locale, t } from "/static/i18n.js";
import {
  $, ICON, api, avatar, closeSheet, coins, dueWords, emojiFor, esc, hooks, itemChips, lang, openSheet,
  rupee, say, send, show, state, stopAudio, store, toast, whenText,
} from "/static/ui.js";

const v = {
  recorder: null, mode: "idle", pending: null, loop: false,
  cards: new Map(), // entry / promise id -> result card (so undo can strike it out)
};
const sheet = () => $("voiceSheet");
const talkOn = () => $("talkMode").checked;

function setMode(mode, status, hint = "") {
  v.mode = mode;
  sheet().dataset.state = mode;
  $("vsStatus").textContent = status ?? {
    idle: t("stIdle"), listening: t("stListen"), busy: t("stWork"), speaking: t("stSpeak"),
  }[mode];
  $("vsHint").textContent = hint || {
    idle: "", listening: t("stListenHint"), busy: t("stWorkHint"), speaking: t("stSpeakHint"),
  }[mode] || "";
  $("vsMic").setAttribute("aria-label", mode === "listening" ? t("micStop") : t("micSpeak"));
}

// ------------------------------------------------------------ open / close
export function openVoice({ listen = true, text = null } = {}) {
  if (sheet().hidden) {
    $("talkMode").checked = store.get("talkMode", "0") === "1";
    if (!$("convo").children.length) intro();
    openSheet(sheet(), $("vsMic"));
    setMode("idle");
  }
  if (text) sendText(text);
  else if (listen) startListening();
}
export function closeVoice() {
  v.loop = false;
  v.pending = null;
  if (v.mode === "listening") cancelListening();
  stopAudio();
  closeSheet(sheet());
}

function intro() {
  const tries = t("tries");
  $("convo").innerHTML = `
    <div class="vs-intro" id="vsIntro">
      <div class="orb-art">${'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/></svg>'}</div>
      <h3>${esc(t("vsIntroTitle"))}</h3>
      <p>${esc(t("vsIntroText"))}</p>
      <ul>${(Array.isArray(tries) ? tries : []).slice(0, 4).map((s) => `<li><button type="button">${esc(s)}</button></li>`).join("")}</ul>
    </div>`;
  $("convo").querySelectorAll(".vs-intro button").forEach((b) => b.addEventListener("click", () => sendText(b.textContent)));
}
function clearIntro() { $("vsIntro")?.remove(); }

function scrollDown() { const c = $("convo"); requestAnimationFrame(() => (c.scrollTop = c.scrollHeight)); }
function addYou(text, typed) {
  clearIntro();
  const el = document.createElement("div");
  el.className = "msg you";
  el.innerHTML = `<small>${esc(typed ? t("youTyped") : t("youSaid"))}</small>${esc(text)}`;
  $("convo").appendChild(el);
  scrollDown();
}
function addApp(html) {
  clearIntro();
  const el = document.createElement("div");
  el.className = "msg app";
  el.innerHTML = html;
  $("convo").appendChild(el);
  scrollDown();
  return el;
}

// ------------------------------------------------------------ listening
export async function startListening() {
  if (v.mode === "busy" || v.mode === "listening") return;
  if (!navigator.mediaDevices?.getUserMedia) { toast(t("micUnsupported")); return; }
  stopAudio();
  v.recorder = new WavRecorder();
  try {
    await v.recorder.start({
      onLevel: (lvl) => $("vsMic").style.setProperty("--level", lvl.toFixed(3)),
      onSilence: () => stopListening(),
      onNoSpeech: () => endConversation(),
      noSpeechMs: v.loop || v.pending ? 8000 : 15000, // nobody spoke: stop quietly
    });
  } catch (err) {
    toast(`${t("micDenied")} (${err.message})`);
    setMode("idle");
    return;
  }
  setMode("listening", v.pending ? t("vsAnswer") : t("stListen"));
}
async function cancelListening() {
  if (v.mode !== "listening") return;
  try { await v.recorder.stop(); } catch { /* ignore */ }
  $("vsMic").style.setProperty("--level", 0);
}
async function endConversation() {
  await cancelListening();
  v.loop = false;
  v.pending = null;
  setMode("idle", t("vsEnded"), t("vsTapHint"));
}
async function stopListening() {
  if (v.mode !== "listening") return;
  const rec = await v.recorder.stop();
  $("vsMic").style.setProperty("--level", 0);
  if (!rec || rec.seconds < 0.6) { setMode("idle"); toast(t("tooShort")); return; }
  const form = new FormData();
  form.append("audio", rec.blob, "speech.wav");
  form.append("language", SPEAK_FOR[getLang()] || "hi-IN");
  form.append("reply_lang", lang());
  if (v.pending) form.append("pending", JSON.stringify(v.pending));
  await run(() => api("/api/voice", { method: "POST", body: form }), false);
}
export async function sendText(text) {
  text = (text || "").trim();
  if (!text || v.mode === "busy") return;
  if (v.mode === "listening") await cancelListening();
  addYou(text, true);
  await run(() => send("/api/text", "POST", { text, reply_lang: lang(), pending: v.pending }), true);
}

async function run(call, typed) {
  setMode("busy");
  let res;
  try {
    res = await call();
  } catch (err) {
    addApp(`<div class="bubble warn"><p>${esc(err.message)}</p></div>`);
    setMode("idle");
    return;
  }
  if (!typed) addYou(res.said, false);
  const card = showResult(res);
  hooks.render?.(res.ledger, res);
  v.pending = res.pending || null;
  setMode("speaking");
  await say(res.reply, card?.querySelector(".play"));
  if (sheet().hidden) return;
  if (res.end) { v.loop = false; setMode("idle", t("vsEnded"), t("vsTapHint")); return; }
  if (v.pending) { startListening(); return; }        // the app asked a question: listen for the answer
  if (talkOn()) { v.loop = true; startListening(); return; } // conversation mode
  v.loop = false;
  setMode("idle");
}

// ------------------------------------------------------------ result cards
const custOf = (res, id) => (res.ledger.customers || []).find((c) => c.id === id);
function balanceLine(c) {
  if (!c) return "";
  const b = c.balance;
  const txt = b > 0.5 ? rupee(b) : b < -0.5 ? `${rupee(b)} ${t("advance")}` : `${t("settled")} 🎉`;
  return `<span class="bal">${esc(t("totalDue"))}<b class="${b > 0.5 ? "due" : b < -0.5 ? "adv" : ""}">${esc(txt)}</b></span>`;
}
function warnBars(res) {
  return (res.warnings || []).map((w) => w.kind === "limit"
    ? `<div class="warnbar limit">⚠️ <span>${esc(t("warnLimit", { name: show(w.customer), limit: rupee(w.limit), bal: rupee(w.balance) }))}</span></div>`
    : `<div class="warnbar kept">🤝 <span>${esc(t("warnKept", { name: show(w.customer) }))}</span></div>`).join("");
}
const foot = (res, extra = "") => `
  <div class="rc-foot">${extra}<button class="play" type="button" aria-label="${esc(t("playAria"))}">${ICON.play}</button></div>
  <p class="rc-say">${esc(res.reply.text)}</p>`;
function wire(el, res) {
  el.querySelector(".play")?.addEventListener("click", (ev) => { stopAudio(); say(res.reply, ev.currentTarget); });
  el.querySelectorAll("[data-cust]").forEach((b) => b.addEventListener("click", () => hooks.openCustomer?.(Number(b.dataset.cust))));
}

function showResult(res) {
  const u = res.understood || {};
  if (res.removed) markUndone(res.removed);
  let html;
  if (res.pending) {
    html = `<div class="bubble ask"><p>${esc(res.reply.text)}</p><small>${esc(t("vsAskHint"))}</small></div>`;
  } else if (res.entries?.length || (res.entry && res.promise)) {
    html = multiCard(res);
  } else if (res.entry) {
    html = entryCard(res);
  } else if (res.promise) {
    html = promiseCard(res);
  } else if (u.intent === "due_today" && res.due) {
    html = dueCard(res);
  } else {
    html = `<div class="bubble"><p>${esc(res.reply.text)}</p><div class="rc-foot" style="background:none;border:0;padding:8px 0 0"><span class="bal"></span><button class="play" type="button" aria-label="${esc(t("playAria"))}">${ICON.play}</button></div></div>`;
  }
  const el = addApp(html);
  wire(el, res);
  const card = el.querySelector(".rc") || el;
  for (const e of [res.entry, ...(res.entries || [])].filter(Boolean)) v.cards.set(`e${e.id}`, card);
  if (res.promise) v.cards.set(`p${res.promise.id}`, card);
  const settled = [res.entry, ...(res.entries || [])].filter(Boolean)
    .some((e) => e.kind === "payment" && Math.abs(custOf(res, e.customer_id)?.balance ?? 1) <= 0.5);
  if (settled) coins();
  return el;
}

function entryCard(res) {
  const e = res.entry;
  const c = custOf(res, e.customer_id);
  const top = e.kind === "credit" ? t("rcCredit") : t("rcPayment");
  return `
    <div class="rc">
      <div class="rc-top ${e.kind}"><span>${esc(top)}</span><time>${esc(whenText(e.created_at))}</time></div>
      <div class="rc-body">
        <button type="button" class="rc-who" data-cust="${e.customer_id}">${avatar(e.customer || c?.name, { trust: c?.trust?.label })}
          <b>${esc(show(e.customer || c?.name))}</b>${res.understood?.new_customer ? `<span class="badge">${esc(t("newBadge"))}</span>` : ""}</button>
        <div class="rc-amt ${e.kind}">${e.kind === "credit" ? "+" : "−"}${rupee(e.amount)}</div>
        ${e.kind === "credit" ? itemChips(e.note) : ""}
      </div>
      ${warnBars(res)}
      ${foot(res, balanceLine(c))}
    </div>`;
}

function multiCard(res) {
  const entries = res.entries?.length ? res.entries : [res.entry].filter(Boolean);
  const lines = entries.map((e) => `
    <div class="rc-line"><span class="k ${e.kind}">${esc(e.kind === "credit" ? t("kCredit") : t("kPayment"))}</span>
      <span class="w">${esc(show(e.customer))}${e.note ? ` · ${emojiFor(e.note)} ${esc(e.note)}` : ""}</span>
      <span class="a" style="color:var(--${e.kind === "credit" ? "due" : "paid"})">${e.kind === "credit" ? "+" : "−"}${rupee(e.amount)}</span></div>`);
  if (res.promise) {
    const p = res.promise;
    lines.push(`<div class="rc-line"><span class="k promise">${esc(t("kPromise"))}</span>
      <span class="w">${esc(show(p.customer))} · ${esc(dueWords({ days: -dayDiffIso(p.due_date), due_date: p.due_date }))}</span>
      <span class="a" style="color:var(--brand)">${p.amount ? rupee(p.amount) : esc(t("promiseAll"))}</span></div>`);
  }
  const ids = [...new Set(entries.map((e) => e.customer_id).concat(res.promise ? [res.promise.customer_id] : []))];
  const bals = ids.map((id) => custOf(res, id)).filter(Boolean);
  const balHtml = bals.length === 1 ? balanceLine(bals[0])
    : `<span class="bal">${bals.map((c) => `${esc(show(c.name))}: <b class="${c.balance > 0.5 ? "due" : "adv"}" style="display:inline">${rupee(c.balance)}</b>`).join(" · ")}</span>`;
  return `
    <div class="rc">
      <div class="rc-top multi"><span>${esc(t("rcMulti", { n: lines.length }))}</span><time>${esc(whenText(entries[0]?.created_at || new Date().toISOString()))}</time></div>
      <div class="rc-body">${lines.join("")}</div>
      ${warnBars(res)}
      ${foot(res, balHtml)}
    </div>`;
}

function dayDiffIso(iso) {
  const a = new Date(iso + "T00:00:00"); const b = new Date(); b.setHours(0, 0, 0, 0);
  return Math.round((b - a) / 86400000);
}
function promiseCard(res) {
  const p = res.promise;
  const c = custOf(res, p.customer_id);
  const d = new Date(p.due_date + "T00:00:00");
  return `
    <div class="rc">
      <div class="rc-top promise"><span>🤝 ${esc(t("rcPromise"))}</span><time>${esc(whenText(p.created_at))}</time></div>
      <div class="rc-body">
        <button type="button" class="rc-who" data-cust="${p.customer_id}">${avatar(p.customer || c?.name, { trust: c?.trust?.label })}<b>${esc(show(p.customer || c?.name))}</b></button>
        <div class="promise-when">
          <div class="cal"><small>${esc(d.toLocaleDateString(locale(), { month: "short" }))}</small><b>${d.getDate()}</b></div>
          <div><b class="num" style="font-size:1.4rem;color:var(--brand)">${p.amount ? rupee(p.amount) : esc(t("promiseAll"))}</b><br>
            <small>${esc(dueWords({ days: -dayDiffIso(p.due_date), due_date: p.due_date }))}</small></div>
        </div>
      </div>
      ${foot(res, balanceLine(c))}
    </div>`;
}

function dueCard(res) {
  const people = [...res.due.overdue, ...res.due.today];
  const lines = people.map((p) => `
    <div class="rc-line"><span class="k ${p.days < 0 ? "credit" : "promise"}">${esc(dueWords(p))}</span>
      <button type="button" class="w" data-cust="${p.customer_id}" style="border:0;background:none;text-align:left;padding:0">${esc(show(p.name))}</button>
      <span class="a">${rupee(p.left)}</span></div>`).join("");
  return `
    <div class="rc">
      <div class="rc-top info"><span>🗓️ ${esc(t("dueTitle"))}</span></div>
      ${lines ? `<div class="rc-body">${lines}</div>` : ""}
      ${foot(res, '<span class="bal"></span>')}
    </div>`;
}

export function markUndone(removed) {
  if (!removed) return;
  const ids = removed.kind === "promise" ? [`p${removed.id}`] : (removed.batch_entries?.length ? removed.batch_entries : [removed]).map((e) => `e${e.id}`);
  ids.forEach((id) => v.cards.get(id)?.classList.add("undone"));
}

async function undo() {
  if (v.mode === "busy") return;
  if (v.mode === "listening") await cancelListening();
  try {
    const res = await send(`/api/undo?lang=${lang()}`, "POST");
    markUndone(res.removed);
    const el = addApp(`<div class="bubble"><p>↩️ ${esc(res.reply.text)}</p></div>`);
    hooks.render?.(res.ledger);
    setMode("speaking");
    await say(res.reply);
    setMode("idle");
    return el;
  } catch (err) { toast(err.message); setMode("idle"); }
}

// ------------------------------------------------------------ wiring
export function initVoice() {
  $("vsClose").addEventListener("click", closeVoice);
  $("vsMic").addEventListener("click", () => {
    if (v.mode === "listening") stopListening();
    else if (v.mode === "speaking") { stopAudio(); startListening(); }
    else if (v.mode === "idle") startListening();
  });
  $("vsUndo").addEventListener("click", undo);
  $("vsKeyboard").addEventListener("click", () => {
    $("vsType").hidden = !$("vsType").hidden;
    if (!$("vsType").hidden) $("vsInput").focus();
  });
  $("vsType").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("vsInput").value;
    $("vsInput").value = "";
    sendText(text);
  });
  $("talkMode").addEventListener("change", () => {
    store.set("talkMode", $("talkMode").checked ? "1" : "0");
    toast($("talkMode").checked ? t("talkModeOn") : t("talkModeOff"), 3000);
  });
  document.addEventListener("keydown", (e) => {
    if (sheet().hidden) return;
    if (e.key === "Escape") closeVoice();
    if (e.code === "Space" && !e.target.closest("input, textarea, button, select")) {
      e.preventDefault();
      $("vsMic").click();
    }
  });
}
export const voiceState = v;
