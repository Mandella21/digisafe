---
title: DigiSafe
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Digital safety and evidence protection for online abuse victims
---

<!--
  The block above is Hugging Face Spaces configuration. Spaces reads it to know
  this is a Docker Space and which port the container listens on. GitHub renders
  it as a small table at the top of the page, which is harmless. Removing it
  breaks the Hugging Face deployment; see DEPLOYMENT.md.
-->

# DigiSafe

**Design and Implementation of a Digital Safety and Record Protection System for
Online Abuse Victims Using Python and Machine Learning**

Kwame Nkrumah University of Science and Technology — College of Science,
Department of Computer Science. BSc. Computer Science individual mini project,
2025/2026. Supervisor: Prof. Frimpong Twum.

---

## What it does

Victims of online abuse usually bring law enforcement informal screenshots,
which carry no metadata, no timestamp authentication and no integrity proof, and
are easily dismissed as fabricated. DigiSafe lets a victim capture that evidence
in a form that survives scrutiny:

1. **Register** — sign up with an email address and confirm it with a code sent
   to that inbox. The account does nothing until the address is proven.
2. **Capture** — submit a threatening message, URL, or screenshot.
3. **Timestamp and fingerprint** — a SHA-256 hash is generated at the moment of
   capture and stored immutably alongside the record.
4. **Encrypt** — the content is encrypted with AES-256-CBC (unique IV per
   record) before it touches the database.
5. **Classify** — a trained scikit-learn model detects abusive, threatening or
   harassing content and assigns a severity band.
6. **Escalate** — high-severity cases raise an alert for administrators and law
   enforcement officers.
7. **Report** — a structured, court-presentable PDF evidence report is generated
   on demand.

Any later alteration of a stored record is caught by re-computing the checksum
and comparing it with the one taken at submission. The system does not silently
repair a mismatch — that would itself destroy the record's legal value. It flags
the record as compromised, raises an alert, and preserves both checksums so the
discrepancy becomes part of the auditable evidence trail.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI |
| Database | SQLAlchemy ORM over SQLite |
| Security | `hashlib` (SHA-256), `cryptography` (AES-256-CBC), bcrypt, JWT |
| Machine learning | scikit-learn (TF-IDF, Multinomial NB, LinearSVC), NLTK |
| Reports | fpdf2 |
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5, Jinja2 templates |

---

## Running it locally

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Then open <http://127.0.0.1:8000>.

The database is created automatically on first start. The trained models are
committed, so no training step is needed to run the project.

### Signing up, and email verification

A new account is created by signing up on `/auth` and is **inert until the email
address is confirmed**. Registration sends a 6-digit code to the address given;
entering it on `/verify` — or tapping the link in the same email — activates the
account and signs the person in. Until then, `/api/auth/login` returns 403 even
with the correct password.

This is what stops someone registering under an address they do not control.
On a platform holding abuse evidence that is not a formality: without it, an
abuser could register as the person they are targeting and be handed that
person's own case tracking.

#### Getting codes into real inboxes

For other people to sign up — on their own phones, with their own Gmail, Yahoo,
Outlook or KNUST addresses — DigiSafe needs one mailbox to send *from*:

```bash
copy .env.example .env      # then fill in the SMTP_ lines
python tools/check_email.py your.own.address@gmail.com
```

`check_email.py` sends one real message and says exactly what happened,
translating SMTP's terse errors into the specific thing to fix. Run it before a
demonstration rather than discovering a bad password during a live sign-up.
[EMAIL_SETUP.md](EMAIL_SETUP.md) walks through getting a Gmail App Password.

`.env` is read automatically at startup and is excluded by `.gitignore`, so no
credential is ever committed — and unlike `set`/`export`, it survives closing
the terminal and double-clicking a start script.

**The project still runs with none of this.** Unconfigured, the code is printed
in the server console and the message saved to `storage/outbox/`, and the
interface says exactly that rather than telling someone to check an inbox
nothing was sent to. Startup states which mode you are in:

```
Email verification ON - codes will be sent via smtp.gmail.com as you@gmail.com.
```

### Using it from a phone

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Binding to `0.0.0.0` rather than `127.0.0.1` makes the site reachable from any
device on the same Wi-Fi at `http://<your-computer-ip>:8000`. For an address
that works from anywhere, run `START_LIVE_SITE.bat`, which opens a public
Cloudflare tunnel and prints an `https://....trycloudflare.com` link.

Verification links are built from the address the browser actually used, so the
button in the email works over a tunnel, over Wi-Fi, or on localhost with no
reconfiguration. The typed code works regardless — which matters because a
tunnel hands out a new address every restart.

### Demonstration accounts

| Role | Email | Password |
|---|---|---|
| Victim / Complainant | `victim@digisafe.org` | `Victim@123` |
| Police Officer | `officer@police.gov.gh` | `Officer@123` |
| System Administrator | `admin@digisafe.org` | `Admin@123` |

One-click login buttons for each are on the sign-in page.

These exist only when `DIGISAFE_SEED_DEMO=true`; a default deployment starts
with an empty database and no demonstration accounts. Seeded accounts are
created already verified, since nobody can read mail at `digisafe.org`.

### Account roles

**Public sign-up always creates a victim account.** The role field in a
registration request is ignored by the server. Honouring it would let anyone
register as an administrator and read every victim's evidence, so privileged
accounts can never be self-assigned.

Public sign-up additionally requires the email address to be confirmed before
the account can be used at all — see above.

Administrator and law enforcement officer accounts are provisioned by an
existing administrator:

```
POST /api/admin/users     { full_name, email, password, role: "admin" | "officer" }
```

Only an administrator may call it — officers are deliberately not allowed to
create further staff accounts. Every such creation is written to the audit log.
This matches Section 3.6, which makes the System Administrator responsible for
managing user accounts. Staff accounts start verified: their owner was
identified in person by the administrator issuing the account, so there is no
inbox left to prove.

### Retraining the classifier

```bash
python ml_model/build_dataset.py
python ml_model/train_model.py
```

Deterministic — it reproduces the published metrics exactly.

### Tests

```bash
python -m unittest discover -s tests -v
```

20 tests covering password hashing and JWTs, SHA-256 hashing, AES encryption
round-trip, ML classification and severity banding, privilege-escalation
regression (public sign-up cannot self-assign a privileged role), admin-only
staff provisioning, email verification, checksum tamper detection, and PDF
report generation.

The verification tests deserve naming individually, since they are what makes
the sign-up flow more than decoration: an unverified account cannot sign in
even with the right password; a code is single-use; the emailed link works and
is likewise single-use; a code is bound to one account, so one person's code
cannot activate another's; resend answers identically for an unknown address;
the message really does carry the code and the link; the SMTP branch that runs
in production is exercised rather than only its offline fallback; and a failed
send leaves the account recoverable instead of stranded.

The suite creates its own fixtures, runs against a separate database file, and
works on a clean checkout with no database present.

---

## Layout

```
main.py                  FastAPI entrypoint, startup lifespan
core/                    config, database session, JWT + bcrypt utilities
models/                  SQLAlchemy ORM: users, evidence, hash_record,
                         ml_classification, report, audit_log, alert
schemas/                 Pydantic request/response models
routers/                 auth, evidence, admin, reports, pages
services/                hashing, encryption, ML inference, PDF generation,
                         verification email
ml_model/                corpus builder, preprocessing, training, saved models
tools/                   check_email.py - mail delivery diagnostic
templates/  static/      Jinja2 templates, CSS, JavaScript
storage/                 encrypted evidence, generated reports, mail outbox
tests/                   unittest suite
```

---

## Documentation

- **[ML_MODEL.md](ML_MODEL.md)** — model architecture, corpus provenance,
  evaluation methodology, measured results, and stated limitations.
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — local setup, Render deployment, Docker,
  and the demonstration checklist.
- **[EMAIL_SETUP.md](EMAIL_SETUP.md)** — pointing the platform at a real mail
  server so verification codes reach people's inboxes, and what to check when
  they do not.
- **[.env.example](.env.example)** — every setting the platform reads, with an
  explanation of each. Copy to `.env` and fill in.

---

## Scope

This is an academic prototype, developed and demonstrated using sample and
simulated data. It does not scrape social media platforms, integrate with law
enforcement databases, or handle real victim data. The classifier's reported
accuracy is measured on a curated synthetic corpus and is not a claim of
real-world harassment-detection accuracy; the automated classification is
investigative decision-support, not evidence. The cryptographic integrity
guarantee is independent of it.
