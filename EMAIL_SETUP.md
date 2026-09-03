# Sending real verification emails

The goal: someone signs up with **their own** address — `@gmail.com`,
`@yahoo.com`, `@outlook.com`, `@st.knust.edu.gh`, anything — and the 6-digit
code arrives in **their** inbox, on their phone, exactly the way it does when
you sign up for any real service. That needs one mailbox for DigiSafe to *send
from*; recipients can then be any address at all.

This takes about five minutes.

> **Without this step DigiSafe still runs.** Verification codes are printed in
> the server console and saved to `storage/outbox/`. That is enough to develop
> against and enough to demonstrate the flow on your own machine — but someone
> registering from their own phone cannot see your console, so nothing below is
> optional if other people are going to use the site.

---

## Important: nobody should type a password into a chat window

The values below are **secrets**. Put them in your own `.env` file, on your own
machine, or in your hosting dashboard. Do not paste them into a chat, a
screenshot, a commit, or any file that gets committed. `.gitignore` already
excludes `.env`, and nothing in `core/config.py` contains a real credential —
every value is read from the environment for exactly this reason.

---

## The short version

```bash
python tools/setup_email.py
```

It asks which provider you use, takes your address and password (typed into
your own terminal, never echoed), writes `.env`, and immediately sends a test
message so you know whether it worked. If that succeeds you are done — skip to
"Step 4" below and restart the server.

The rest of this page is the same thing done by hand, plus what to do when it
goes wrong.

---

## Step 1 — Get an App Password

Gmail will not accept your normal Google password from an application. You need
a 16-character **App Password**: a separate credential, revocable at any time
without touching your account password.

1. Turn on 2-Step Verification: <https://myaccount.google.com/security>
   (App Passwords do not exist until 2-Step Verification is on.)
2. Go to <https://myaccount.google.com/apppasswords>
3. Create one, name it `DigiSafe`, and copy the 16 characters.
   It is shown **once**. If you lose it, delete it and make another.

Gmail's free tier sends roughly 500 messages a day — far more than a project
demonstration needs.

<details>
<summary>Not using Gmail?</summary>

Any transactional mail provider works — Brevo, Mailjet, SendGrid, Resend — and
all of them have a free tier that gives you a host, a username and a key. Fill
in the same fields with their values. This is what a real deployment would use:
mail from a proper sending domain is far less likely to be filtered into spam
than mail from a personal Gmail account.

</details>

---

## Step 2 — Create your `.env` file

In the project folder, copy the template:

```bash
copy .env.example .env
```

(on macOS or Linux, `cp .env.example .env`)

Open `.env` and fill in the email section:

```ini
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USER=your.address@gmail.com
SMTP_PASSWORD="abcd efgh ijkl mnop"
MAIL_FROM=your.address@gmail.com
MAIL_FROM_NAME=DigiSafe
```

The quotes around the password let you paste the App Password with or without
the spaces Google displays it in.

The server reads `.env` automatically at startup, so this survives closing your
terminal, rebooting, and double-clicking `START_LIVE_SITE.bat`. That is the
whole reason to prefer it over typing `set` in a console window — a `set` only
applies to the one window you typed it in, which is how mail silently stops
working the next time you start the server.

`.env` is in `.gitignore`. `.env.example` holds no real values and is committed,
so anyone cloning the project knows what to fill in.

---

## Step 3 — Prove it works, before you need it

```bash
python tools/check_email.py your.own.address@gmail.com
```

This sends one real message and tells you exactly what happened. `DELIVERED`
means sign-up now works for every address anyone types in, on any provider.

Run this *before* a demonstration. Discovering a bad password during a live
sign-up is discovering it too late.

If it fails, the script names the likely cause. The common ones:

| Message contains | What to fix |
|---|---|
| `Application-specific password required` | You used your Google password. Go back to Step 1. |
| `Username and Password not accepted` | Same cause, or `SMTP_USER` is missing the `@gmail.com` part. |
| `getaddrinfo failed` | Typo in `SMTP_HOST`, or the machine is offline. |
| `timed out` | A firewall or the campus network is blocking outbound SMTP. Try a phone hotspot. |
| `WRONG_VERSION_NUMBER` | Port 465 needs `SMTP_SSL=true`; port 587 needs `SMTP_STARTTLS=true`. |
| `certificate verify failed` | Something is intercepting the connection — see below. |

### "certificate verify failed" / `Basic Constraints of CA cert not marked critical`

This is not a password problem, and no password will fix it. An antivirus
"mail shield" or a campus proxy is terminating the encrypted connection and
presenting its own certificate in place of the mail provider's, and Python
correctly refuses it.

Both `setup_email.py` and `check_email.py` now detect this before asking for
or using a credential, and say so. Three ways past it, easiest first:

1. **Use port 2525.** Scanners routinely intercept 587 and 465 and almost never
   touch 2525. Brevo offers it — that is why it is the Brevo option in
   `setup_email.py`.
2. **Turn off encrypted-mail scanning.** In Avast:
   *Menu → Settings → Protection → Core Shields → Mail Shield →* untick
   *"Scan secure connections"*. Other products call it SSL scanning or mail
   filtering.
3. **Try another network.** A phone hotspot settles it in a minute — if it
   works there, the block is on your usual network rather than the machine.

In every failure case the code is still printed to the console and the message
still saved to `storage/outbox/`, so an account is never stranded mid-signup.

**Check the spam folder** on the first message. If it landed there, mark it "not
spam" before your demonstration so later ones reach the inbox. Mail from a
personal Gmail to an unfamiliar recipient is filtered more aggressively than
mail from a dedicated sending domain.

---

## Step 4 — Start the server and watch the banner

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Startup now tells you which mode you are in:

```
Email verification ON - codes will be sent via smtp.gmail.com as you@gmail.com.
```

If it instead says **NO MAIL SERVER is configured**, `.env` is not being read —
check it is named exactly `.env` (not `.env.txt`, which Windows will hide the
extension of) and sits beside `main.py`.

---

## Deploying with email

On Render, Hugging Face or any host with an Environment tab, set the same keys
there rather than committing a `.env`. `render.yaml` already lists them with
`sync: false`, which means the platform prompts you for each value and never
stores it in the repository. A real environment variable always takes precedence
over `.env`, so a stray file cannot override the host's own settings.

---

## The other settings

| Variable | Default | What it does |
|---|---|---|
| `APP_BASE_URL` | *(unset)* | Address used to build the link inside the email. Leave unset and it is taken from the request, so the link works over a Cloudflare tunnel, on a phone over Wi-Fi, or on localhost without reconfiguration. Set it on a fixed domain — that also stops a forged `Host` header from influencing the link. |
| `DIGISAFE_REQUIRE_VERIFICATION` | `true` | Set `false` only for an offline walkthrough. Accounts then become usable the moment they are created. |
| `VERIFICATION_TTL_MINUTES` | `30` | How long a code stays valid. |
| `VERIFICATION_RESEND_COOLDOWN` | `60` | Seconds between resends for one account. |
| `VERIFICATION_MAX_ATTEMPTS` | `8` | Wrong guesses before the code is cancelled and must be resent. |

---

## Why every email carries both a code and a link

Either one completes verification. That is deliberate: a Cloudflare tunnel hands
out a new address on every restart, so a link generated before a restart points
at a host that no longer exists. The typed code does not care where the site is
being served from, so it always works — and on a phone, `autocomplete="one-time-code"`
lets iOS and Android offer the code straight from the notification without
switching apps.

The relevant code lives in [`services/email_service.py`](services/email_service.py)
and [`routers/auth.py`](routers/auth.py).
