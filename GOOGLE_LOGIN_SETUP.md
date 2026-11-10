# Login and sign-up for Bol Khata (with Gmail): step by step

This guide turns on **"Continue with Google"**. After that, **every person who signs in gets their own,
private khata**. Asha sees only Asha's customers, and Ravi sees only Ravi's.
Setup takes about **10–15 minutes, one time**. You don't write any code: login and sign-up are already built
into Bol Khata. You only make a free "Client ID" in Google Cloud and paste it into the `.env` file.

---

## 1. How it works (simple words)

- **There are no passwords.** Google checks who you are (Gmail password, phone OTP, 2-step verification,
  whatever that Gmail already uses). Bol Khata never sees or stores a password.
- **Sign-up = the first "Continue with Google".** A new account and an **empty khata** are created for that
  Gmail in about a second. Bol Khata then asks one question: *"What's your shop called?"*
- **Login = every later "Continue with Google"** with the same Gmail. The same khata opens again.
  You stay signed in while you keep using it. After **12 hours without use**, you sign in again.
- **Every account is separate.** Each Gmail's khata is saved in **its own file**
  (`data/users/<account>/khata.db`). The server opens only the signed-in person's file on every request, so
  nobody can read someone else's khata, not even by skipping the login page or guessing numbers.
- **Who can sign up?** Anyone you allow. During the contest, that's the **test users** you list in Google
  Cloud (part C). You can also lock it to a list of Gmails in `.env` (part 10).

```
  "Continue with Google"  ──►  Google's own window: pick a Gmail
                                     │
                                     ▼
                Bol Khata checks Google's signed token: who is this?
                                     │
              ┌──────────────────────┴──────────────────────┐
     first time for this Gmail                       seen before
              │                                             │
              ▼                                             ▼
   SIGN-UP: new account + empty khata               LOGIN: their own khata
   "What's your shop called?"                       opens again
```

---

## 2. Before you start

You need:

1. Bol Khata already working on your laptop (README Steps 1–4).
2. Your **Gmail** address and password.
3. Internet.
4. About 15 minutes.

Keep this guide open on one side of the screen and the browser on the other.

---

## 3. Part A — Make a Google Cloud project (2 minutes)

A "project" is just a folder in Google Cloud that holds your login settings. It is free.

1. Open <https://console.cloud.google.com> and sign in with **your Gmail**.
2. If Google asks you to accept the terms of service, choose your country, tick the box, click **Agree and continue**.
3. At the top-left, next to the "Google Cloud" logo, click the **project picker** (it may say
   *Select a project* or show another project's name).
4. In the window that opens, click **New project** (top-right of that window).
5. **Project name:** type `Bol Khata`. Leave *Location* as it is ("No organization" is fine).
6. Click **Create**. Wait about 20 seconds.
7. Click the project picker again and **select `Bol Khata`**. Its name should now show at the top.

✅ Check: the top bar shows **Bol Khata**.

> Google Cloud may ask for a credit card for *other* products. **You do not need billing for login.**
> If a page asks you to enable billing, you are on the wrong page. Go back to the steps below.

---

## 4. Part B — Branding: the name people see on the Google window (3 minutes)

1. In the search bar at the top, type **Google Auth Platform** and open it.
   (Or open <https://console.cloud.google.com/auth/overview> directly.)
   In some accounts the same place is called **APIs & Services → OAuth consent screen**.
2. If you see **Get started**, click it. Fill in:
   - **App name:** `Bol Khata`
   - **User support email:** choose your Gmail from the list
   - Click **Next**
3. **Audience:** choose **External** → **Next**.
   (*Internal* is only for company Google Workspace accounts. Gmail users must pick External.)
4. **Contact information:** type your Gmail → **Next**.
5. Tick **I agree to the Google API Services: User Data Policy** → **Continue** → **Create**.

✅ Check: the left menu now shows **Overview, Branding, Audience, Clients, Data access**.

You don't need a logo, home page, privacy policy or "authorized domains" for use on your own laptop.
Leave them empty.

---

## 5. Part C — Audience: who may sign up (2 minutes)

Your Google app starts in **Testing** mode. In Testing mode, **only the Gmail addresses you list as test users
can sign in or sign up**. That's perfect for the contest: you decide exactly who gets an account.

1. In the left menu, click **Audience**.
2. Check that **Publishing status** says **Testing**. Leave it like that for now.
3. Scroll to **Test users** → click **+ Add users**.
4. Type **your Gmail**, plus the Gmail of **every person who should be able to sign up** (a friend, a family
   member, a judge you're demoing to). Put one Gmail per line, up to 100 → **Save**.

✅ Check: the Gmails show in the *Test users* list.

**Later, to let anyone at all sign up:** on the same Audience page, click **Publish app** → **Confirm**
(status becomes *In production*). Bol Khata only asks Google for a person's **name, email and photo**, which
Google treats as basic, non-sensitive information, so normally no review is needed. If Google asks you to
verify the app, follow the steps it shows. Keep **Testing** for the contest. It's simpler and more private.

---

## 6. Part D — Clients: create the Client ID (3 minutes)

1. In the left menu, click **Clients** → **+ Create client**.
   (Older layout: **APIs & Services → Credentials → + Create credentials → OAuth client ID**.)
2. **Application type:** choose **Web application**.
3. **Name:** `Bol Khata laptop` (only you see this).
4. Find **Authorized JavaScript origins** → click **+ Add URI** and type exactly:
   ```
   http://localhost:8000
   ```
   Click **+ Add URI** again and add:
   ```
   http://localhost
   ```
   - No `/` at the end. No spaces. `http`, **not** `https`.
   - Google's guide asks for both lines when you test on your own laptop.
5. **Authorized redirect URIs:** leave this **empty**. Bol Khata uses the pop-up button, which doesn't need it.
6. Click **Create**.
7. A box shows **Client ID** and **Client secret**.
   - **Copy the Client ID.** It looks like `1234567890-abc123def456.apps.googleusercontent.com`.
   - You **don't need the client secret**. Don't paste it anywhere.
   - If you closed the box: open **Clients**, click **Bol Khata laptop**, and copy the Client ID from there.

✅ Check: you copied a long text ending in `.apps.googleusercontent.com`.

> Google says new settings can take **5 minutes (sometimes longer)** to start working. If the first try says
> *origin_mismatch*, wait a few minutes and try again.

---

## 7. Part E — Paste it into Bol Khata (2 minutes)

1. Close the black **start.bat** window if it is open (this stops the app).
2. Open the **bol-khata** folder. Right-click the file **`.env`** → **Open with** → **Notepad**.
   (If you can't see `.env`: in File Explorer click **View → Show → File name extensions** and
   **Hidden items**.)
3. Find the line `GOOGLE_CLIENT_ID=` (if it isn't there, type it on a new line at the end) and paste your
   Client ID after the `=`:
   ```
   GOOGLE_CLIENT_ID=1234567890-abc123def456.apps.googleusercontent.com
   ```
   - No spaces, no quotes.
   - **Don't touch the `GNANI_API_KEY=` line.**
   - If your file has an old line `OWNER_EMAIL=yourname@gmail.com`, **empty it** (`OWNER_EMAIL=`) so other people
     can sign up too. If you keep a Gmail there, it works like the invite list in part 10.
4. **File → Save** (Ctrl + S) and close Notepad.
5. Double-click **start.bat** again.

---

## 8. Part F — Sign up (first time, 1 minute)

1. Open **<http://localhost:8000>**. Type `localhost`, **not** `127.0.0.1` (Google only trusts the address you
   added in part D).
2. You see the Bol Khata **sign-in page** with a blue **Continue with Google** button and the note
   *"New here? Continue with Google and your khata is ready in seconds."*
3. Click **Continue with Google**. Google's window pops up. Pick **your Gmail** (enter its password or OTP if asked).
4. Google may show **"Google hasn't verified this app"**. That's normal for your own app in Testing mode.
   Click **Continue**.
5. Google may ask to share your **name, email and profile picture** with Bol Khata. Click **Continue**.
6. Bol Khata opens with **"Welcome, <your name>! 🎉"** and asks **"What's your shop called?"** Type it
   (for example *Sharma General Store*) → **Start my khata**. (You can click *Later* and set it from the ⋯ menu
   → **Shop name** any time. It's used in WhatsApp reminder messages.)
7. Done: this is **your** account and **your** khata.

**Your old entries:** anything you saved *before* turning on sign-in moves into the **first** account that signs
up. So sign up with your own Gmail first. Everyone after that starts with an empty khata.

---

## 9. Part G — A second person signs up (and how to switch)

**On your laptop, one after the other:**

1. Make sure their Gmail is a **test user** (part C).
2. In Bol Khata: ⋯ menu (top-right of the khata) → **Sign out**.
3. They click **Continue with Google** and pick **their** Gmail. They get a new, empty khata and the welcome
   question.
4. When they're done: ⋯ → **Sign out**. You click *Continue with Google* with your Gmail, and your khata is
   exactly as you left it.

**Side by side (handy for a demo):** open a second browser, or a private/incognito window. Each window can be
signed in with a different Gmail at the same time.

**On their own phone or laptop:** see part 13. The app must be put online first.

---

## 10. Optional: invite-only (only listed Gmails may sign up)

Google's test-user list (part C) already limits who can sign in. If you also want Bol Khata itself to enforce
a list (for example after you click *Publish app*), add this line to `.env`:

```
ALLOWED_EMAILS=yourname@gmail.com,friend@gmail.com
```

- Separate Gmails with a comma, no spaces. Save, then restart `start.bat`.
- People not on the list see *"… isn't allowed here. Ask the person who runs this Bol Khata to add your Gmail."*
- **Removing** someone from the list locks them out **on their very next click**. Their khata stays saved in
  case you add them back.
- Leave `ALLOWED_EMAILS=` empty to allow everyone whom Google lets in.

---

## 11. Daily use and handy facts

| You want to | Do this |
|---|---|
| Open your khata | Double-click **start.bat** → browser opens → you're still signed in, or click *Continue with Google* |
| Change your shop name | ⋯ menu → **Shop name** (or *दुकान का नाम*) |
| Sign out | ⋯ menu → **Sign out** (or *साइन आउट*) |
| See whose account a folder is | Open `data\users\<folder>\email.txt` |
| Back up everyone's khatas | Close `start.bat`, copy the whole **`data`** folder somewhere safe |
| Wipe one person's khata | Close `start.bat`, delete their folder in `data\users\` (check `email.txt` first). Next time they sign in, they get an empty khata. |
| Sign everyone out at once | Close `start.bat`, delete **`data\secret.key`**, start again |
| Turn login off again | Empty the line `GOOGLE_CLIENT_ID=` in `.env`, save, restart. The app opens without login and uses one shared khata (`data\khata.db`). The accounts' khatas stay saved for when you turn login back on. |

Where things are kept:

```
data/
├─ accounts.db            who has signed up (Gmail, name, shop name)
├─ secret.key             signs the login cookie (don't share)
├─ khata.db               the shared khata used while login is OFF
└─ users/
   ├─ g1084…/khata.db     Asha's khata      (email.txt says asha@gmail.com)
   └─ g2231…/khata.db     Ravi's khata      (email.txt says ravi@gmail.com)
```

---

## 12. If something goes wrong

| You see | Why | Fix |
|---|---|---|
| No sign-in page, the khata opens directly | `GOOGLE_CLIENT_ID` is empty or `start.bat` wasn't restarted | Check the line in `.env` (part E), save, restart `start.bat` |
| **Error 400: origin_mismatch** | The address in the browser isn't in "Authorized JavaScript origins" | Use `http://localhost:8000` (not `127.0.0.1`). Check part D: both origins, `http` not `https`, no `/` at the end. Wait 5 minutes after any change. |
| **Error 401: invalid_client** / "The OAuth client was not found" | The Client ID was copied wrong | Copy it again from **Clients**. It must end with `.apps.googleusercontent.com`, and the whole ID must be on one line. |
| **Access blocked: Bol Khata has not completed the Google verification process** | That Gmail isn't a test user | Add it in **Audience → Test users** (part C) |
| **"… isn't allowed here"** | `ALLOWED_EMAILS` (or an old `OWNER_EMAIL`) in `.env` lists Gmails, and this one isn't on it | Add the Gmail to that line, or empty it (parts E and 10) |
| A new person sees **your** customers | They didn't sign up: you were still signed in | ⋯ → **Sign out** first, then they click *Continue with Google* |
| Your old entries are in someone else's account | They signed up first after login was turned on | Close `start.bat`. In `data\users\`, find their folder (`email.txt`), and swap the `khata.db` files between their folder and yours. |
| The sign-in button doesn't appear, or "could not load" | The Google button loads from the internet | Check your internet, then reload. Some ad-blockers block `accounts.google.com`: allow it for localhost. |
| The pop-up opens and closes, nothing happens | The browser blocked pop-ups or third-party cookies | Allow pop-ups for `localhost` (icon at the right of the address bar), then try again. Use Chrome or Edge. |
| "Google sign-in could not be checked: Token used too early / expired" | The laptop's clock is wrong | Windows **Settings → Time & language → Date & time → Set time automatically: On**, then sign in again |
| Signed out every morning | Normal: after 12 hours without use, you sign in again | Just sign in again |

---

## 13. Other people on their own phones: putting Bol Khata online (optional)

Right now Bol Khata runs **only on your laptop** (`localhost`), so other people can use their accounts only on
your laptop. For other shopkeepers to sign up from **their own phones**, the app has to run on a server with an
**https** address. Phones only allow the microphone on https pages, and Google only allows https outside localhost.

When you do that, for example at `https://bolkhata.example.com`:

1. Add `https://bolkhata.example.com` to **Authorized JavaScript origins** (part D).
2. In the server's `.env`, add `PUBLIC_URL=https://bolkhata.example.com` (the login cookie is then sent over https only).
3. Add test users (part C), or click **Publish app** to let anyone sign up.
4. The server needs a disk that keeps files (the `data` folder holds every account's khata).

This isn't needed for the contest demo. Two browser windows on your laptop show separate accounts well.

---

## 14. Is this safe? (good to say in your demo)

- Passwords stay with **Google**. Bol Khata only receives a **signed token** and checks it with Google's public
  keys (`google-auth` library) before trusting it.
- **Each account has its own database file.** At the start of every request, the server picks the file that
  belongs to the Gmail in the **signed, HTTP-only session cookie**. Without a valid cookie, every data request
  (customers, entries, voice, CSV download) is refused with **401**. If no account was picked, the code refuses
  to run instead of falling back to a shared file.
- On your laptop, the app only listens on `127.0.0.1`, so other phones or laptops on the same Wi-Fi can't open it.
- The **Client ID is not a secret** (it is shown inside every login page), but your `.env` also holds your
  **Gnani API key**, so **never share `.env`** or show it in a screenshot or video.
