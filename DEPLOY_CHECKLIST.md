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

## Choosing a host

| Host | Free for this app? | Notes |
|---|---|---|
| **Render + Neon** | **Yes** | **Recommended.** Configured in `render.yaml`. The web service needs no card; use Neon for the database, which also needs none. A long-running process, so the models load once and stay loaded. 512 MB RAM, sleeps after 15 min idle. |
| **Vercel** | **Yes** | Configured in `vercel.json` + `api/index.py`. Hobby needs no card, 2 GB memory, and Python functions get a 500 MB bundle limit against this app's 245 MB. But it is serverless: a cold start re-imports scikit-learn, so the first request after a quiet period is slow. |
| ~~Hugging Face Spaces~~ | **No longer** | Docker Spaces now require a PRO plan for personal accounts. Only Static Spaces are free, and those cannot run Python. The `Dockerfile` still works if you have PRO or deploy it elsewhere. |
| ~~Firebase~~ | **No** | App Hosting supports Next.js and Angular, not Python, and requires the Blaze plan — a credit card — regardless. |

Every one of them needs the Neon database from section A. Sections C and D
below apply whichever you choose; only the place you type the variables differs.

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

### Four variables. That is the whole list.

| Key | Value |
|---|---|
| `DATABASE_URL` | the Neon connection string from section A |
| `SECRET_KEY` | see generator below |
| `DIGISAFE_AES_KEY` | see generator below — **exactly 32 characters** |
| `DIGISAFE_REQUIRE_VERIFICATION` | `false` *(until email works — see section D)* |

On **Render** add `PYTHON_VERSION` = `3.12` as a fifth. Vercel reads
`.python-version` from the repository instead and ignores that variable.

Ignore every other name you see in section E or in `.env.example`. Those are
reference material, and each already has a default that works.

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

## E. Reference — NOT a list to fill in

**You do not set these.** Every one has a working default; the table exists so
that when you later want to change how long a code lasts, or which mail server
is used, you know the name to use.

The only variables you set are the four in section C, plus the email group in
section D when you have a password. A deployment with exactly those four was
tested end to end: register, sign in, submit evidence, SHA-256 fingerprint,
Critical threat classification, PDF report, and the browser icon — all working,
with none of the rest of this table set to anything.

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

## E2. Deploying to Vercel instead

1. <https://vercel.com/signup> → **Continue with GitHub** (Hobby plan, no card)
2. **Add New… → Project** → import `Mandella21/digisafe`
3. Framework Preset: **Other**. Leave build and output settings empty —
   `vercel.json` already describes everything.
4. Expand **Environment Variables** and add the same five from section C.
5. **Deploy**

You get `https://digisafe-<something>.vercel.app`, permanently.

`api/index.py` is the entrypoint: Vercel does not run `uvicorn`, it imports an
ASGI app from under `api/`. That file just puts the project root on `sys.path`
and re-exports the same application every other host runs.

**The trade-off:** Vercel is serverless, so an idle function is torn down and
the next request pays for reloading scikit-learn and the models. On Render or
Spaces the process stays alive between requests. If the first hit after a quiet
period feels slow, that is why — and it is the reason a long-running host suits
this project better.

---

## E3. Deploying to Hugging Face Spaces instead

Full steps are in [DEPLOYMENT.md](DEPLOYMENT.md) section 2b. In short:

1. <https://huggingface.co/join> — email and password, no card
2. <https://huggingface.co/new-space> → name `digisafe` → SDK **Docker → Blank**
   → **CPU basic** (free) → Public → Create
3. Push to it:

   ```bash
   git remote add hf https://huggingface.co/spaces/YOUR-USERNAME/digisafe
   git push hf main
   ```

   Use a **write token** from <https://huggingface.co/settings/tokens> as the
   password, not your account password.
4. Space → **Settings → Variables and secrets** → add the same five from
   section C as **Secrets**.

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
