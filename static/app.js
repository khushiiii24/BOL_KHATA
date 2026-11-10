// Bol Khata: the main page. Home tab, bottom tabs, language, start-up.
import { LANG_EN, LANG_NAMES, getLang, setLang, t } from "/static/i18n.js";
import {
  $, APP_VERSION, api, avatar, dueWords, emojiFor, esc, hooks, lang, reducedMotion, rupee, show, state, store,
  toast, topSheet, whatsappLink, whenText,
} from "/static/ui.js";
import { closeVoice, initVoice, openVoice } from "/static/voice.js";
import { closeCustomer, initKhata, openCustomer, openQR, refreshCustomer, renderKhata } from "/static/khata.js";
import { hearSummary, initHisaab, loadSample, openShopDialog, renderHisaab, renderMore } from "/static/hisaab.js";

// ------------------------------------------------------------ tabs
const TABS = ["home", "khata", "hisaab", "more"];
function go(tab) {
  state.tab = tab;
  TABS.forEach((name) => {
    $(`view-${name}`).hidden = name !== tab;
    $(`tab-${name}`).toggleAttribute("aria-current", name === tab);
    if (name === tab) $(`tab-${name}`).setAttribute("aria-current", "page");
  });
  $("views").scrollTop = 0;
  if (tab === "khata") renderKhata();
}

// ------------------------------------------------------------ text in the chosen language
function applyI18n() {
  document.documentElement.lang = lang();
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  document.querySelectorAll("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
  $("langName").textContent = LANG_NAMES[lang()];
  const tries = t("tries");
  $("tries").innerHTML = (Array.isArray(tries) ? tries : []).map((s) => `<li><button type="button">${esc(s)}</button></li>`).join("");
  $("tries").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => openVoice({ text: b.textContent })));
  $("greet").textContent = greeting();
  if (state.ledger) render(state.ledger);
}
function switchLang(l) {
  setLang(l);
  store.set("uiLang", l);
  if (reducedMotion()) { applyI18n(); return; }
  $("views").style.opacity = "0";
  setTimeout(() => { applyI18n(); $("views").style.opacity = ""; }, 120);
}
function openLangPicker() {
  $("langGrid").innerHTML = Object.keys(LANG_NAMES).map((l) => `
    <button type="button" data-lang="${l}" aria-current="${l === lang()}"><b>${LANG_NAMES[l]}</b><small>${LANG_EN[l]}</small></button>`).join("");
  $("langGrid").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    $("langDialog").close();
    switchLang(b.dataset.lang);
  }));
  $("langDialog").showModal();
}

// ------------------------------------------------------------ home
let shownTotal = 0;
function countTo(el, to) {
  const from = shownTotal;
  shownTotal = to;
  if (reducedMotion() || from === to) { el.textContent = rupee(to); return; }
  const start = performance.now();
  const step = (now) => {
    const k = Math.min(1, (now - start) / 600);
    el.textContent = rupee(from + (to - from) * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function renderHome() {
  const L = state.ledger;
  const s = L.stats;
  countTo($("heroAmt"), s.total_due);
  $("heroSub").textContent = s.owing_count === 1 ? t("owing1") : s.owing_count ? t("owing", { n: s.owing_count }) : t("nobody");
  $("todayGiven").textContent = rupee(s.credit_today);
  $("todayGot").textContent = rupee(s.payment_today);
  const given = s.given_30 || 0;
  $("rate30").textContent = given > 0 ? `${Math.min(100, Math.round(((s.collected_30 || 0) / given) * 100))}%` : "—";

  // alerts
  const alerts = [];
  if (s.due_today_count) alerts.push(`<button type="button" class="alert warn" data-go="due">🗓️ ${esc(t("alertDue", { n: s.due_today_count }))}</button>`);
  if (s.over_limit_count) alerts.push(`<button type="button" class="alert risk" data-filter="limit">🚧 ${esc(t("alertLimit", { n: s.over_limit_count }))}</button>`);
  if (s.trust_counts?.risk) alerts.push(`<button type="button" class="alert risk" data-filter="risk">⚠️ ${esc(t("alertRisk", { n: s.trust_counts.risk }))}</button>`);
  $("alerts").innerHTML = alerts.join("");

  // who should pay today (promises due today or overdue)
  const due = [...(L.due?.overdue || []), ...(L.due?.today || [])];
  const byId = new Map(L.customers.map((c) => [c.id, c]));
  $("dueCount").textContent = due.length ? String(due.length) : "";
  $("dueList").innerHTML = due.map((p) => {
    const c = byId.get(p.customer_id) || { name: p.name };
    return `
      <li>
        <button type="button" class="rowbtn" data-cust="${p.customer_id}">${avatar(p.name, { trust: c.trust?.label })}
          <span class="main"><span class="name" style="display:block">${esc(show(p.name))}</span>
          <span class="sub ${p.days < 0 ? "late" : "today"}" style="display:block">🤝 ${esc(dueWords(p))}</span></span></button>
        <span class="right"><span class="amt due">${rupee(p.left)}</span>
          <span class="mini"><button type="button" class="wa" data-remind="${p.customer_id}">💬 ${esc(t("remindShort"))}</button>
          <button type="button" class="collect" data-collect="${p.customer_id}">📲 ${esc(t("collect"))}</button></span></span>
      </li>`;
  }).join("");
  $("dueEmpty").hidden = due.length > 0;
  const up = L.due?.upcoming || [];
  $("upcoming").hidden = !up.length;
  $("upcomingList").innerHTML = up.map((p) => `
    <li><button type="button" class="rowbtn" data-cust="${p.customer_id}">${avatar(p.name)}
      <span class="main"><span class="name" style="display:block">${esc(show(p.name))}</span><span class="sub" style="display:block">🤝 ${esc(dueWords(p))}</span></span></button>
      <span class="right"><span class="amt">${rupee(p.left)}</span></span></li>`).join("");

  // recent entries
  const recent = L.recent || [];
  $("recentCard").hidden = !recent.length;
  $("recentList").innerHTML = recent.map((e) => `
    <li><button type="button" class="rowbtn" data-cust="${e.customer_id}">
      <span class="kind-dot ${e.kind}">${e.kind === "credit" ? emojiFor(e.note) : "💵"}</span>
      <span class="main"><span class="name" style="display:block">${esc(show(e.customer))}</span>
        <span class="sub" style="display:block">${esc(e.kind === "credit" ? (e.note || t("kCredit")) : t("gotMoney"))} · ${esc(whenText(e.created_at))}</span></span></button>
      <span class="right"><span class="amt ${e.kind === "credit" ? "due" : "paid"}">${e.kind === "credit" ? "+" : "−"}${rupee(e.amount)}</span></span></li>`).join("");

  const empty = !L.customers.length;
  $("startEmpty").hidden = !empty;
  $("hero").style.display = empty ? "none" : "";
  $("dueList").closest(".card").hidden = empty;
}

// ------------------------------------------------------------ one place that redraws everything
function render(ledger, res = null) {
  if (!ledger) return;
  state.ledger = ledger;
  const fresh = res?.entry?.customer_id || res?.entries?.[0]?.customer_id || null;
  renderHome();
  renderKhata(fresh);
  renderHisaab();
  renderMore();
  if (res) refreshCustomer();
}
// A small hello under the shop name that follows the time of day, the way a person would greet you.
function greeting() {
  const h = new Date().getHours();
  const g = t(h >= 5 && h < 12 ? "greetM" : h >= 12 && h < 17 ? "greetA" : h >= 17 && h < 22 ? "greetE" : "greetN");
  const first = String(state.me?.account?.name || "").trim().split(/\s+/)[0];
  return first ? t("greetName", { g, name: show(first) }) : g;
}
function renderProfile() {
  const p = state.profile || {};
  $("shopName").textContent = p.shop_name || t("brand");
  $("greet").textContent = greeting();
  renderMore();
}

Object.assign(hooks, { render, openCustomer, go, renderProfile });

// ------------------------------------------------------------ wiring
async function remindFromHome(id) {
  const c = state.ledger.customers.find((x) => x.id === id);
  try {
    const r = await api(`/api/reminder/${id}?lang=${lang()}`);
    window.open(whatsappLink(c?.phone, r.text), "_blank", "noopener");
  } catch (err) { toast(err.message); }
}

function wire() {
  document.querySelectorAll(".tabbar [data-tab]").forEach((b) => b.addEventListener("click", () => go(b.dataset.tab)));
  $("micFab").addEventListener("click", () => openVoice({ listen: true }));
  $("startMic").addEventListener("click", () => openVoice({ listen: true }));
  $("startSample").addEventListener("click", loadSample);
  $("hearBtn").addEventListener("click", (e) => hearSummary(e.currentTarget));
  $("seeKhata").addEventListener("click", () => go("khata"));
  $("langBtn").addEventListener("click", openLangPicker);
  $("moreLang").addEventListener("click", openLangPicker);
  $("meBtn").addEventListener("click", () => go("more"));
  $("shopTop").addEventListener("click", () => openShopDialog(false));
  $("reloadBtn").addEventListener("click", () => location.reload());
  $("scrim").addEventListener("click", () => topSheet()?.querySelector("#vsClose, #custBack")?.click());
  $("view-home").addEventListener("click", (e) => {
    const remind = e.target.closest("[data-remind]");
    if (remind) { remindFromHome(Number(remind.dataset.remind)); return; }
    const collect = e.target.closest("[data-collect]");
    if (collect) {
      const c = state.ledger.customers.find((x) => x.id === Number(collect.dataset.collect));
      if (c) openQR(c);
      return;
    }
    const cust = e.target.closest("[data-cust]");
    if (cust) { openCustomer(Number(cust.dataset.cust)); return; }
    const alert = e.target.closest(".alert");
    if (alert?.dataset.filter) { state.filter = alert.dataset.filter; go("khata"); }
    else if (alert?.dataset.go === "due") $("dueTitle").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  // dialogs: close buttons and clicking outside
  document.querySelectorAll("dialog").forEach((d) => {
    d.addEventListener("click", (e) => {
      if (e.target.closest("[data-close]")) d.close();
      else if (e.target === d) d.close();
    });
  });
  // Space opens the mic from anywhere (when not typing)
  document.addEventListener("keydown", (e) => {
    if (e.code !== "Space" || e.target.closest("input, textarea, select, button, a") || document.querySelector("dialog[open]")) return;
    if (topSheet()) return; // the voice screen handles Space itself
    e.preventDefault();
    openVoice({ listen: true });
  });
  window.addEventListener("popstate", () => { closeVoice(); closeCustomer(); });
}

// ------------------------------------------------------------ start
(async function init() {
  setLang(store.get("uiLang", "hi"));
  initVoice();
  initKhata();
  initHisaab();
  wire();
  applyI18n();
  try {
    const [status, me, profile, ledger] = await Promise.all([
      api("/api/status"), api("/api/me"), api("/api/profile"), api("/api/ledger"),
    ]);
    state.status = status;
    state.me = me;
    state.profile = profile;
    if (status.version !== APP_VERSION) $("updateBanner").hidden = false; // an old server window is still running
    if (!status.gnani_ready) toast(t("noKeyShort"), 9000);
    if (me.account?.picture) { $("meImg").src = me.account.picture; $("meImg").hidden = false; $("meInitial").hidden = true; }
    else if (me.account?.name) $("meInitial").textContent = me.account.name[0].toUpperCase();
    renderProfile();
    render(ledger);
    if (me.account && !me.account.shop_name && !store.get(`askedShop:${me.account.email}`, "")) openShopDialog(true);
    if (["ta", "te", "kn", "bn", "gu", "mr"].includes(getLang()) && status.understanding !== "smart" && !store.get("smartTip", "")) {
      store.set("smartTip", "1");
      setTimeout(() => toast(t("needSmart"), 7000), 1500);
    }
  } catch (err) {
    toast(err.message, 10000);
  }
})();
