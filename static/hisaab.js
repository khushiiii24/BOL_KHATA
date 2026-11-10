// The "Hisaab" (reports) tab, the settings tab, saved khatas, and the welcome step after sign-up.
import { LANG_NAMES, locale, t } from "/static/i18n.js";
import { customerRow } from "/static/khata.js";
import {
  $, APP_VERSION, api, esc, hooks, lang, rupee, say, send, state, store, toast, whenText,
} from "/static/ui.js";

// ------------------------------------------------------------ reports
export function renderHisaab() {
  const L = state.ledger;
  if (!L) return;
  const s = L.stats;
  const given = s.given_30 || 0, got = s.collected_30 || 0;
  const rate = given > 0 ? Math.min(100, Math.round((got / given) * 100)) : null;
  const max = Math.max(1, ...L.week.map((d) => Math.max(d.credit, d.payment)));
  const aging = s.aging || [0, 0, 0];
  const agingTotal = aging.reduce((a, b) => a + b, 0) || 1;
  const AG = [["#E2B04B", t("rpAging0")], ["#D2702A", t("rpAging1")], ["#B21E26", t("rpAging2")]];
  const tc = s.trust_counts || {};
  const top = [...L.customers].filter((c) => c.balance > 0.5).sort((a, b) => b.balance - a.balance).slice(0, 5);

  $("report").innerHTML = `
    <section class="card">
      <header class="card-head"><h2>${esc(t("rp30"))}</h2>
        <button type="button" class="link" id="rpHear">🔊 ${esc(t("summaryBtn"))}</button></header>
      <div class="stat-grid">
        <div class="stat credit"><small>${esc(t("rpGiven"))}</small><b>${rupee(given)}</b></div>
        <div class="stat payment"><small>${esc(t("rpCollected"))}</small><b>${rupee(got)}</b></div>
      </div>
      <div class="rate">
        <span class="ring" style="--p:${rate ?? 0}" data-label="${rate == null ? "—" : rate + "%"}"></span>
        <div><b>${esc(t("rpRate"))}</b><small>${esc(rate == null ? t("rpRateNone") : t("rpRateText", { n: rate }))}</small></div>
      </div>
    </section>

    <section class="card">
      <header class="card-head"><h2>${esc(t("weekTitle"))}</h2></header>
      <div class="week">${L.week.map((d) => `
        <div class="day" title="${esc(d.date)}: +${rupee(d.credit)} / −${rupee(d.payment)}">
          <div class="bars"><i class="c" style="height:${(d.credit / max) * 100}%"></i><i class="p" style="height:${(d.payment / max) * 100}%"></i></div>
          <small>${esc(new Date(d.date + "T00:00:00").toLocaleDateString(locale(), { weekday: "narrow" }))}</small>
        </div>`).join("")}</div>
      <div class="legend"><span><i style="background:#C6434B"></i>${esc(t("legendCredit"))}</span><span><i style="background:#2E8A55"></i>${esc(t("legendPaid"))}</span></div>
    </section>

    <section class="card">
      <header class="card-head"><h2>${esc(t("rpAging"))}</h2><span class="amt due">${rupee(s.total_due)}</span></header>
      <div class="aging-bar">${aging.map((a, i) => `<i style="width:${(a / agingTotal) * 100}%;background:${AG[i][0]}"></i>`).join("")}</div>
      <ul class="aging-list">${aging.map((a, i) => `<li><span><i style="background:${AG[i][0]}"></i>${esc(AG[i][1])}</span><b class="num">${rupee(a)}</b></li>`).join("")}</ul>
    </section>

    <section class="card">
      <header class="card-head"><h2>${esc(t("rpTrust"))}</h2></header>
      <div class="trust-chips">
        ${["good", "ok", "risk", "new"].map((k) => `<button type="button" class="${k}" data-trust="${k}"><b>${tc[k] || 0}</b>${esc(t({ good: "trustGood", ok: "trustOk", risk: "trustRisk", new: "trustNew" }[k]))}</button>`).join("")}
      </div>
      <p class="note">${esc(t("rpTrustHelp"))}</p>
    </section>

    ${top.length ? `<section class="card"><header class="card-head"><h2>${esc(t("rpTop"))}</h2></header>
      <ul class="cust-list" style="margin:0;padding:0;box-shadow:none">${top.map((c) => `<li>${customerRow(c)}</li>`).join("")}</ul></section>` : ""}`;

  $("rpHear").onclick = (ev) => hearSummary(ev.currentTarget);
  $("report").querySelectorAll("[data-trust]").forEach((b) => (b.onclick = () => {
    state.filter = b.dataset.trust === "risk" ? "risk" : "all";
    state.sort = "trust";
    $("sort").value = "trust";
    hooks.go?.("khata");
  }));
  $("report").querySelectorAll("[data-cust]").forEach((b) => (b.onclick = () => hooks.openCustomer?.(Number(b.dataset.cust))));
}

export async function hearSummary(btn) {
  try {
    const r = await api(`/api/summary?lang=${lang()}`);
    await say(r, btn);
  } catch (err) { toast(err.message); }
}

// ------------------------------------------------------------ settings
export function renderMore() {
  const me = state.me || {};
  const acc = me.account;
  $("accountCard").innerHTML = acc
    ? `${acc.picture ? `<img src="${esc(acc.picture)}" alt="" referrerpolicy="no-referrer">` : `<span class="avatar big" style="--av-bg:var(--brand-soft);--av-fg:var(--brand)">${esc((acc.name || "?")[0])}</span>`}
       <div class="who"><b>${esc(acc.name || "")}</b><small>${esc(acc.email)}</small></div>
       <button type="button" class="btn" id="signOutBtn">${esc(t("signOut"))}</button>`
    : `<span style="font:1.8rem/1 var(--emoji)">🔓</span><div class="who"><b>${esc(t("brand"))}</b><small>${esc(t("authOff"))}</small></div>`;
  $("signOutBtn")?.addEventListener("click", async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* ignore */ }
    location.reload();
  });
  const p = state.profile || {};
  if (document.activeElement !== $("pfShop")) $("pfShop").value = p.shop_name || "";
  if (document.activeElement !== $("pfUpi")) $("pfUpi").value = p.upi_id || "";
  $("talkDefault").checked = store.get("talkMode", "0") === "1";
  $("moreLangName").textContent = LANG_NAMES[lang()];
  const n = state.ledger?.stats?.archive_count || 0;
  $("archiveCount").textContent = n ? String(n) : "›";
  $("version").textContent = `${t("stVersion", { v: APP_VERSION })} · Gnani Prisma + Timbre`;
}

async function saveProfile(shop, upi) {
  const res = await send("/api/profile", "PATCH", { shop_name: shop, upi_id: upi });
  state.profile = { ...state.profile, ...res };
  if (res.account) state.me = { ...state.me, account: res.account };
  hooks.renderProfile?.();
  return res;
}

// welcome after sign-up, or "Shop name" from the header
export function openShopDialog(welcome = false) {
  const acc = state.me?.account;
  $("shopTitle").textContent = welcome ? t("welcomeTitle", { name: (acc?.name || "").split(" ")[0] }) : t("stShop");
  $("shopText").hidden = !welcome;
  $("shopLater").textContent = welcome ? t("later") : t("cancel");
  $("shopSave").textContent = welcome ? t("welcomeGo") : t("save");
  $("shopInput").value = state.profile?.shop_name && state.profile.shop_name !== acc?.name ? state.profile.shop_name : "";
  $("shopUpi").value = state.profile?.upi_id || "";
  if (welcome && acc) store.set(`askedShop:${acc.email}`, "1");
  $("shopDialog").showModal();
  setTimeout(() => $("shopInput").focus(), 50);
}

// ------------------------------------------------------------ saved khatas
async function openArchives() {
  let data;
  try { data = await api("/api/archives"); } catch (err) { toast(err.message); return; }
  const list = data.archives || [];
  $("arBody").innerHTML = list.length ? `<ul class="ar-list">${list.map((a) => `
      <li data-id="${a.id}">
        <div class="grow"><b>${esc(t("arSavedOn", { date: whenText(a.created_at) }))}</b>
          <small>${esc(t("arStats", { c: a.customer_count, e: a.entry_count }))} · ${esc(t("arDue", { amt: rupee(a.total_due) }))}${a.reason === "sample" ? ` · ${esc(t("arReasonSample"))}` : ""}</small></div>
        <a class="chipbtn" href="/api/archives/${a.id}/csv" download>${esc(t("arCsv"))}</a>
        <button type="button" class="chipbtn" data-open="${a.id}">${esc(t("arOpen"))}</button>
        <button type="button" class="chipbtn danger" data-del="${a.id}">${esc(t("arDelete"))}</button>
        <div class="ar-detail" id="ard${a.id}" hidden style="flex-basis:100%"></div>
      </li>`).join("")}</ul>` : `<p>${esc(t("arEmpty"))}</p>`;
  $("arBody").querySelectorAll("[data-open]").forEach((b) => (b.onclick = async () => {
    const box = $(`ard${b.dataset.open}`);
    if (!box.hidden) { box.hidden = true; return; }
    try {
      const d = await api(`/api/archives/${b.dataset.open}`);
      box.innerHTML = `<p class="note">${esc(t("arReadonly"))}</p><ul class="cust-list" style="margin:6px 0 0;padding:0 10px;pointer-events:none">${d.customers.map((c) => `<li>${customerRow(c)}</li>`).join("")}</ul>`;
      box.hidden = false;
    } catch (err) { toast(err.message); }
  }));
  $("arBody").querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    if (!b.dataset.sure) { b.dataset.sure = "1"; b.textContent = t("arDeleteConfirm"); return; }
    try {
      const res = await api(`/api/archives/${b.dataset.del}`, { method: "DELETE" });
      hooks.render?.(res.ledger);
      openArchives();
    } catch (err) { toast(err.message); }
  }));
  if (!$("archiveDialog").open) $("archiveDialog").showModal();
}

export async function loadSample() {
  try {
    const res = await send(`/api/demo?lang=${lang()}`, "POST");
    hooks.render?.(res);
    if (res.saved) toast(t("sampleSaved"));
    hooks.go?.("home");
  } catch (err) { toast(err.message); }
}

export function initHisaab() {
  $("profileForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try { await saveProfile($("pfShop").value, $("pfUpi").value); toast(t("saved"), 2500); } catch (err) { toast(err.message); }
  });
  $("shopForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try { await saveProfile($("shopInput").value, $("shopUpi").value); $("shopDialog").close(); toast(t("saved"), 2500); }
    catch (err) { toast(err.message); }
  });
  $("talkDefault").addEventListener("change", () => store.set("talkMode", $("talkDefault").checked ? "1" : "0"));
  $("archivesBtn").addEventListener("click", openArchives);
  $("newKhataBtn").addEventListener("click", () => $("newKhataDialog").showModal());
  $("nkConfirm").addEventListener("click", async () => {
    $("newKhataDialog").close();
    try {
      const res = await send("/api/archive", "POST");
      hooks.render?.(res);
      toast(res.saved ? t("arSavedToast") : t("arNothing"));
      hooks.go?.("home");
    } catch (err) { toast(err.message); }
  });
  document.querySelectorAll("[data-sample]").forEach((b) => b.addEventListener("click", loadSample));
}
