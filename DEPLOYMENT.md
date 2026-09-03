# DigiSafe: Deployment & Hosting Guide

This guide provides step-by-step instructions to run **DigiSafe** locally and deploy it online to **Render.com** (or Railway / Docker) before your Friday deadline.

---

## 1. Local Quickstart (Testing On Your Machine)

1. Open a terminal in this project folder:
   ```bash
   cd "mini project"
   ```

2. Install dependencies (first time only):
   ```bash
   pip install -r requirements.txt
   ```

3. Build the ML corpus and train the classifier (first time only):
   ```bash
   python ml_model/build_dataset.py
   python ml_model/train_model.py
   ```
   The trained models are committed to the repository, so this step is only
   needed if you change the corpus or the model. See `ML_MODEL.md`.

4. Run the application:
   ```bash
   python -m uvicorn main:app --reload
   ```

5. Open your browser and visit:
   ```
   http://127.0.0.1:8000
   ```

6. Create an account by signing up at `/auth`. A 6-digit verification code is
   sent to the address you register with, and the account cannot sign in until
   that code is entered at `/verify` (or the link in the same email is tapped).

   **No mail server is required to run this.** With SMTP unconfigured the code
   is printed in the terminal running the server, and a copy of the message is
   written to `storage/outbox/`.

   For other people to sign up with **their own** email addresses — which is the
   point of the feature — set up sending once:

   ```bash
   python tools/setup_email.py
   ```

   It asks which provider you send from, takes the credentials in your own
   terminal, writes `.env`, and sends a test message straight away. See
   [EMAIL_SETUP.md](EMAIL_SETUP.md) for how to get a Gmail App Password. To
   re-test later without changing anything:

   ```bash
   python tools/check_email.py your.own.address@gmail.com
   ```

   `DELIVERED` means every address anyone types at sign-up — Gmail, Yahoo,
   Outlook, `@st.knust.edu.gh` — will receive its own code. The server also
   states which mode it is in on startup, so you never have to guess.

7. *(Optional)* Bring back the pre-configured demonstration accounts:

   ```bash
   set DIGISAFE_SEED_DEMO=true        # Windows
   export DIGISAFE_SEED_DEMO=true     # macOS / Linux
   ```

   - **Victim Complainant**: `victim@digisafe.org` / `Victim@123`
   - **Police Officer**: `officer@police.gov.gh` / `Officer@123`
   - **System Administrator**: `admin@digisafe.org` / `Admin@123`

   These are seeded already verified, and 1-click login buttons appear on the
   sign-in page. They are **off by default**: on a live deployment those buttons
   would hand any visitor an administrator session.

---

## 1b. Reaching the site from your phone

**Same Wi-Fi as the computer** — bind to every interface instead of loopback:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Find the computer's IP (`ipconfig` on Windows, `ifconfig` on macOS/Linux) and
open `http://<that-ip>:8000` on the phone. `127.0.0.1` means "this machine
only", which is why the default will not work from another device.

**From anywhere** — double-click `START_LIVE_SITE.bat`. It starts the server and
opens a Cloudflare tunnel, then prints a public `https://....trycloudflare.com`
address that works on mobile data, on another network, on anyone's phone. Keep
that window open; closing it takes the site offline, and the address changes
each time you run it.

Verification links adapt automatically: the link inside the email is built from
the address the browser actually used, so it points at the tunnel when you are
tunnelled and at the LAN address when you are on Wi-Fi. The typed 6-digit code
works regardless of address, which is what keeps the flow intact when a tunnel
restarts with a new hostname.

---

## 2. Deploy Free to Render.com (Recommended - 5 Minutes)

Render provides free hosting for Python web services with HTTPS enabled out of the box.

### Step A: Push Project to GitHub
1. Initialize Git in the project directory (if not already done):
   ```bash
   git init
   git add .
   git commit -m "DigiSafe complete prototype release"
   ```
2. Create a new repository on [GitHub.com](https://github.com/new) named `digisafe`.
3. Push your code to GitHub:
   ```bash
   git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/digisafe.git
   git branch -M main
   git push -u origin main
   ```

### Step B: Launch on Render
1. Go to [dashboard.render.com](https://dashboard.render.com/) and sign up or log in.
2. Click **New +** -> **Web Service**.
3. Connect your GitHub account and select the `digisafe` repository.
4. Configure the service settings:
   - **Name**: `digisafe-knust` (or your preferred name)
   - **Region**: Frankfurt (EU) or Oregon (US)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
     That is the whole build. The trained models are committed, and
     `requirements.txt` pins scikit-learn, numpy, scipy and joblib to the exact
     versions that produced them, so the pickles load as-is.

     Do **not** add a training step here. Fitting the model on a 512 MB free
     instance risks an out-of-memory build failure, and the version pins already
     give the guarantee that retraining was there to provide. The database is
     created and seeded automatically at start-up.
   - **Start Command**:
     ```bash
     uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: **Free**
5. Under **Environment**, add these variables:

   | Key | Value |
   |---|---|
   | `PYTHON_VERSION` | `3.12.7` |
   | `SECRET_KEY` | any long random string (signs the JWTs) |
   | `DIGISAFE_AES_KEY` | exactly 32 characters (AES-256 evidence encryption) |
   | `APP_BASE_URL` | your live address, e.g. `https://digisafe-knust.onrender.com` |
   | `SMTP_HOST` | e.g. `smtp.gmail.com` (optional - see below) |
   | `SMTP_PORT` | `587` |
   | `SMTP_USER` | the sending address |
   | `SMTP_PASSWORD` | an app password, never your account password |
   | `MAIL_FROM` | the sending address |

   The `SMTP_*` group is optional. Leave it out and the platform still works -
   verification codes go to the Render service log instead of an inbox, which is
   enough to demonstrate the flow but not enough for real users, who cannot read
   your logs. [EMAIL_SETUP.md](EMAIL_SETUP.md) walks through getting a Gmail app
   password in about three minutes.

   Set `APP_BASE_URL` once the service has its final address. Leaving it unset
   still works - the link is then taken from each request - but pinning it also
   stops a forged `Host` header from putting another domain into a verification
   link.

   `DIGISAFE_AES_KEY` **must stay the same across deploys**. Changing it makes
   every evidence record already in the database undecryptable — for this system
   that means permanently destroying a victim's evidence. If you leave it unset
   the app still runs on a built-in development key, which is fine for the demo
   but is not safe for real victim data.

6. **Instance Type**: Free. Then click **Create Web Service**.
7. Render builds the service, trains the model, and assigns a live public HTTPS
   URL (e.g. `https://digisafe-knust.onrender.com`). The first build takes
   roughly 3-5 minutes, mostly installing scikit-learn and SciPy.

### Known free-tier behaviour (say this before the panel notices it)

- **The service sleeps after 15 minutes of inactivity.** The first request after
  that takes ~40-60 seconds to wake. **Open your URL 2-3 minutes before you
  present** so it is warm when the panel looks at it.
- **Disk is ephemeral.** Uploaded evidence files, generated PDFs, and the SQLite
  database are wiped on each redeploy, and the demo accounts and sample cases are
  re-seeded automatically at start-up. This is expected for a free-tier prototype
  and matches the scope in Section 6 of your proposal. A production deployment
  would use Render's managed PostgreSQL plus object storage — worth saying as
  your "future work" answer if asked about scalability.

---

## 2b. Deploy free to Hugging Face Spaces (no credit card, ever)

Use this if Render asks for a card. Hugging Face Spaces is free permanently,
never asks for payment details, and gives a permanent public HTTPS URL. For a
machine-learning project it is arguably the more appropriate home anyway, since
Spaces is where ML demos are normally published.

The repository is already configured for it: the YAML block at the top of
`README.md` tells Spaces this is a Docker Space listening on port 8000, and the
`Dockerfile` runs as UID 1000, which Spaces requires.

### Step A: Create the Space

1. Sign up at [huggingface.co/join](https://huggingface.co/join) — email and
   password only, no card.
2. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
3. **Space name**: `digisafe`
4. **License**: MIT
5. **Space SDK**: choose **Docker** -> **Blank**
6. **Hardware**: `CPU basic - 2 vCPU, 16 GB` (the free option)
7. **Visibility**: Public
8. Click **Create Space**.

### Step B: Push the code to it

Hugging Face gives you a git URL like
`https://huggingface.co/spaces/<your-username>/digisafe`. Add it as a second
remote alongside GitHub and push:

```bash
git remote add hf https://huggingface.co/spaces/<your-username>/digisafe
git push hf main
```

When git asks for a password, use a **Hugging Face access token**, not your
account password: [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
-> **New token** -> type **Write**. Paste the token as the password.

The Space builds automatically. Watch the **Logs** tab; the first build takes a
few minutes while it installs scikit-learn and SciPy.

Your site will be live at:

```
https://<your-username>-digisafe.hf.space
```

### Step C: Set the encryption key

In the Space, go to **Settings** -> **Variables and secrets** -> **New secret**:

| Name | Value |
|---|---|
| `DIGISAFE_AES_KEY` | a 32-character string |
| `SECRET_KEY` | any long random string |

Add these as **Secrets**, not public Variables. As with any host, never change
`DIGISAFE_AES_KEY` after evidence has been stored — doing so makes existing
records permanently undecryptable.

### What to expect on the free tier

- The Space sleeps after about 48 hours of no visitors and wakes on the next
  request. That is far more forgiving than Render's 15 minutes, but still open
  the URL a few minutes before you present.
- Storage is ephemeral, exactly as on Render's free tier: uploaded files, the
  SQLite database and generated PDFs reset when the Space restarts, and the demo
  accounts and sample cases are re-seeded automatically at start-up. This is
  consistent with the prototype scope declared in Section 6 of the proposal.

---

## 3. Alternative 1-Click Deploy via Railway.app

1. Visit [railway.app](https://railway.app/) and sign in with GitHub.
2. Click **New Project** -> **Deploy from GitHub repo** -> Select `digisafe`.
3. Railway automatically detects the `Procfile` and `requirements.txt`.
4. Add a domain under **Settings** -> **Networking** -> **Generate Domain**.
5. Your app is immediately live!

---

## 4. Docker Deployment

If deploying to a VPS (Ubuntu/Debian) or Docker host:
```bash
docker build -t digisafe-app .
docker run -d -p 8000:8000 --name digisafe digisafe-app
```
Access at `http://localhost:8000`.

---

## 5. Defense & Demonstration Checklist

During your project defense with your supervisor (Prof. Frimpong Twum) and panel:
0. **Registration & Email Verification (Section 3.8.2)**:
   - Beforehand, run `python tools/check_email.py <your address>` and confirm
     it says `DELIVERED`, so mail is known to work before anyone is watching
   - Sign up at `/auth` with a real address, on a phone if you like — ask a
     panel member for theirs and let the code arrive on their own device
   - Show that `/api/auth/login` refuses the account at this point, *with the
     correct password* — an unverified address is an unowned address
   - Enter the emailed code (or tap the link) and watch the same login succeed
   - Point out that the code is single-use, expires, is compared in constant
     time, is cancelled after 8 wrong guesses, and is bound to one account, so
     one person's code cannot activate another's
   - Open `/audit` afterwards to show `USER_REGISTER` and `EMAIL_VERIFIED`
     recorded against the new account
1. **Victim Workflow**:
   - Log in using the account you just verified
   - Go to **Submit Evidence**: enter a threat message (e.g., WhatsApp threat) and optional screenshot
   - Observe instant SHA-256 digital fingerprint and ML threat score (`Critical` or `High`)
   - Go to **Tracking Dashboard** and download the **Court-Admissible PDF Report**
2. **Cryptographic Integrity & Tamper Detection (Section 4.1.8)**:
   - Switch to **Police Officer** or **Admin**
   - Click **Verify** on any case to show mathematical integrity match
   - Click **Simulate Tampering** (Section 4.1.8) on the Admin dashboard to show the panel that modifying database ciphertext immediately flags the case as `COMPROMISED` and triggers a high-severity alert!
3. **Audit Trail (Section 3.15.1)**:
   - Open `/audit` to show the chronological audit log of all logins, submissions, and integrity checks
   - Click **Export to CSV** to demonstrate compliance with digital evidence standards
