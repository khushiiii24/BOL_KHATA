// The khata tab (customer list) and one customer's page: trust score, limit, promise,
// WhatsApp reminder, voice note, UPI QR to collect, quick entry and the full timeline.
import { locale, t } from "/static/i18n.js";
import {
  $, ICON, TRUST_KEYS, ageWords, api, avatar, closeSheet, coins, dayDiff, dueWords, esc, hooks, itemChips,
  lang, openSheet, play, rupee, say, send, show, speechBlob, state, toast, trustBadge, upiLink, whatsappLink, whenText,
} from "/static/ui.js";

// ------------------------------------------------------------ list
const FILTERS = {
  all: () => true,
  owing: (c) => c.balance > 0.5,
  promise: (c) => !!c.promise,
  old: (c) => c.balance > 0.5 && c.due_since && dayDiff(c.due_since) > 30,
  limit: (c) => c.over_limit,
  risk: (c) => c.trust?.label === "risk",
  settled: (c) => Math.abs(c.balance) <= 0.5,
};
const FILTER_KEYS = { all: "fAll", owing: "fOwing", promise: "fPromise", old: "fOld", limit: "fLimit", risk: "fRisk", settled: "fSettled" };
const SORTERS = {
  recent: (a, b) => (b.last_at || "").localeCompare(a.last_at || ""),
  highest: (a, b) => b.balance - a.balance || SORTERS.recent(a, b),
  oldest: (a, b) => (a.due_since ? 0 : 1) - (b.due_since ? 0 : 1) || (a.due_since || "").localeCompare(b.due_since || "") || SORTERS.recent(a, b),
  trust: (a, b) => (a.trust?.score ?? 101) - (b.trust?.score ?? 101) || b.balance - a.balance,
  name: (a, b) => show(a.name).localeCompare(show(b.name), locale()),
};

function rowSub(c) {
  if (c.promise) {
    const late = c.promise.days < 0;
    return `<span class="${late ? "late" : c.promise.days <= 1 ? "soon" : ""}">🤝 ${esc(t("promiseShort", { when: dueWords(c.promise), amt: rupee(c.promise.left) }))}</span>`;
  }
  if (c.balance > 0.5) {
    const days = c.due_since ? dayDiff(c.due_since) : 0;
    return `<span class="${days > 30 ? "late" : ""}">${esc(ageWords(c))}</span>`;
  }
  return esc(c.last_at ? whenText(c.last_at) : t("noEntry"));
}
function amountHtml(bal) {
  if (bal > 0.5) return `<span class="amt due">${rupee(bal)}</span>`;
  if (bal < -0.5) return `<span class="amt adv">${rupee(bal)}<small style="display:block;font-size:.7rem;font-weight:700">${esc(t("advance"))}</small></span>`;
  return `<span class="amt zero">${esc(t("settled"))}</span>`;
}
export function customerRow(c) {
  const limit = c.over_limit ? `<span class="tbadge limit">${esc(t("fLimit"))}</span>` : "";
  return `
    <button type="button" data-cust="${c.id}">
      ${avatar(c.name, { trust: c.trust?.label })}
      <span class="main" style="min-width:0"><span class="name" style="display:block">${esc(show(c.name))}${c.trust && c.trust.label !== "new" ? trustBadge(c.trust, false) : ""}${limit}</span>
        <span class="sub" style="display:block">${rowSub(c)}</span></span>
      <span class="right" style="display:flex;align-items:center;gap:6px">${amountHtml(c.balance)}${ICON.chevron}</span>
    </button>`;
}

export function renderKhata(freshId = null) {
  const all = state.ledger?.customers || [];
  $("filters").innerHTML = Object.keys(FILTERS).map((f) => {
    const n = all.filter(FILTERS[f]).length;
    if (f !== "all" && f !== state.filter && n === 0) return "";
    return `<button type="button" data-f="${f}" aria-pressed="${f === state.filter}">${esc(t(FILTER_KEYS[f]))}<i>${n}</i></button>`;
  }).join("");
  const q = state.search.trim().toLowerCase();
  const list = all.filter(FILTERS[state.filter] || FILTERS.all)
    .filter((c) => !q || c.name.toLowerCase().includes(q) || show(c.name).toLowerCase().includes(q))
    .sort(SORTERS[state.sort] || SORTERS.recent);
  $("custList").innerHTML = list.map((c) => `<li class="${c.id === freshId ? "fresh" : ""}">${customerRow(c)}</li>`).join("");
  $("khataEmpty").hidden = all.length > 0;
  $("noMatch").hidden = !(all.length && !list.length);
}

// ------------------------------------------------------------ one customer
let current = null; // { customer, entries }
let kind = "credit";

export async function openCustomer(id) {
  let data;
  try { data = await api(`/api/customers/${id}`); } catch (err) { toast(err.message); return; }
  current = data;
  state.openCustomer = id;
  kind = "credit";
  renderCustomer();
  openSheet($("custSheet"), $("custBack"));
  $("custBody").scrollTop = 0;
}
export function closeCustomer() {
  state.openCustomer = null;
  closeSheet($("custSheet"));
}
export async function refreshCustomer() {
  if (!state.openCustomer || $("custSheet").hidden) return;
  try { current = await api(`/api/customers/${state.openCustomer}`); renderCustomer(); } catch { closeCustomer(); }
}

function trustCard(c) {
  const tr = c.trust || { label: "new" };
  const color = { good: "var(--good)", ok: "var(--ok)", risk: "var(--risk)", new: "#9A917C" }[tr.label];
  const lines = [];
  if (tr.avg_days != null) lines.push(t("trustAvg", { n: tr.avg_days }));
  if (tr.kept || tr.missed) lines.push(t("trustPromises", { k: tr.kept, m: tr.missed }));
  if (c.balance > 0.5 && tr.oldest_days) lines.push(t("trustOldest", { n: tr.oldest_days }));
  if (tr.label === "new") lines.push(t("trustNewText"));
  return `
    <section class="card trust-card">
      <span class="ring" style="--p:${tr.score ?? 0};--c:${color}" data-label="${tr.score ?? "—"}"></span>
      <div style="min-width:0"><h3>${esc(t("trustTitle"))} ${trustBadge(tr, false)}</h3>
        <ul>${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul></div>
    </section>`;
}

function renderCustomer() {
  const { customer: c, entries } = current;
  $("custTitle").textContent = show(c.name);
  const bal = c.balance;
  const balCls = bal > 0.5 ? "due" : bal < -0.5 ? "adv" : "zero";
  const balTxt = bal > 0.5 ? rupee(bal) : bal < -0.5 ? `${rupee(bal)} ${t("advance")}` : t("settled");
  const days = c.due_since ? dayDiff(c.due_since) : 0;
  const p = c.promise;
  const lim = c.credit_limit;
  const pct = lim ? Math.min(100, Math.round((Math.max(bal, 0) / lim) * 100)) : 0;
  const today = new Date().toISOString().slice(0, 10);

  $("custBody").innerHTML = `
    <form class="card inline-form" id="renameForm" hidden>
      <input id="renameInput" value="${esc(c.name)}" maxlength="60" aria-label="${esc(t("rename"))}">
      <button class="btn primary" type="submit">${esc(t("save"))}</button>
    </form>

    <section class="cust-hero">
      ${avatar(c.name, { big: true, trust: c.trust?.label })}
      <div class="main">
        <small>${esc(t("totalDue"))}</small>
        <div class="big-amt ${balCls}">${esc(balTxt)}</div>
        <span class="age ${days > 30 ? "late" : ""}">${esc(ageWords(c))}</span>
      </div>
    </section>

    ${trustCard(c)}

    <div class="action-grid">
      <button type="button" class="wa" id="cWa"><span class="ic">💬</span>${esc(t("waRemind"))}<small>${esc(c.phone ? c.phone : t("waNoPhone"))}</small></button>
      <button type="button" class="upi" id="cUpi"><span class="ic">📲</span>${esc(t("upiCollect"))}<small>${esc(t("upiCollectSub"))}</small></button>
      <button type="button" class="vn" id="cVoice"><span class="ic">🔊</span>${esc(t("remind"))}<small>${esc(t("remindSub"))}</small></button>
      ${c.phone ? `<a class="ph" href="tel:${esc(c.phone)}"><span class="ic">📞</span>${esc(t("call"))}<small>${esc(c.phone)}</small></a>`
                : `<button type="button" class="ph" id="cPhoneQuick"><span class="ic">📞</span>${esc(t("phoneLabel"))}<small>${esc(t("phoneAdd"))}</small></button>`}
    </div>
    <div class="card" id="voiceNote" hidden></div>

    <section class="card">
      <div class="set-row">
        <span class="ic">🤝</span>
        <div class="txt"><b>${esc(t("promiseTitle"))}</b>
          <small class="${p && p.days < 0 ? "late" : ""}">${p ? esc(t("promiseShort", { when: dueWords(p), amt: rupee(p.left) })) : esc(t("promiseNone"))}</small></div>
        ${p ? `<button type="button" class="chipbtn danger" id="pDel">${esc(t("remove"))}</button>` : ""}
        <button type="button" class="chipbtn" id="pEdit">${esc(p ? t("change") : t("add"))}</button>
      </div>
      <form class="inline-form" id="pForm" hidden>
        <input type="date" id="pDate" min="${today}" value="${p ? p.due_date : ""}" required aria-label="${esc(t("promiseDate"))}">
        <input type="number" id="pAmt" min="1" step="1" inputmode="numeric" placeholder="${esc(t("promiseAmountPh"))}" value="${p && p.amount ? Math.round(p.amount) : ""}">
        <button class="btn primary" type="submit">${esc(t("save"))}</button>
      </form>

      <div class="set-row">
        <span class="ic">🚧</span>
        <div class="txt"><b>${esc(t("limitTitle"))}</b>
          <small class="${c.over_limit ? "over" : ""}">${lim ? esc(t("limitUsed", { limit: rupee(lim), pct })) : esc(t("limitNone"))}</small>
          ${lim ? `<div class="meter"><i class="${c.over_limit ? "over" : ""}" style="width:${pct}%"></i></div>` : ""}</div>
        <button type="button" class="chipbtn" id="lEdit">${esc(lim ? t("change") : t("add"))}</button>
      </div>
      <form class="inline-form" id="lForm" hidden>
        <input type="number" id="lAmt" min="1" step="1" inputmode="numeric" placeholder="${esc(t("limitPh"))}" value="${lim ? Math.round(lim) : ""}">
        <button class="btn primary" type="submit">${esc(t("save"))}</button>
        ${lim ? `<button class="btn danger" type="button" id="lDel">${esc(t("remove"))}</button>` : ""}
      </form>

      <div class="set-row">
        <span class="ic">📞</span>
        <div class="txt"><b>${esc(t("phoneLabel"))}</b><small>${esc(c.phone || t("phoneAdd"))}</small></div>
        <button type="button" class="chipbtn" id="phEdit">${esc(c.phone ? t("change") : t("add"))}</button>
      </div>
      <form class="inline-form" id="phForm" hidden>
        <input type="tel" id="phInput" inputmode="tel" maxlength="16" placeholder="${esc(t("phonePh"))}" value="${esc(c.phone || "")}">
        <button class="btn primary" type="submit">${esc(t("save"))}</button>
      </form>
    </section>

    <section class="card">
      <header class="card-head"><h2>${esc(t("quickTitle"))}</h2></header>
      <form class="quick" id="quickForm" autocomplete="off">
        <div class="seg" role="group">
          <button type="button" class="credit" data-kind="credit" aria-pressed="${kind === "credit"}">${esc(t("kCredit"))}</button>
          <button type="button" class="payment" data-kind="payment" aria-pressed="${kind === "payment"}">${esc(t("kPayment"))}</button>
        </div>
        <div class="two">
          <input type="number" id="qAmt" min="1" step="1" inputmode="numeric" placeholder="${esc(t("amountPh"))}" aria-label="${esc(t("amountPh"))}">
          <input id="qNote" maxlength="80" placeholder="${esc(t("notePh"))}" aria-label="${esc(t("notePh"))}">
        </div>
        <button class="btn primary" type="submit" id="qSave">${esc(kind === "credit" ? t("addCredit") : t("addPayment"))}</button>
      </form>
    </section>

    <section class="card">
      <header class="card-head"><h2>${esc(t("timeline"))}</h2><span class="note" style="margin:0">${entries.length}</span></header>
      <ul class="timeline">${entries.map(timelineRow).join("") || `<li><span></span><small>${esc(t("noEntry"))}</small></li>`}</ul>
    </section>`;
  wireCustomer();
}

function timelineRow(e) {
  const sign = e.kind === "credit" ? "+" : "−";
  return `
    <li>
      <span class="dot ${e.kind}">${e.kind === "credit" ? "🛍️" : "💵"}</span>
      <div class="t-main"><b>${esc(e.kind === "credit" ? t("kCredit") : t("kPayment"))}</b>
        <small>${esc(whenText(e.created_at))}</small>
        ${e.kind === "credit" && e.note ? itemChips(e.note) : ""}
        ${e.said ? `<span class="t-said">🎙️ “${esc(e.said)}”</span>` : ""}</div>
      <div class="t-right"><b class="${e.kind}">${sign}${rupee(e.amount)}</b>
        <small>${esc(t("balAfter", { amt: rupee(e.balance_after) }))}</small>
        <button type="button" class="del" data-del="${e.id}">${esc(t("deleteEntry"))}</button></div>
    </li>`;
}

async function afterChange(res, message) {
  if (res.ledger) hooks.render?.(res.ledger);
  await refreshCustomer();
  if (message) toast(message, 3000);
}

function wireCustomer() {
  const c = current.customer;
  const toggle = (id) => { const f = $(id); f.hidden = !f.hidden; if (!f.hidden) f.querySelector("input")?.focus(); };
  $("pEdit").onclick = () => toggle("pForm");
  $("lEdit").onclick = () => toggle("lForm");
  $("phEdit").onclick = () => toggle("phForm");
  if ($("cPhoneQuick")) $("cPhoneQuick").onclick = () => { toggle("phForm"); $("phForm").scrollIntoView({ block: "center" }); };

  $("pForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await send(`/api/customers/${c.id}/promise`, "POST",
        { due_date: $("pDate").value, amount: Number($("pAmt").value) || null, reply_lang: lang() });
      await afterChange(res, res.reply.text);
    } catch (err) { toast(err.message); }
  };
  if ($("pDel")) $("pDel").onclick = async () => {
    try { await afterChange(await api(`/api/promises/${c.promise.id}`, { method: "DELETE" }), t("saved")); } catch (err) { toast(err.message); }
  };
  $("lForm").onsubmit = async (e) => {
    e.preventDefault();
    try { await afterChange(await send(`/api/customers/${c.id}`, "PATCH", { credit_limit: Number($("lAmt").value) || null }), t("saved")); }
    catch (err) { toast(err.message); }
  };
  if ($("lDel")) $("lDel").onclick = async () => {
    try { await afterChange(await send(`/api/customers/${c.id}`, "PATCH", { credit_limit: null }), t("saved")); } catch (err) { toast(err.message); }
  };
  $("phForm").onsubmit = async (e) => {
    e.preventDefault();
    try { await afterChange(await send(`/api/customers/${c.id}`, "PATCH", { phone: $("phInput").value }), t("saved")); }
    catch (err) { toast(err.message); }
  };
  $("renameForm").onsubmit = async (e) => {
    e.preventDefault();
    const name = $("renameInput").value.trim();
    if (!name) return;
    try { await afterChange(await send(`/api/customers/${c.id}`, "PATCH", { name }), t("saved")); } catch (err) { toast(err.message); }
  };

  $("custBody").querySelectorAll(".seg button").forEach((b) => (b.onclick = () => {
    kind = b.dataset.kind;
    $("custBody").querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    $("qSave").textContent = kind === "credit" ? t("addCredit") : t("addPayment");
  }));
  $("quickForm").onsubmit = async (e) => {
    e.preventDefault();
    const amount = Number($("qAmt").value);
    if (!(amount > 0)) { toast(t("amountMissing")); return; }
    await addEntry(c.id, kind, amount, $("qNote").value);
  };
  $("custBody").querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    try { await afterChange(await api(`/api/entries/${b.dataset.del}`, { method: "DELETE" }), t("entryDeleted")); } catch (err) { toast(err.message); }
  }));

  $("cWa").onclick = () => remindWhatsApp(c);
  $("cVoice").onclick = () => voiceNote(c);
  $("cUpi").onclick = () => openQR(c);
}

export async function addEntry(customerId, k, amount, note = "") {
  try {
    const res = await send("/api/entry", "POST", { customer_id: customerId, kind: k, amount, note, reply_lang: lang() });
    hooks.render?.(res.ledger);
    await refreshCustomer();
    toast(res.reply.text, 4000);
    const c = res.ledger.customers.find((x) => x.id === customerId);
    if (k === "payment" && c && Math.abs(c.balance) <= 0.5) coins();
    say(res.reply);
    return res;
  } catch (err) { toast(err.message); return null; }
}

// ------------------------------------------------------------ reminders
async function remindWhatsApp(c) {
  try {
    const r = await api(`/api/reminder/${c.id}?lang=${lang()}`);
    window.open(whatsappLink(c.phone, r.text), "_blank", "noopener");
  } catch (err) { toast(err.message); }
}
async function voiceNote(c) {
  const box = $("voiceNote");
  box.hidden = false;
  box.innerHTML = `<p class="note" style="margin:0">${esc(t("stWork"))}</p>`;
  try {
    const r = await api(`/api/reminder/${c.id}?lang=${lang()}`);
    const blob = await speechBlob(r.speech, r.lang);
    const ext = blob.type.includes("wav") ? "wav" : "mp3";
    const url = URL.createObjectURL(blob);
    box.innerHTML = `
      <p style="margin:0 0 10px;color:var(--ink-2)">${esc(r.text)}</p>
      <div class="modal-actions" style="margin:0">
        <button type="button" class="btn" id="vnPlay">🔊 ${esc(t("playAria"))}</button>
        <a class="btn primary" href="${url}" download="reminder-${esc(c.name)}.${ext}">⬇ ${esc(t("download"))}</a>
      </div>`;
    $("vnPlay").onclick = (ev) => play(blob, ev.currentTarget);
    play(blob, $("vnPlay"));
  } catch (err) { box.innerHTML = `<p class="note">${esc(t("noteFailed"))} ${esc(err.message)}</p>`; }
}

// ------------------------------------------------------------ UPI QR: the customer scans and pays
function qrSvg(text) {
  if (!window.qrcode) return "";
  const qr = window.qrcode(0, "M");
  qr.addData(text);
  qr.make();
  return qr.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
}
function qrPng(text, caption) {
  const qr = window.qrcode(0, "M");
  qr.addData(text);
  qr.make();
  const n = qr.getModuleCount(), cell = 10, pad = 30, size = n * cell + pad * 2;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size + 70;
  const g = canvas.getContext("2d");
  g.fillStyle = "#fff";
  g.fillRect(0, 0, canvas.width, canvas.height);
  g.fillStyle = "#111";
  for (let r = 0; r < n; r++) for (let col = 0; col < n; col++) if (qr.isDark(r, col)) g.fillRect(pad + col * cell, pad + r * cell, cell, cell);
  g.fillStyle = "#8E1A22";
  g.font = "bold 26px 'Baloo 2', sans-serif";
  g.textAlign = "center";
  g.fillText(caption, size / 2, size + 40);
  return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
}

export function openQR(c, amount = null) {
  const prof = state.profile || {};
  const due = amount ?? (c.promise ? c.promise.left : Math.max(c.balance, 0));
  const body = $("qrBody");
  if (!prof.upi_id) {
    body.innerHTML = `
      <p>${esc(t("upiNeedId"))}</p>
      <form class="form" id="qrUpiForm" autocomplete="off">
        <label><span>${esc(t("upiIdLabel"))}</span><input id="qrUpiId" required maxlength="130" inputmode="email" placeholder="${esc(t("upiIdPh"))}"></label>
        <div class="modal-actions"><button type="button" class="btn" data-close>${esc(t("cancel"))}</button>
          <button type="submit" class="btn primary">${esc(t("save"))}</button></div>
      </form>`;
    $("qrUpiForm").onsubmit = async (e) => {
      e.preventDefault();
      try {
        state.profile = await send("/api/profile", "PATCH", { upi_id: $("qrUpiId").value });
        hooks.renderProfile?.();
        openQR(c, amount);
      } catch (err) { toast(err.message); }
    };
  } else {
    body.innerHTML = `
      <p class="qr-meta" style="margin-top:4px">${esc(show(c.name))} → ${esc(prof.shop_name || "")}</p>
      <label class="qr-amt"><span>₹</span><input type="number" id="qrAmt" min="1" step="1" inputmode="numeric" value="${Math.round(due) || ""}" aria-label="${esc(t("upiAmount"))}"></label>
      <div class="qr-box" id="qrBox"></div>
      <p class="qr-meta">${esc(t("upiScan"))}<br><b>${esc(prof.upi_id)}</b></p>
      <div class="qr-actions">
        <a class="btn" id="qrOpen" href="#">📲 ${esc(t("upiOpen"))}</a>
        <button type="button" class="btn" id="qrShare">📤 ${esc(t("upiShare"))}</button>
        <button type="button" class="btn green wide" id="qrGot">✓ ${esc(t("upiReceived"))}</button>
        <button type="button" class="btn wide" data-close>${esc(t("closeAria"))}</button>
      </div>`;
    const draw = () => {
      const amt = Number($("qrAmt").value) || 0;
      const link = upiLink(prof.upi_id, prof.shop_name, amt, `${t("brand")} - ${show(c.name)}`);
      $("qrBox").innerHTML = qrSvg(link);
      $("qrOpen").href = link;
      $("qrGot").disabled = !(amt > 0);
      return { amt, link };
    };
    draw();
    $("qrAmt").oninput = draw;
    $("qrShare").onclick = async () => {
      const { amt, link } = draw();
      const blob = await qrPng(link, `${prof.shop_name || ""}  ${amt > 0 ? rupee(amt) : ""}`);
      const file = new File([blob], `upi-${c.name}.png`, { type: "image/png" });
      if (navigator.canShare?.({ files: [file] })) {
        try { await navigator.share({ files: [file], text: `${t("upiScan")} ${amt > 0 ? rupee(amt) : ""}` }); } catch { /* cancelled */ }
      } else {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = file.name;
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      }
    };
    $("qrGot").onclick = async () => {
      const { amt } = draw();
      if (!(amt > 0)) return;
      $("qrDialog").close();
      await addEntry(c.id, "payment", amt, "UPI");
    };
  }
  if (!$("qrDialog").open) $("qrDialog").showModal();
}

export function initKhata() {
  $("filters").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-f]");
    if (!b) return;
    state.filter = b.dataset.f;
    renderKhata();
  });
  $("search").addEventListener("input", (e) => { state.search = e.target.value; renderKhata(); });
  $("sort").addEventListener("change", (e) => { state.sort = e.target.value; renderKhata(); });
  $("custList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-cust]");
    if (b) openCustomer(Number(b.dataset.cust));
  });
  $("custBack").addEventListener("click", closeCustomer);
  $("custRename").addEventListener("click", () => {
    const f = $("renameForm");
    if (!f) return;
    f.hidden = !f.hidden;
    if (!f.hidden) $("renameInput").select();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("custSheet").hidden && $("voiceSheet").hidden && !document.querySelector("dialog[open]")) closeCustomer();
  });
}
export { TRUST_KEYS };
