# Sending real verification emails

DigiSafe works out of the box with no setup: when no mail server is configured,
the verification code is **printed in the server console** and a copy of the
message is saved to `storage/outbox/`. Sign-up, verification and login all work
that way — nothing is faked, the mail simply is not posted.

To have codes actually arrive in people's inboxes, point the app at a mail
server. That takes five environment variables and about three minutes.

---

## Important: nobody should type a password into a chat window

The values below are **secrets**. Set them yourself, on your own machine or in
your hosting dashboard. Do not paste them into a chat, a screenshot, a commit,
or a file inside this repository. `.gitignore` already excludes `.env`, and
nothing in `core/config.py` contains a real credential — every value is read
from the environment for exactly this reason.

---

## Option A — Gmail (easiest for a student project)

Gmail will not accept your normal Google password from an app. You need a
16-character **App Password**, which is a separate credential you can revoke at
any time without touching your account password.

1. Turn on 2-Step Verification: <https://myaccount.google.com/security>
   (App Passwords do not exist until 2-Step Verification is on.)
2. Go to <https://myaccount.google.com/apppasswords>
3. Create one, name it `DigiSafe`, and copy the 16 characters it shows you.
   It is shown once. If you lose it, delete it and make another.
4. Use these settings:

| Variable        | Value                                  |
|-----------------|----------------------------------------|
| `SMTP_HOST`     | `smtp.gmail.com`                       |
| `SMTP_PORT`     | `587`                                  |
| `SMTP_USER`     | your full Gmail address                |
| `SMTP_PASSWORD` | the 16-character App Password          |
| `SMTP_STARTTLS` | `true`                                 |
| `MAIL_FROM`     | your full Gmail address                |
| `MAIL_FROM_NAME`| `DigiSafe`                             |

Gmail's free tier sends roughly 500 messages a day — far more than a project
demonstration needs.

## Option B — Brevo, Mailjet, SendGrid, Resend

Any transactional mail provider works; they all give you a host, a username and
a key on their free tier. Fill in the same five variables. Providers like these
are what a real deployment would use, because mail from a proper sending domain
is far less likely to land in a spam folder than mail from a personal Gmail.

---

## Setting the variables

### Windows — running locally

Create a file called `run_with_email.bat` next to `main.py`
(**do not commit it** — add it to `.gitignore` if you keep it):

```bat
@echo off
set SMTP_HOST=smtp.gmail.com
set SMTP_PORT=587
set SMTP_USER=your.address@gmail.com
set SMTP_PASSWORD=your16charapppassword
set MAIL_FROM=your.address@gmail.com
set MAIL_FROM_NAME=DigiSafe
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Double-click it to start the server with mail enabled.

### PowerShell, one session

```powershell
$env:SMTP_HOST="smtp.gmail.com"; $env:SMTP_PORT="587"; $env:SMTP_USER="your.address@gmail.com"; $env:SMTP_PASSWORD="your16charapppassword"; $env:MAIL_FROM="your.address@gmail.com"
```

### Render (or any host with an Environment tab)

Add each variable in the dashboard under **Environment**. `render.yaml` already
lists them with `sync: false`, which means Render prompts you for the value and
never stores it in the repository.

---

## Checking it works

Start the server and register an account with an address you can actually open.

* **Code arrives in the inbox** — done.
* **Console says `EMAIL NOT SENT — no SMTP server is configured`** — the
  variables are not reaching the process. On Windows, `set` only applies to the
  window you typed it in, so start the server from that same window.
* **Console says `EMAIL DELIVERY FAILED`** — the reason is printed on the next
  line. The usual causes:

  | Message contains | Meaning |
  |---|---|
  | `Username and Password not accepted` | Using your Google password instead of an App Password |
  | `Application-specific password required` | 2-Step Verification is on but you used the account password |
  | `getaddrinfo failed` / `timed out` | No internet, or a firewall blocking port 587 |
  | `SSLError` / `WRONG_VERSION_NUMBER` | Port 465 needs `SMTP_SSL=true` instead of `SMTP_STARTTLS=true` |

  In every failure case the code is still printed to the console and the message
  is still saved to `storage/outbox/`, so an account is never stranded.

---

## The other settings

| Variable | Default | What it does |
|---|---|---|
| `APP_BASE_URL` | *(unset)* | Address used to build the link inside the email. Leave unset and it is taken from the request, so the link works over a Cloudflare tunnel, on a phone over Wi-Fi, or on localhost without reconfiguration. Set it on a fixed domain — doing so also stops a forged `Host` header from influencing the link. |
| `DIGISAFE_REQUIRE_VERIFICATION` | `true` | Set `false` only for an offline walkthrough. Accounts then become usable the moment they are created. |
| `VERIFICATION_TTL_MINUTES` | `30` | How long a code stays valid. |
| `VERIFICATION_RESEND_COOLDOWN` | `60` | Seconds between resends for one account. |
| `VERIFICATION_MAX_ATTEMPTS` | `8` | Wrong guesses before the code is cancelled and must be resent. |

---

## What the emails contain

Every verification message carries **both** a 6-digit code and a clickable link,
and either one completes the process. That is deliberate: a Cloudflare tunnel
hands out a new address on every restart, and a link generated before a restart
points at a host that no longer exists. The typed code does not care where the
site is being served from, so it always works.

The relevant code lives in [`services/email_service.py`](services/email_service.py)
and [`routers/auth.py`](routers/auth.py).
