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

1. **Capture** — submit a threatening message, URL, or screenshot.
2. **Timestamp and fingerprint** — a SHA-256 hash is generated at the moment of
   capture and stored immutably alongside the record.
3. **Encrypt** — the content is encrypted with AES-256-CBC (unique IV per
   record) before it touches the database.
4. **Classify** — a trained scikit-learn model detects abusive, threatening or
   harassing content and assigns a severity band.
5. **Escalate** — high-severity cases raise an alert for administrators and law
   enforcement officers.
6. **Report** — a structured, court-presentable PDF evidence report is generated
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

The database is created and seeded automatically on first start. The trained
models are committed, so no training step is needed to run the project.

### Demonstration accounts

| Role | Email | Password |
|---|---|---|
| Victim / Complainant | `victim@digisafe.org` | `Victim@123` |
| Police Officer | `officer@police.gov.gh` | `Officer@123` |
| System Administrator | `admin@digisafe.org` | `Admin@123` |

One-click login buttons for each are on the sign-in page.

### Account roles

**Public sign-up always creates a victim account.** The role field in a
registration request is ignored by the server. Honouring it would let anyone
register as an administrator and read every victim's evidence, so privileged
accounts can never be self-assigned.

Administrator and law enforcement officer accounts are provisioned by an
existing administrator:

```
POST /api/admin/users     { full_name, email, password, role: "admin" | "officer" }
```

Only an administrator may call it — officers are deliberately not allowed to
create further staff accounts. Every such creation is written to the audit log.
This matches Section 3.6, which makes the System Administrator responsible for
managing user accounts.

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

12 tests covering password hashing and JWTs, SHA-256 hashing, AES encryption
round-trip, ML classification and severity banding, privilege-escalation
regression (public sign-up cannot self-assign a privileged role), admin-only
staff provisioning, checksum tamper detection, and PDF report generation. The
suite creates its own fixtures and runs on a clean checkout with no database
present.

---

## Layout

```
main.py                  FastAPI entrypoint, startup lifespan
core/                    config, database session, JWT + bcrypt utilities
models/                  SQLAlchemy ORM: users, evidence, hash_record,
                         ml_classification, report, audit_log, alert
schemas/                 Pydantic request/response models
routers/                 auth, evidence, admin, reports, pages
services/                hashing, encryption, ML inference, PDF generation
ml_model/                corpus builder, preprocessing, training, saved models
templates/  static/      Jinja2 templates, CSS, JavaScript
tests/                   unittest suite
```

---

## Documentation

- **[ML_MODEL.md](ML_MODEL.md)** — model architecture, corpus provenance,
  evaluation methodology, measured results, and stated limitations.
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — local setup, Render deployment, Docker,
  and the demonstration checklist.

---

## Scope

This is an academic prototype, developed and demonstrated using sample and
simulated data. It does not scrape social media platforms, integrate with law
enforcement databases, or handle real victim data. The classifier's reported
accuracy is measured on a curated synthetic corpus and is not a claim of
real-world harassment-detection accuracy; the automated classification is
investigative decision-support, not evidence. The cryptographic integrity
guarantee is independent of it.
