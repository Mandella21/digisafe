# Cap the numerical libraries to one thread each, BEFORE anything imports
# numpy - the value is read once, at import, and ignored afterwards.
#
# OpenBLAS allocates per-thread working buffers sized to the CPU count. On a
# 512 MB instance, or on a machine whose commit limit is already tight, that
# allocation fails and the process dies with a bare MemoryError during import -
# nothing to do with the size of the data, and confusing to diagnose. This
# project's models are small enough that multi-threaded BLAS buys nothing
# measurable, so the memory is pure cost.
import os

for _threads_var in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_threads_var, "1")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings, DOTENV_PATH, DOTENV_LOADED
from core.database import engine, ensure_schema
from models.base import Base
from seed_data import seed_database
from services import ml_service, email_service
from routers import auth, evidence, admin, reports, pages


def _report_mail_configuration():
    """Say, at startup, whether verification codes will actually be emailed.

    The difference matters before anyone signs up, not after. Configured, every
    person who registers gets their own code in their own inbox. Unconfigured,
    the codes appear only in this console - fine while developing, useless the
    moment someone registers from their own phone, because they cannot see this
    window. Printing it here means the answer is known before a demonstration
    rather than discovered during one.
    """
    if DOTENV_LOADED:
        print(f"Configuration loaded from {DOTENV_PATH.name} ({DOTENV_LOADED} setting(s)).")

    if not settings.REQUIRE_EMAIL_VERIFICATION:
        print("Email verification is OFF (DIGISAFE_REQUIRE_VERIFICATION). "
              "Accounts are usable as soon as they are created.")
        return

    if email_service.is_smtp_configured():
        print(f"Email verification ON - codes will be sent via {settings.SMTP_HOST} "
              f"as {settings.MAIL_FROM}.")
    else:
        print("Email verification ON, but NO MAIL SERVER is configured.")
        print("  Verification codes will be printed HERE and saved to storage/outbox/.")
        print("  Anyone registering from their own device will not be able to see them.")
        print("  To send real email: copy .env.example to .env, then see EMAIL_SETUP.md.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables & seed data exist
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    if settings.SEED_DEMO_DATA:
        seed_database()
        print("Demonstration data seeded (DIGISAFE_SEED_DEMO is on).")
    else:
        print("Running with a real, empty database. Users are created by signing up.")
    _report_mail_configuration()
    # Load the trained scikit-learn models once, up front, so the first victim
    # to submit evidence does not pay the model-loading latency (Section 3.10,
    # Performance: submissions must respond within three seconds).
    if ml_service.warmup():
        print(f"ML classifier ready ({ml_service.MODEL_VERSION}).")
    else:
        print("WARNING: ML models failed to load. Run: python ml_model/train_model.py")
    yield

app = FastAPI(
    title="DigiSafe API & Web Platform",
    description="Digital Safety and Record Protection System for Online Abuse Victims",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration (Listing 4.2)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # The browser branches on this header to tell "wrong password" apart from
    # "correct password, email not confirmed yet" and open the verification
    # screen instead of a dead end. Custom headers are invisible to
    # cross-origin JavaScript unless they are named here, so a front end served
    # from anywhere but this origin would silently lose that distinction.
    expose_headers=["X-DigiSafe-Reason"],
)

# Mount Static & Storage Assets
app.mount("/static", StaticFiles(directory="static"), name="static")
# storage/ is deliberately NOT mounted.
#
# It previously was, which served every file under it to anyone who could name
# one - no login, no ownership check. That directory holds victims' evidence
# attachments, generated forensic reports, and (when no mail server is
# configured) copies of verification emails containing live sign-up codes.
# Report filenames follow a predictable pattern, so "unlisted" was never the
# same as "private".
#
# Everything under it is now served through an authenticated endpoint that
# checks who is asking: attachments via /api/evidence/{id}/attachment, reports
# via /api/reports/download/{id}.

# Include Routers
app.include_router(pages.router, tags=["Web Pages"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(evidence.router, prefix="/api/evidence", tags=["Evidence Capture & Hashing"])
app.include_router(admin.router, prefix="/api/admin", tags=["Law Enforcement & Admin"])
app.include_router(reports.router, prefix="/api/reports", tags=["Forensic Evidence Reports"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
