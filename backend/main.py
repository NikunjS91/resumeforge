import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import get_settings
from database import create_tables, SessionLocal
from seed import seed_ai_providers

from routers import auth, parse, analyze, tailor, score, export, providers

settings = get_settings()

# ─── FILE LOGGING ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("/tmp/resumeforge.log"),
        logging.StreamHandler(),
    ]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables + seed data
    create_tables()
    db = SessionLocal()
    try:
        seed_ai_providers(db)
    finally:
        db.close()
    print(f"✅ {settings.app_name} v{settings.app_version} started")
    yield
    # Shutdown (cleanup if needed)
    print("👋 ResumeForge shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered resume tailoring tool",
    lifespan=lifespan,
)

# CORS — allow React frontend on localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(auth.router)
app.include_router(parse.router)
app.include_router(analyze.router)
app.include_router(tailor.router)
app.include_router(score.router)
app.include_router(export.router)
app.include_router(providers.router)


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
