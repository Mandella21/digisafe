from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import engine, ensure_schema
from models.base import Base
from seed_data import seed_database
from services import ml_service
from routers import auth, evidence, admin, reports, pages

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
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

# Include Routers
app.include_router(pages.router, tags=["Web Pages"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(evidence.router, prefix="/api/evidence", tags=["Evidence Capture & Hashing"])
app.include_router(admin.router, prefix="/api/admin", tags=["Law Enforcement & Admin"])
app.include_router(reports.router, prefix="/api/reports", tags=["Forensic Evidence Reports"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
