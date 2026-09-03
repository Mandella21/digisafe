from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import engine
from models.base import Base
from seed_data import seed_database
from routers import auth, evidence, admin, reports, pages

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables & seed data exist
    Base.metadata.create_all(bind=engine)
    seed_database()
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
