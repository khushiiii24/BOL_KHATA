// Continue with Google: the first time is sign-up (a new, empty khata), every later time is login.
// The server checks the token with Google; each Gmail only ever sees its own khata.
import { LANG_NAMES, getLang, setLang, t } from "/static/i18n.js";

const $ = (id) => document.getElementById(id);
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};
let config = null;

function applyText() {
  document.documentElement.lang = getLang();
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $("langs").innerHTML = Object.entries(LANG_NAMES).map(([l, n]) =>
    `<button type="button" data-lang="${l}" aria-current="${l === getLang()}">${n}</button>`).join("");
  $("langs").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    setLang(b.dataset.lang);
    store.set("uiLang", b.dataset.lang);
    applyText();
    renderButton();
  }));
}

function showError(text) {
  $("loginError").textContent = text;
  $("loginError").hidden = !text;
}

async function onCredential(response) {
  showError("");
  try {
    const res = await fetch("/api/auth/google", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    });
    const body = await res.json().catch(() => ({}));
    if (res.ok) { location.href = "/"; return; }
    if (res.status === 403 && body.detail === "not_allowed") showError(t("loginNotOwner", { email: body.email || "" }));
    else showError(`${t("loginError")} ${body.detail || res.status}`);
  } catch (err) {
    showError(`${t("loginError")} ${err.message}`);
  }
}

function renderButton() {
  if (!config || !window.google?.accounts?.id) return;
  google.accounts.id.initialize({ client_id: config.client_id, callback: onCredential, ux_mode: "popup" });
  $("googleBtn").innerHTML = "";
  google.accounts.id.renderButton($("googleBtn"), {
    type: "standard", theme: "filled_blue", size: "large", shape: "pill",
    text: "continue_with", logo_alignment: "left", width: 280, locale: getLang(),
  });
}

(async function init() {
  setLang(store.get("uiLang", "hi"));
  applyText();
  try {
    config = await (await fetch("/api/auth/config")).json();
  } catch (err) {
    showError(`${t("loginError")} ${err.message}`);
    return;
  }
  if (!config.enabled) { location.href = "/"; return; }
  $("firstNote").hidden = !config.open_signup;   // anyone can sign up
  $("inviteNote").hidden = config.open_signup;   // only the Gmails in ALLOWED_EMAILS
  // Google's script loads in the background; wait for it
  let tries = 0;
  const wait = setInterval(() => {
    if (window.google?.accounts?.id) { clearInterval(wait); renderButton(); }
    else if (++tries > 50) { clearInterval(wait); showError(`${t("loginError")} Google sign-in could not load. Check your internet.`); }
  }, 100);
})();
