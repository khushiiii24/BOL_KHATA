# बोल खाता — Bol Khata

**A voice udhaar khata for kirana shops.** The shopkeeper just says
*"रमेश भैया, दो किलो आटा, 340 रुपये उधार"* and Bol Khata writes it in the khata, then says back
*"रमेश जी के खाते में तीन सौ चालीस रुपये उधार लिख दिया। कुल बाकी आठ सौ नब्बे रुपये।"*

Built for the **Great Indian AI Internship Challenge** on Gnani AI's speech models:

| What | Gnani model | Where in the code |
|---|---|---|
| Hearing the shopkeeper (speech to text) | **Prisma v3.0** (falls back to v2.5) | `app/gnani.py` → `transcribe()` |
| Speaking the reply and reminders (text to speech) | **Timbre v2.5**, one voice per language (Nalini for Hindi, Kaveri for English, Asmita for Tamil...) | `app/gnani.py` → `speak()` |

---

## The problem (in simple words)

Lakhs of small shops in India still write udhaar in a paper notebook. During rush hour there is no time to
write every entry. Pages get lost, totals are added by hand, and mistakes cause fights with customers.
Most khata apps need typing, often in English, which many shopkeepers find slow or hard.

**Bol Khata lets the shopkeeper simply speak**, in Hindi, Hinglish or English, the way they already talk.

## What it can do

### ⭐ What makes Bol Khata different

| Feature | Say this (or tap) | What happens |
|---|---|---|
| **Talk-back voice** | "रमेश को उधार लिखो" | Missing amount? The app *asks* "रमेश जी के खाते में कितने रुपये उधार लिखूँ?" in Gnani Timbre's voice, listens again by itself, and saves when you answer "तीन सौ". Same for a missing name or date. |
| **Conversation mode** | switch on *बातचीत* in the voice screen | After every reply it keeps listening, so you can say entry after entry hands-free. "बस / धन्यवाद" (or silence) ends it. |
| **Promise-to-pay tracker** | "रमेश शुक्रवार को 500 देगा", "बाकी 5 तारीख को देगा" | Saves the promise with its date. Home shows **"आज किससे पैसा आना है"**, overdue promises turn red, and a payment that covers the promise says "रमेश जी ने अपना वादा निभाया". Ask "आज किससे पैसा आना है?" and it reads the list out loud. |
| **Trust (भरोसा) score** | automatic | 0–100 for every customer, from how fast they repay (first-in-first-out), how old their oldest due is, promises kept vs missed, and how much they've paid back. Shown as a coloured ring: भरोसेमंद / ठीक-ठाक / ध्यान दें. |
| **Credit limits** | "सुनीता की लिमिट 1000 रखो" | When new udhaar crosses the limit, the receipt turns red and the voice warns: "ध्यान दें: सुनीता जी की सीमा ₹1,000 है, पर उधार अब ₹1,240 हो गया है।" |
| **UPI collect QR** | customer page → *UPI से पैसे लें* | A QR for the exact due amount using your shop's UPI ID. The customer scans it with any UPI app. Tap *पैसे मिल गए* to record the payment. The WhatsApp reminder includes your UPI ID too. |
| **Two things in one sentence** | "मनीष जी ने 2000 का सामान लिया और वो 1000 जमा करके गए" | Two entries (₹2,000 udhaar + ₹1,000 jama, so ₹1,000 due). "अब 1000 बाकी है" or "कुल 500" are not saved as extra entries. |
| **Voice correction** | "हटाओ, गलत सुना। मनीष जी 2000 का सामान ले गए…" or "रमेश 500 नहीं 400 उधार" | Removes the wrong entry and saves the right one in one go. |
| **Reports** | *हिसाब* tab | 30-day recovery rate ("हर ₹100 उधार में से ₹59 वापस आए"), 7-day chart, how old the dues are (0–7 / 8–30 / 30+ days), customers by trust, biggest dues. |
| **Looks like their own bahi-khata** | just open it | The red cloth ledger every shop already keeps: a cloth cover with gold stitching for the total, ruled pages with a red margin, amounts in handwriting (red ink for udhaar, green for jama), and a brass mic button. On a laptop the cover becomes a sidebar and each section is its own ledger sheet. |
| **Talks like a person** | just use it | Replies aren't one fixed recording. The same entry can come back as "लिख दिया! रमेश जी के खाते में ₹340 उधार।" one time and "ठीक है, रमेश जी के नाम ₹340 उधार चढ़ा दिया।" the next, and it never repeats the same line twice in a row. The header greets you by time of day ("शुभ संध्या, रवि जी"), and if it heard you wrong it says sorry and fixes it. |
| **Accounts** | Step 6 | Gmail login and sign-up. Every person gets their own private khata, shop name and UPI ID. |

### Everyday basics

- **Udhaar:** "रमेश, 340 रुपये उधार", "Pappu ko 160 ka doodh bread diya", "सीता 600 का सामान लेकर गई"
- **Jama (payment):** "Sharma ji ne 500 jama kiye", "इमरान से 200 मिले", "सीता जी 600 रुपये देकर गई हैं"
- **Ask a balance:** "सुनीता का कितना बाकी है?" · **Today:** "आज का हिसाब बताओ" · **Everyone:** "सबका हिसाब"
- **Undo:** "गलत हो गया, हटाओ" (removes everything from the last sentence, including a promise)
- **Amounts the Indian way:** "साढ़े तीन सौ" (350), "dedh sau" (150), "1 लाख 20 हज़ार"; Timbre speaks them back in words.
- **Reminders:** WhatsApp message (with your UPI ID) and a polite voice note in Gnani Timbre's voice to download and send.
- **8 languages:** English, हिंदी, मराठी, ગુજરાતી, বাংলা, தமிழ், తెలుగు, ಕನ್ನಡ. Screens, spoken replies, the language
  Gnani listens for, and customer names (रमेश → *Ramesh* → *ரமேஷ்*) all switch together.
- **Smart hearing:** your customer names are sent to Prisma as *keyterms*, so it hears "Imran" or "Pappu" correctly.
- **Patient mic:** it waits for 2.5 seconds of quiet, so a pause mid-sentence doesn't cut you off.
- **By hand too:** each customer page has a quick udhaar/jama form, phone number, rename, and a deletable timeline.
- **Khata tools:** search, sort (latest, highest due, pending longest, lowest trust), filters (owing, promises,
  30+ days, over limit, careful), CSV download, *Saved khatas* (start fresh without losing anything), sample data.

## Setup, step by step

You need: a Windows laptop with a microphone, Google Chrome or Microsoft Edge, and internet.

### Step 1 — Install Python (one time)

1. Go to <https://www.python.org/downloads/> and download Python 3.12 (any 3.10 or newer is fine).
2. Run the installer. **On the first screen, tick "Add python.exe to PATH"**, then click *Install Now*.

### Step 2 — Get your Gnani API key

1. Open <https://app.gnani.ai> and sign in **with your college email** (the contest asks for this).
   If you don't have one, use your personal email and keep your student ID ready.
2. Open the voice API dashboard: <https://app.gnani.ai/voice>.
3. Find the **API keys** section and **create a new key**. You get 3 free keys and 5,000 credits.
4. **Copy the key** and keep it safe. Don't share it or put it in a screenshot or video.

Optional but useful: in the dashboard, try the **speech-to-text** and **text-to-speech** testers. Say a
Hindi sentence and listen to the voices (Nalini, Deepak, Poorvi...) so you know what to expect.
Docs: <https://docs.gnani.ai>

### Step 3 — Start Bol Khata

1. Open this folder and **double-click `start.bat`**.
2. The first time, it installs what it needs (about a minute). Then **Notepad opens a file called `.env`**.
3. Replace `paste-your-gnani-key-here` with your key, so the line looks like
   `GNANI_API_KEY=abc123...` Change `SHOP_NAME` to your shop's name if you like.
4. **Save and close Notepad.** The app starts and your browser opens <http://localhost:8000>.
5. When the browser asks for the microphone, click **Allow**.

Next time, just double-click `start.bat` again. Keep its black window open while you use the app;
closing it stops the app.

> Mac or Linux teammate? Run `./start.sh` instead.

### Step 4 — Try it

1. On the khata side, click **नमूना ग्राहक भरें** (Load sample customers) to fill in made-up customers.
   (Later you'll find it in the ⋯ menu next to *हिसाब सुनें*.)
2. Click the big yellow **बोलिए** button (or press **Space**) and say:
   *"रमेश भैया, दो किलो आटा, 340 रुपये उधार"*.
   It stops listening by itself when you stop talking.
3. Watch the three steps light up: **सुना** (Gnani Prisma heard you) → **समझा** (Bol Khata understood)
   → **लिखा और बोला** (written in the khata, and Gnani Timbre speaks the reply).
4. Ramesh's row is written into the khata with a yellow highlight.
5. Try the example sentences above the mic. Click any customer to see their timeline, add an amount by hand,
   or make a reminder voice note.
6. Tap 🌐 at the top to see the whole app in English, Tamil, Bengali and the other languages.

No microphone? Type in the box under the mic instead. Gnani still speaks the reply.

### Step 5 (optional) — Smart mode with a free LLM

The built-in rules understand common sentences. For messy, long sentences, add a free LLM:

1. Go to <https://console.groq.com>, sign in, open **API Keys**, create a key.
2. In `.env`, set `LLM_API_KEY=your-groq-key`. Save and restart `start.bat`.
3. The result slip will now say **"समझ: Smart mode (LLM)"**. If the LLM ever fails, Bol Khata quietly
   goes back to the built-in rules.

Prefer Google Gemini? See the commented lines in `.env.example`.

### Step 6 (recommended) — Gmail login and sign-up (every user gets their own khata)

After this step, anyone you allow can **sign up with their Gmail** and gets their **own, private khata**.
Asha sees only Asha's customers, and Ravi only Ravi's. It takes about 10 minutes, one time.

> 📘 **Full click-by-click guide (sign-up, a second person, invite-only, backups, putting it online, a fix for every
> error): [GOOGLE_LOGIN_SETUP.md](GOOGLE_LOGIN_SETUP.md).** The short version is below.

1. Open <https://console.cloud.google.com> and sign in with your Gmail.
2. At the top, click the project list → **New project** → name it `Bol Khata` → **Create**. Make sure it is selected.
3. Open **Google Auth Platform** (older name: **APIs & Services → OAuth consent screen**) → **Get started**:
   - App name: `Bol Khata`, User support email: your Gmail → **Next**
   - Audience: **External** → **Next**
   - Contact email: your Gmail → **Next** → tick the agreement → **Create**
4. Open **Audience** → **Test users** → **Add users**: add **your Gmail and everyone who should be able to sign
   up** (up to 100). While the app is in "Testing", only these Gmails can sign in at all.
5. Open **Clients** (or **Credentials → Create credentials → OAuth client ID**):
   - Application type: **Web application**, name: `Bol Khata laptop`
   - **Authorized JavaScript origins** → add `http://localhost:8000` and also `http://localhost`
   - Leave "redirect URIs" empty → **Create**
   - Copy the **Client ID** (it ends with `.apps.googleusercontent.com`). You do **not** need the client secret.
6. Open `.env` in Notepad and add (or fill in):
   ```
   GOOGLE_CLIENT_ID=paste-your-client-id-here
   ```
   If there is an old line `OWNER_EMAIL=...`, empty it so others can sign up. Save, close the black start.bat
   window and double-click **start.bat** again.
7. Open <http://localhost:8000> → **Continue with Google** → pick your Gmail. The first time is the **sign-up**:
   Bol Khata says *Welcome!* and asks your shop's name. After that it's a normal **login** to the same khata.
8. For someone else: ⋯ menu → **Sign out**, then they click **Continue with Google** with their Gmail and get a new,
   empty khata. (Or use a second browser window, so both can be open at once.)

Your entries from before Step 6 move into the **first** account that signs up, so sign up with your own Gmail first.
To let only certain Gmails sign up, add `ALLOWED_EMAILS=a@gmail.com,b@gmail.com` to `.env`.

**What protects each khata:** every account's khata is a separate file (`data/users/<account>/khata.db`). The server
picks the file from the signed, HTTP-only login cookie on every request, and refuses all data requests without
one. The app also only listens on your own laptop (`127.0.0.1`), so other devices on the Wi-Fi can't open it.

---

## Settings you can change (in `.env`)

| Setting | What it does | Default |
|---|---|---|
| `GNANI_API_KEY` | Your Gnani key (**required**) | — |
| `SHOP_NAME` | Shop name used in reminders while sign-in is off (with sign-in, each person sets their own) | Sharma General Store |
| `STT_MODEL` | Gnani speech-to-text model | `prisma-v3.0` |
| `TTS_MODEL` | Gnani text-to-speech model | `timbre-v2.5` |
| `TTS_VOICE_HI` | Hindi voice. Others: Deepak, Ambuja, Bhavna, Chitra, Omkar, Vikrant... | `Nalini` |
| `TTS_VOICE_EN` | English voice. Others: Devika, Girish, Pranav, Shlok, Trupti | `Kaveri` |
| `TTS_VOICE_MR` / `_GU` / `_BN` | Marathi / Gujarati / Bengali voice (Ishaan, Veera, Dhruva are male options) | `Zahira` / `Falak` / `Kirra` |
| `TTS_VOICE_TA` / `_TE` / `_KN` | Tamil / Telugu / Kannada voice (Trisha, Suhana, Kavin are other options) | `Asmita` / `Lavanya` / `Saanvi` |
| `LLM_API_KEY` | Optional smart mode | empty |
| `GOOGLE_CLIENT_ID` | Turns on Gmail login / sign-up, one khata per Gmail (Step 6) | empty (sign-in off, one shared khata) |
| `ALLOWED_EMAILS` | Only these Gmails (comma-separated) may sign up. Old name: `OWNER_EMAIL` | empty (anyone Google lets in) |
| `PUBLIC_URL` | Only when hosted online: its https address | empty |

If you switch to `TTS_MODEL=timbre-v3.0`, also change the voices to v3.0 names such as `Shivani`
or `Avinash` (v2.5 voice names don't work with v3.0).

The 🌐 button at the top sets one language for everything: the page text, the spoken replies and what Gnani
listens for. With English picked, Gnani listens for English and Hindi, since many people mix the two.

**Note on languages:** Hindi, Hinglish and English are understood well without extra setup. For Marathi,
Gujarati, Bengali, Tamil, Telugu and Kannada, common sentences work (like the examples above the mic), but
for anything more free-form, turn on smart mode (Step 5) — the LLM understands all these languages.

---

## If something goes wrong

> **The page says "Bol Khata was updated…" or new features don't work:** an old black window was still running the
> old version. Close every black Bol Khata window and double-click `start.bat` again (it now closes an old copy by itself).

| You see | Do this |
|---|---|
| Yellow box: "Gnani API key नहीं मिली" | Open `.env`, paste the key after `GNANI_API_KEY=`, save, restart `start.bat`. |
| "Gnani ... error 401" | The key is wrong. Copy it again from app.gnani.ai (no spaces). |
| "Gnani ... error 402" | Credits may be finished. Check usage on app.gnani.ai. |
| "माइक की इजाज़त नहीं मिली" | Click the mic/lock icon in the address bar, set Microphone to **Allow**, reload. Use Chrome or Edge. |
| "No speech was heard" | Speak a bit louder and closer to the mic. Tap the mic again to stop if it keeps listening. |
| Wrong name or amount | Speak the whole sentence; short pauses are fine (the mic waits 2.5 s of quiet). Say "गलत हो गया, हटाओ" (or click *यह एंट्री हटाओ*) and say it again. Turn on smart mode for better understanding. |
| Strange English on the page, like "Fifth note of musical scale" | That is the browser's own auto-translate, not the app. The page now tells the browser not to translate it. If you still see it, click the translate icon in the address bar and choose **Show original** / **Never translate this site**, then use the app's 🌐 button instead. |
| Google says **Error 400: origin_mismatch** | In Google Cloud, the "Authorized JavaScript origins" must be exactly `http://localhost:8000` (and `http://localhost`). Open the app as `localhost`, not `127.0.0.1`. Changes can take 5 minutes. |
| Google says **Access blocked** / app not verified | Add your Gmail as a **Test user** (Step 6, point 4). |
| "… isn't allowed here" | `ALLOWED_EMAILS` (or an old `OWNER_EMAIL`) in `.env` lists Gmails and this one isn't on it. Add it, or empty the line. |
| Sign-in button doesn't appear | It needs internet to load from Google. Check your connection and reload. |
| "Python is not installed" | Do Step 1 again and make sure "Add python.exe to PATH" is ticked. |
| Page doesn't open | Make sure the black `start.bat` window is still open, then go to <http://localhost:8000>. |

All entries are saved in `data/khata.db` on your laptop. *नया खाता शुरू करें* starts a fresh khata and keeps
the old one in *पुराने खाते* (Saved khatas). The only way to delete data for good is *हमेशा के लिए मिटाएँ*
(Delete forever) inside Saved khatas, which needs two taps.

---

## How the code is organised

```
bol-khata/
├─ start.bat            double-click to run (Windows)
├─ .env.example         settings template (start.bat copies it to .env)
├─ GOOGLE_LOGIN_SETUP.md  click-by-click guide for Gmail login / sign-up
├─ app/
│  ├─ main.py           web server and the flow: hear → understand → write → reply
│  ├─ gnani.py          calls Gnani Prisma (speech→text) and Timbre (text→speech)
│  ├─ understand.py     works out customer, amount, udhaar/jama (rules + optional LLM), 8 languages
│  ├─ numbers.py        Indian number words: "साढ़े तीन सौ" ⇄ 350, lakh/crore
│  ├─ replies.py        what Bol Khata says back, in 8 languages (screen text + spoken text)
│  ├─ translit.py       shows names in the reader's script: रमेश → Ramesh / ரமேஷ் / রমেশ
│  ├─ auth.py           Gmail login / sign-up: checks Google's token
│  ├─ accounts.py       one account + one separate khata file per Gmail
│  ├─ phrases.py        replies for talk-back, promises, limits, UPI (8 languages)
│  └─ ledger.py         the khata: entries, promises, limits, trust score, overdue buckets, saved khatas (SQLite)
├─ static/              the phone-app website
│  ├─ index.html, style.css   screens: Home · Khata · Hisaab · More, voice screen, customer page
│  ├─ app.js            tabs, home screen, start-up      ├─ voice.js   mic, talk-back loop, result cards
│  ├─ khata.js          customer list + customer page, UPI QR  ├─ hisaab.js  reports, settings, saved khatas
│  ├─ recorder.js       16 kHz WAV recorder              ├─ ui.js      shared helpers
│  ├─ i18n.js + i18n-extra.js  all page text in 8 languages,  translit.js  names in each script
│  └─ vendor/qrcode.js  QR code maker (MIT licence, Kazuhiko Arase)
└─ tests/               run with:  python -m pytest -q
```

How one voice command flows:

1. `recorder.js` records your voice as a **16 kHz WAV** in the browser. Gnani accepts WAV, but browsers
   record WebM by default, which is why we make the WAV ourselves. It stops after 2.5 s of quiet, so a pause mid-sentence is fine.
2. `POST /api/voice` → `gnani.transcribe()` sends it to **Prisma** at `https://api.vachana.ai/stt/v3` with
   `model=prisma-v3.0`, `format=transcribe` (so numbers come back as digits), a `topic` describing a kirana
   khata, and your customer names as `keyterms`.
3. `understand.py` finds the intent, customer, amount and items. If a sentence has two or more amounts, it
   splits it at "और / aur / and / फिर", commas, or the next name, and makes one entry per part. Pronouns
   ("वो", "उन्होंने") reuse the name said before, and remarks like "अब 1000 बाकी है" are skipped.
   It also spots promises ("शुक्रवार को देगा" + dates like कल / परसों / 5 तारीख / 3 दिन में), limits,
   "आज किससे पैसा आना है?", corrections ("हटाओ, गलत सुना…") and "बस" (end of conversation).
   If something is missing, the server returns a `pending` question; the browser speaks it, listens again,
   and sends the answer with that `pending`, so "तीन सौ" fills in the amount (talk-back).
4. `ledger.py` saves the entry; `replies.py` writes the reply twice: with ₹ digits for the screen, and with
   numbers as words for the voice (Gnani's docs recommend writing numbers as words for Timbre).
5. `POST /api/speak` → `gnani.speak()` sends the reply to **Timbre** at `/api/v1/tts/inference` and the
   browser plays it. Replies are cached, so the same sentence never uses credits twice.

---

## Contest checklist (deadline: 10 November 2026, 11:59 PM IST)

- [ ] App runs on your laptop with your real Gnani key, and voice in + voice out both work.
- [ ] Use **made-up data only**: no real phone numbers, Aadhaar, PAN or real recorded calls.
      (The sample customers are fictional.)
- [ ] Record the demo video (script below). Keep your API key out of the video.
- [ ] Post the video on **LinkedIn and/or X** with **#GnaniAI** and **#GreatIndianAIInternshipChallenge**,
      and tag Gnani AI. Post early (8–9 Nov) so it has time to get likes and comments. Real engagement only.
- [ ] Fill the **Project Submission Form** with your post link(s), the demo video, a written explanation,
      the Gnani models used (Prisma v3.0, Timbre v2.5) and each team member's contribution.

### 90-second demo script (shows what makes it different)

Before recording: ⋯/*और* tab → *नमूना ग्राहक भरें* (sample customers come with promises, a limit and trust scores),
and put a **made-up** UPI ID like `sharmastore@okaxis` in *दुकान की जानकारी*.

| Time | Show | Say / do |
|---|---|---|
| 0–8 s | A paper khata, then the app's home | "Kirana shops still write udhaar by hand. Bol Khata lets them just *say* it." |
| 8–20 s | Mic | *"मनीष जी ने 2000 का सामान लिया और वो 1000 जमा करके गए"*: two entries from one sentence, ₹1,000 due. |
| 20–34 s | Mic (talk-back) | *"रमेश को उधार लिखो"* → the app asks "कितने रुपये?" by itself → answer *"तीन सौ"* → saved. "It talks back like a person." |
| 34–44 s | Mic | *"रमेश शुक्रवार को 500 देगा"* → the promise card. Then *"आज किससे पैसा आना है?"* → it reads the list. |
| 44–54 s | Mic | *"सुनीता 300 का सामान ले गई"* → red limit warning, spoken. Open Sunita: trust ring *ध्यान दें*. |
| 54–68 s | Sunita's page → *UPI से पैसे लें* | The QR for her exact due. Tap *पैसे मिल गए*. Show the WhatsApp reminder and the Timbre voice note. |
| 68–80 s | *हिसाब* tab, then 🌐 → Tamil | Recovery rate and aging; the whole app, names and voice switch to Tamil. |
| 80–90 s | Desktop view | "Bol Khata: Gnani Prisma hears, Gnani Timbre speaks. #GnaniAI" |

Tips: record in a slightly noisy place (a real shop is even better: it shows Prisma handles noise),
use a phone held near the speaker, add Hindi + English captions, and never show your `.env` or API key.

### Draft post (edit it in your own words)

Keep it short and in your own voice. One real line about a shop you know will do more than any list of features.

> The kirana shop near my place still keeps udhaar in a notebook. Every evening the uncle adds it all up by hand,
> and some pages are hard to read even for him.
>
> So I built Bol Khata for the Great Indian AI Internship Challenge. You don't type anything, you just say it:
> "मनीष जी ने 2000 का सामान लिया और 1000 जमा करके गए". It writes both entries, tells you ₹1,000 is still due,
> and says it back in Hindi. If you forget the amount it asks "कितने रुपये?" and waits for you.
>
> It also remembers who promised to pay on Friday, warns you when someone goes past their limit,
> and makes a UPI QR for the exact amount. It works in 8 Indian languages.
>
> Gnani Prisma does the listening and Gnani Timbre does the talking. Demo below, I'd love your feedback.
>
> #GnaniAI #GreatIndianAIInternshipChallenge

(Change the first two lines to your own story, or drop them if it isn't true for you.)

### For the submission form

- **Project title:** Bol Khata: a voice udhaar khata for kirana shops
- **Problem:** Small shopkeepers track credit in paper notebooks; entries are slow to write, easy to lose,
  and totals are error-prone. Typing apps don't suit busy, Hindi-first users.
- **Target users:** kirana owners, sabzi vendors, chai stalls, small traders.
- **Gnani models/APIs used:** Prisma v3.0 STT REST (`/stt/v3`, with topic + keyterms + transcribe format),
  Timbre v2.5 TTS REST (`/api/v1/tts/inference`, a matching voice for each of 8 languages).
- **Accounts & security:** Google Sign-In (ID token checked on the server with google-auth); sign-up on first login;
  one separate SQLite khata per account, picked from a signed session cookie on every request.
- **What's unique:** a voice khata that *talks back* (asks for a missing amount, name or date and listens again),
  a hands-free conversation mode, promise-to-pay tracking with "who pays today", a 0–100 trust score per customer,
  credit limits with spoken warnings, UPI collect QR for the exact due, two entries from one sentence, and
  voice corrections ("हटाओ, गलत सुना…"), all in 8 Indian languages.
- **Award categories it fits:** Real Deal, Mixed Vibes (Hinglish), Main Character (8 Indian languages), Demo Day Drop.
