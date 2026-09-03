# DigiSafe — deployment checklist

Everything you need in one place. Work top to bottom.

---

## A. Create the database (Neon — free, no credit card)

Render's free Postgres asks for a card. Neon's does not, and unlike Render's it
does not expire after 30 days.

1. <https://neon.com> → **Sign up** → use **GitHub**
2. Create a project named `digisafe`, region closest to **Frankfurt**
3. Copy the **Connection string**. It looks like:

```
postgresql://digisafe_owner:xxxxxxxx@ep-something-123456.eu-central-1.aws.neon.tech/digisafe?sslmode=require
```

Keep that tab open — you need the string in section C.

---

## B. Create the web service (Render — free)

<https://dashboard.render.com> → **New ▾ → Web Service** → connect
`Mandella21/digisafe`

| Setting | Value |
|---|---|
| Name | `digisafe-knust` |
| Language / Runtime | **Python 3** |
| Branch | `main` |
| Region | **Frankfurt (EU Central)** |
| Root Directory | *(leave blank)* |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | **Free** |
| Health Check Path | `/` |

Do **not** add a training step to the build. The trained models are committed
and the library versions are pinned to match them; fitting a model on a 512 MB
instance risks an out-of-memory build failure.

---

## C. Environment variables

### Set these five now — the site will not work correctly without them

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.7` |
| `DATABASE_URL` | the Neon connection string from section A |
| `SECRET_KEY` | see generator below |
| `DIGISAFE_AES_KEY` | see generator below — **exactly 32 characters** |
| `DIGISAFE_REQUIRE_VERIFICATION` | `false` *(until email works — see section D)* |

Generate the two secrets on your own machine and copy the output:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```bash
python -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))"
```

> **`DIGISAFE_AES_KEY` can never change once evidence exists.** It decrypts
> every stored record. Change it later and all of them become permanently
> unreadable. Save it somewhere safe.

> **`DATABASE_URL` matters more than it looks.** Without it the app falls back
> to a SQLite file on Render's disposable disk, and every account and evidence
> record is destroyed on each restart, redeploy and idle spin-down.

Then **Deploy**.

---

## D. Turn on real email (when you have a Gmail App Password)

Until this is done, `DIGISAFE_REQUIRE_VERIFICATION=false` keeps the site fully
usable — people register and sign in immediately, no code needed.

**Get the password** (your normal Google password will not work):

1. <https://myaccount.google.com/security> → switch on **2-Step Verification**
2. <https://myaccount.google.com/apppasswords> → name it `DigiSafe` → **Create**
3. Copy the 16 characters — shown once

**Then in Render → Environment**, type these in (never paste a password into a
chat, a document, or a commit):

| Key | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | your Gmail address |
| `SMTP_PASSWORD` | the 16 characters |
| `MAIL_FROM` | your Gmail address |
| `MAIL_FROM_NAME` | `DigiSafe` |
| `APP_BASE_URL` | your live URL, e.g. `https://digisafe-knust.onrender.com` |

**And delete `DIGISAFE_REQUIRE_VERIFICATION`** so verification switches back on.

Render restarts itself. The log should then read:

```
Email verification ON - codes will be sent via smtp.gmail.com as you@gmail.com.
```

Register on the live site with an address you can check. **Look in spam** on the
first message — if it lands there, mark it "not spam" before showing anyone.

---

## E. Every setting the platform understands

Only the ones marked **required** matter for a working deployment.

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | SQLite file | **Required in deployment.** Postgres connection string. `postgres://` and `postgresql://` are both accepted and rewritten automatically. |
| `SECRET_KEY` | dev fallback | **Required.** Signs the login tokens. Changing it only forces everyone to sign in again. |
| `DIGISAFE_AES_KEY` | dev fallback | **Required.** AES-256 key for evidence at rest. Exactly 32 characters. Must never change. |
| `PYTHON_VERSION` | — | `3.12.7`. Matches `.python-version`. |
| `DIGISAFE_REQUIRE_VERIFICATION` | `true` | `false` lets accounts be used immediately, with no email. |
| `APP_BASE_URL` | from the request | Address used in the emailed verification link. Unset, it is taken from the request, so tunnels and phones work unchanged. Setting it also blocks Host-header spoofing. |
| `SMTP_HOST` | *(unset)* | Mail server. Unset = codes printed to the log instead of sent. |
| `SMTP_PORT` | `587` | `587` with STARTTLS, or `465` with `SMTP_SSL=true`. `2525` avoids antivirus mail shields. |
| `SMTP_USER` | *(unset)* | The sending mailbox. |
| `SMTP_PASSWORD` | *(unset)* | App password — never the account password. |
| `SMTP_STARTTLS` | `true` | Upgrade the connection to TLS. |
| `SMTP_SSL` | `false` | Use implicit TLS instead — set with port 465. |
| `SMTP_TIMEOUT` | `20` | Seconds to wait on the mail server. |
| `MAIL_FROM` | `SMTP_USER` | Address recipients see. |
| `MAIL_FROM_NAME` | `DigiSafe` | Name recipients see. |
| `DIGISAFE_SYSTEM_TRUST` | `true` | Verify mail servers against the OS certificate store. Needed where an antivirus mail shield re-signs SMTP connections. `false` refuses any intercepted connection. |
| `VERIFICATION_TTL_MINUTES` | `30` | How long a code stays valid. |
| `VERIFICATION_RESEND_COOLDOWN` | `60` | Seconds between resends for one account. |
| `VERIFICATION_MAX_ATTEMPTS` | `8` | Wrong guesses before a code is cancelled. |
| `DIGISAFE_SEED_DEMO` | `false` | `true` seeds sample cases and one-click role logins. **Keep false on anything public** — those buttons hand any visitor an administrator session. |

---

## F. What to expect once it is live

- **First load after a quiet spell takes about a minute.** Render spins a free
  service down after 15 minutes with no traffic and wakes it on the next
  request. Nothing is lost. Open the site a few minutes before a demonstration
  so nobody else meets the cold start.
- **The URL never changes** — unlike the Cloudflare tunnel.
- **The tab shows the DigiSafe shield**, and the site can be added to a phone
  home screen as an app.

---

## G. Checking it worked

1. Open the URL — the home page loads
2. **Create an account** → you are signed in
3. **Submit Evidence** → a SHA-256 fingerprint and a threat level appear
4. **My Evidence** → the record is listed
5. Download the **PDF report** → it opens
6. With email on: the 6-digit code arrives in the inbox
