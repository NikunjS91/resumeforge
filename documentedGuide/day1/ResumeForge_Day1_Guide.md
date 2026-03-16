# ResumeForge — Day 1 Complete Build Guide
## Database Schema + Project Foundation

> **For the code agent:** Read this entire document before writing a single line of code.
> Follow every section in order. Do not skip steps. Do not improvise on structure.

---

## Overview

**What you are building today:**
The complete project foundation for ResumeForge — an AI-powered resume tailoring tool.

Day 1 has two goals:
1. Set up the full project folder structure (backend + frontend scaffolding)
2. Implement the complete SQLite database schema with all 6 tables

**You are NOT building any AI or parsing logic today.** That comes in later days.
Today is purely: structure, database, and a working FastAPI server that connects to it.

---

## Tech Stack (Do Not Deviate)

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI (Python) |
| Database | SQLite |
| ORM | SQLAlchemy (with declarative base) |
| Migrations | Alembic |
| Password hashing | bcrypt via passlib |
| Auth tokens | JWT via python-jose |
| Python version | 3.11+ |
| Package manager | pip with requirements.txt |
| Frontend (scaffold only) | React + Vite + TailwindCSS |
| Frontend package manager | npm |

---

## Part 1 — Project Folder Structure

Create this **exact** folder structure inside `/Users/nikunjshetye/Project/ResumeForge/`.
Do not rename folders. Do not add extra folders at this stage.

```
ResumeForge/
│
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── config.py
│   ├── requirements.txt
│   ├── .env
│   ├── alembic.ini
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── resume.py
│   │   ├── resume_section.py
│   │   ├── job.py
│   │   ├── tailoring_session.py
│   │   └── ai_provider_config.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── resume.py
│   │   ├── job.py
│   │   └── tailoring_session.py
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── parse.py
│   │   ├── analyze.py
│   │   ├── tailor.py
│   │   ├── score.py
│   │   ├── export.py
│   │   └── providers.py
│   │
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── parser/
│   │   │   ├── __init__.py
│   │   │   ├── resume_parser.py
│   │   │   └── section_extractor.py
│   │   ├── analyzer/
│   │   │   ├── __init__.py
│   │   │   └── job_analyzer.py
│   │   ├── tailor/
│   │   │   ├── __init__.py
│   │   │   ├── tailor_agent.py
│   │   │   └── prompts/
│   │   │       ├── tailor_resume.md
│   │   │       └── analyze_job.md
│   │   ├── scorer/
│   │   │   ├── __init__.py
│   │   │   └── ats_scorer.py
│   │   ├── exporter/
│   │   │   ├── __init__.py
│   │   │   └── pdf_exporter.py
│   │   └── ai_provider/
│   │       ├── __init__.py
│   │       └── provider_manager.py
│   │
│   ├── migrations/
│   │   └── (alembic will generate files here)
│   │
│   └── data/
│       ├── resumes/
│       │   └── .gitkeep
│       ├── jobs/
│       │   └── .gitkeep
│       └── resumeforge.db
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ResumeUploader.jsx
│   │   │   ├── JobInput.jsx
│   │   │   ├── TailoredResume.jsx
│   │   │   ├── ATSScoreCard.jsx
│   │   │   └── ProviderSelector.jsx
│   │   ├── pages/
│   │   │   ├── Home.jsx
│   │   │   └── History.jsx
│   │   ├── api/
│   │   │   └── client.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── public/
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── .env
├── .gitignore
├── docker-compose.yml
└── README.md
```

**Important rules for all module files not built today:**
- Every module file that is NOT being implemented today must exist as a file with a single comment: `# TODO: Implement in Day X`
- Do NOT leave empty files. Empty `__init__.py` files are fine.
- Router files not implemented today get a stub: a FastAPI router object with a single placeholder GET that returns `{"status": "not implemented yet"}`

---

## Part 2 — Environment Setup

### Step 1: Create and activate a virtual environment

```bash
cd /Users/nikunjshetye/Project/ResumeForge/backend
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Create requirements.txt

Write this exact content to `backend/requirements.txt`:

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
alembic==1.13.1
pydantic==2.7.1
pydantic-settings==2.2.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
python-dotenv==1.0.1
pdfplumber==0.11.0
python-docx==1.1.2
reportlab==4.2.0
httpx==0.27.0
```

Install all dependencies:

```bash
pip install -r requirements.txt
```

### Step 3: Create the .env file

Write this to `backend/.env`:

```
APP_NAME=ResumeForge
APP_VERSION=1.0.0
DEBUG=True
DATABASE_URL=sqlite:///./data/resumeforge.db
SECRET_KEY=your-secret-key-change-this-in-production-minimum-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# AI Provider API Keys (fill these in later)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# File storage
UPLOAD_DIR=./data/resumes
MAX_FILE_SIZE_MB=10
```

**Also create a root-level `.env`** at `ResumeForge/.env` with the same content (frontend will reference it).

### Step 4: Create .gitignore

Write this to `ResumeForge/.gitignore`:

```
# Python
__pycache__/
*.py[cod]
*.pyo
venv/
.env
*.egg-info/

# Database
*.db
*.sqlite3

# Uploaded files
backend/data/resumes/*
backend/data/jobs/*
!backend/data/resumes/.gitkeep
!backend/data/jobs/.gitkeep

# Node
node_modules/
dist/
.DS_Store

# IDE
.vscode/
.idea/
*.swp
```

---

## Part 3 — Configuration (config.py)

Write this to `backend/config.py`:

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ResumeForge"
    app_version: str = "1.0.0"
    debug: bool = True

    database_url: str = "sqlite:///./data/resumeforge.db"

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    upload_dir: str = "./data/resumes"
    max_file_size_mb: int = 10

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

---

## Part 4 — Database Setup (database.py)

Write this to `backend/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}  # Required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency — yields a DB session per request,
    closes it after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Creates all tables from SQLAlchemy models.
    Called once on application startup.
    """
    Base.metadata.create_all(bind=engine)
```

---

## Part 5 — Database Models

Implement each model file exactly as specified below.
All models live in `backend/models/`.

---

### models/__init__.py

```python
from .user import User
from .resume import Resume
from .resume_section import ResumeSection
from .job import Job
from .tailoring_session import TailoringSession
from .ai_provider_config import AIProviderConfig
```

---

### models/user.py

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    resumes = relationship("Resume", back_populates="owner", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="owner", cascade="all, delete-orphan")
    tailoring_sessions = relationship("TailoringSession", back_populates="owner", cascade="all, delete-orphan")
```

---

### models/resume.py

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)                   # User-chosen name e.g. "Google SWE Resume"
    original_filename = Column(String, nullable=False)      # Original uploaded filename
    file_format = Column(String, nullable=False)            # "pdf" or "docx"
    file_path = Column(String, nullable=False)              # Relative path on disk
    raw_text = Column(Text, nullable=False)                 # Full plain text extracted from file
    structured_json = Column(Text, nullable=False)          # JSON blob of all parsed sections
    llm_extras_json = Column(Text, nullable=True)           # LLM-detected extra sections beyond standard 7
    char_count = Column(Integer, nullable=False, default=0)
    page_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="resumes")
    sections = relationship("ResumeSection", back_populates="resume", cascade="all, delete-orphan")
    tailoring_sessions = relationship("TailoringSession", back_populates="resume", cascade="all, delete-orphan")
```

---

### models/resume_section.py

```python
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ResumeSection(Base):
    __tablename__ = "resume_sections"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)

    # Section identity
    # Valid values: contact | summary | experience | education | skills | projects | certifications | llm_detected
    section_type = Column(String, nullable=False)
    section_label = Column(String, nullable=False)          # Heading as it appeared in the file e.g. "WORK EXPERIENCE"

    # Content storage — dual format
    content_text = Column(Text, nullable=False)             # Plain text of this section
    content_json = Column(Text, nullable=False)             # Structured JSON e.g. list of jobs with bullets

    # Formatting metadata extracted from PDF/DOCX
    # JSON array: [{ "text": "...", "bold": true, "italic": false, "font": "Calibri", "size": 12, "x": 72, "y": 140 }]
    formatting_json = Column(Text, nullable=False, default="[]")

    # Position in original document (1 = first section, 2 = second, etc.)
    position_index = Column(Integer, nullable=False, default=0)

    # Edit tracking — user can optionally review and edit parsed content
    is_edited = Column(Boolean, default=False, nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    resume = relationship("Resume", back_populates="sections")
```

---

### models/job.py

```python
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Auto-generated name: "Google — SWE Intern — Mar 2026"
    auto_name = Column(String, nullable=False)

    # Full pasted job description text
    jd_raw_text = Column(Text, nullable=False)

    # LLM-extracted metadata
    company_name = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    location = Column(String, nullable=True)
    is_remote = Column(Boolean, nullable=True)

    # Intern | Junior | Mid | Senior | Lead
    seniority_level = Column(String, nullable=True)

    # JSON arrays: ["Python", "FastAPI", "AWS", "Docker"]
    required_skills_json = Column(Text, nullable=True, default="[]")
    nicetohave_skills_json = Column(Text, nullable=True, default="[]")

    # e.g. "$80,000 — $100,000" if mentioned in JD
    salary_range = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="jobs")
    tailoring_sessions = relationship("TailoringSession", back_populates="job", cascade="all, delete-orphan")
```

---

### models/tailoring_session.py

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class TailoringSession(Base):
    __tablename__ = "tailoring_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Foreign keys to three parent tables
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    # AI output
    tailored_text = Column(Text, nullable=False)            # Full AI-generated tailored resume text
    tailored_json = Column(Text, nullable=False)            # Structured JSON of tailored sections

    # ATS scoring
    ats_score = Column(Integer, nullable=False, default=0)  # 0-100
    matched_keywords_json = Column(Text, nullable=False, default="[]")   # Keywords found
    missing_keywords_json = Column(Text, nullable=False, default="[]")   # Keywords still missing
    # e.g. { "skills_match": 88, "experience_relevance": 72, "keyword_density": 80 }
    score_breakdown_json = Column(Text, nullable=False, default="{}")

    # AI provider tracking
    # Values: "ollama" | "claude" | "openai" | "gemini"
    ai_provider = Column(String, nullable=False)
    # Exact model used e.g. "mistral:7b", "gpt-4o", "claude-sonnet-4-6"
    ai_model = Column(String, nullable=False)

    # PDF export — NULL until user clicks Export PDF
    pdf_path = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="tailoring_sessions")
    resume = relationship("Resume", back_populates="tailoring_sessions")
    job = relationship("Job", back_populates="tailoring_sessions")
```

---

### models/ai_provider_config.py

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_config"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # "ollama" | "claude" | "openai" | "gemini"
    provider_name = Column(String, unique=True, nullable=False)

    # Toggle on/off without touching code
    is_enabled = Column(Boolean, default=True, nullable=False)

    # Default model for this provider e.g. "mistral:7b", "claude-sonnet-4-6", "gpt-4o"
    default_model = Column(String, nullable=False)

    # Per-module model overrides
    # e.g. { "analyzer": "mistral:7b", "tailor": "llama3.2", "scorer": "deepseek-r1" }
    module_overrides_json = Column(Text, nullable=True, default="{}")

    # Fallback order: 1 = try first, 2 = try second, etc.
    priority_order = Column(Integer, nullable=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

---

## Part 6 — Database Seeder

Create `backend/seed.py`. This seeds the `ai_provider_config` table on first startup.

```python
from database import SessionLocal
from models.ai_provider_config import AIProviderConfig


def seed_ai_providers(db):
    """
    Seeds default AI provider config rows.
    Only inserts if the table is empty — safe to call on every startup.
    """
    if db.query(AIProviderConfig).count() > 0:
        return  # Already seeded

    providers = [
        AIProviderConfig(
            provider_name="ollama",
            is_enabled=True,
            default_model="mistral:7b",
            module_overrides_json="{}",
            priority_order=1,
        ),
        AIProviderConfig(
            provider_name="claude",
            is_enabled=False,   # Disabled until API key is set
            default_model="claude-sonnet-4-6",
            module_overrides_json="{}",
            priority_order=2,
        ),
        AIProviderConfig(
            provider_name="openai",
            is_enabled=False,
            default_model="gpt-4o",
            module_overrides_json="{}",
            priority_order=3,
        ),
        AIProviderConfig(
            provider_name="gemini",
            is_enabled=False,
            default_model="gemini-1.5-pro",
            module_overrides_json="{}",
            priority_order=4,
        ),
    ]

    db.add_all(providers)
    db.commit()
    print("✅ AI providers seeded.")


if __name__ == "__main__":
    db = SessionLocal()
    seed_ai_providers(db)
    db.close()
```

---

## Part 7 — Pydantic Schemas

Schemas live in `backend/schemas/`. These are separate from models — models are for the DB, schemas are for API request/response validation.

### schemas/__init__.py
```python
from .user import UserCreate, UserResponse, Token
from .resume import ResumeCreate, ResumeResponse
from .job import JobCreate, JobResponse
from .tailoring_session import TailoringSessionResponse
```

### schemas/user.py
```python
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
```

### schemas/resume.py
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ResumeCreate(BaseModel):
    name: str


class ResumeResponse(BaseModel):
    id: int
    user_id: int
    name: str
    original_filename: str
    file_format: str
    char_count: int
    page_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
```

### schemas/job.py
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class JobCreate(BaseModel):
    jd_raw_text: str


class JobResponse(BaseModel):
    id: int
    user_id: int
    auto_name: str
    company_name: Optional[str]
    job_title: Optional[str]
    location: Optional[str]
    is_remote: Optional[bool]
    seniority_level: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
```

### schemas/tailoring_session.py
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TailoringSessionResponse(BaseModel):
    id: int
    user_id: int
    resume_id: int
    job_id: int
    ats_score: int
    ai_provider: str
    ai_model: str
    pdf_path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
```

---

## Part 8 — Authentication Router

This is the only fully implemented router for Day 1.
Write this to `backend/routers/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional

from database import get_db
from models.user import User
from schemas.user import UserCreate, UserResponse, Token, TokenData
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    user.last_login_at = datetime.utcnow()
    db.commit()

    token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

---

## Part 9 — Stub Routers (Not Implemented Today)

For every router file below, write a stub so the app boots without errors.
Use this exact pattern for each:

**Template (copy and adapt for each file):**
```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/REPLACE_PREFIX", tags=["REPLACE_TAG"])

@router.get("/status")
def status():
    return {"status": "not implemented yet", "module": "REPLACE_MODULE"}
```

Files and their values:

| File | prefix | tag | module |
|------|--------|-----|--------|
| routers/parse.py | /api/parse | Resume Parser | resume-parser |
| routers/analyze.py | /api/analyze | Job Analyzer | job-analyzer |
| routers/tailor.py | /api/tailor | Resume Tailor | resume-tailor |
| routers/score.py | /api/score | ATS Scorer | ats-scorer |
| routers/export.py | /api/export | PDF Exporter | pdf-exporter |
| routers/providers.py | /api/providers | AI Providers | ai-providers |

---

## Part 10 — Stub Module Files (Not Implemented Today)

For every module file below, write a single comment line only.
Do not write functions, do not import anything.

```
modules/parser/resume_parser.py      → # TODO: Implement Day 2 — PDF/DOCX parsing
modules/parser/section_extractor.py  → # TODO: Implement Day 2 — Section extraction
modules/analyzer/job_analyzer.py     → # TODO: Implement Day 3 — Job description analysis
modules/tailor/tailor_agent.py       → # TODO: Implement Day 4 — AI resume tailoring
modules/scorer/ats_scorer.py         → # TODO: Implement Day 5 — ATS keyword scoring
modules/exporter/pdf_exporter.py     → # TODO: Implement Day 6 — ATS-safe PDF export
modules/ai_provider/provider_manager.py → # TODO: Implement Day 7 — AI provider switching
```

Prompt files in `modules/tailor/prompts/` — write placeholder content:
- `tailor_resume.md` → first line: `# TODO: Add resume tailoring prompt — Day 4`
- `analyze_job.md` → first line: `# TODO: Add job analysis prompt — Day 3`

---

## Part 11 — Main Application Entry Point

Write this to `backend/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import get_settings
from database import create_tables, SessionLocal
from seed import seed_ai_providers

from routers import auth, parse, analyze, tailor, score, export, providers

settings = get_settings()


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
```

---

## Part 12 — Frontend Scaffold (React + Vite)

Do this from the `ResumeForge/frontend/` directory:

```bash
cd /Users/nikunjshetye/Project/ResumeForge
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install axios react-router-dom
```

Update `frontend/tailwind.config.js`:
```js
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

Add this to `frontend/src/index.css` (top of file):
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

Create `frontend/src/api/client.js`:
```js
import axios from 'axios';

const client = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default client;
```

For all other `.jsx` component and page files — create them with a single placeholder:
```jsx
export default function ComponentName() {
  return <div className="p-4 text-gray-500">TODO: Implement ComponentName — Day 7</div>;
}
```

---

## Part 13 — Alembic Setup (Database Migrations)

```bash
cd /Users/nikunjshetye/Project/ResumeForge/backend
alembic init migrations
```

Update `alembic.ini` — change this line:
```
sqlalchemy.url = sqlite:///./data/resumeforge.db
```

Update `migrations/env.py` — add these lines after existing imports:
```python
from config import get_settings
from database import Base
import models  # Import all models so Alembic can detect them

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

Generate and run the initial migration:
```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

---

## Part 14 — Verification Checklist

After completing all parts, run these checks. Every check must pass before Day 1 is complete.

### Check 1: Server starts without errors
```bash
cd /Users/nikunjshetye/Project/ResumeForge/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```
Expected output:
```
✅ AI providers seeded.
✅ ResumeForge v1.0.0 started
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Check 2: API docs load
Open `http://localhost:8000/docs` in browser.
Expected: Swagger UI loads showing all routers listed.

### Check 3: Health check
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"healthy"}`

### Check 4: Signup works
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "testpassword123", "full_name": "Test User"}'
```
Expected: JSON with user id, email, full_name, created_at

### Check 5: Login works and returns JWT token
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@test.com&password=testpassword123"
```
Expected: `{"access_token": "eyJ...", "token_type": "bearer"}`

### Check 6: Protected route works
Use the token from Check 5:
```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```
Expected: JSON with user details

### Check 7: Database file exists and has all 6 tables
```bash
cd /Users/nikunjshetye/Project/ResumeForge/backend
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print('Tables found:', [t[0] for t in tables])
conn.close()
"
```
Expected output:
```
Tables found: ['users', 'resumes', 'resume_sections', 'jobs', 'tailoring_sessions', 'ai_provider_config']
```

### Check 8: AI providers seeded
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
rows = conn.execute('SELECT provider_name, default_model, priority_order FROM ai_provider_config').fetchall()
for r in rows: print(r)
conn.close()
"
```
Expected:
```
('ollama', 'mistral:7b', 1)
('claude', 'claude-sonnet-4-6', 2)
('openai', 'gpt-4o', 3)
('gemini', 'gemini-1.5-pro', 4)
```

### Check 9: Frontend scaffold runs
```bash
cd /Users/nikunjshetye/Project/ResumeForge/frontend
npm run dev
```
Expected: Vite dev server starts at `http://localhost:5173`

### Check 10: All 6 tables have correct columns
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
for table in ['users','resumes','resume_sections','jobs','tailoring_sessions','ai_provider_config']:
    cols = conn.execute(f'PRAGMA table_info({table})').fetchall()
    print(f'{table}: {[c[1] for c in cols]}')
conn.close()
"
```
Review output and confirm all columns match the model definitions.

---

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: No module named 'config'` | Running uvicorn from wrong directory | Always run from `backend/` directory |
| `SECRET_KEY field required` | .env file not found | Verify `.env` exists in `backend/` and has SECRET_KEY set |
| `check_same_thread` SQLite error | Missing connect_args | Add `connect_args={"check_same_thread": False}` in `database.py` |
| `Table already exists` | Running create_tables twice | Safe to ignore — SQLAlchemy uses `CREATE TABLE IF NOT EXISTS` |
| Alembic `Target database is not up to date` | Migration not applied | Run `alembic upgrade head` |
| CORS error from frontend | Origin not in allow list | Add your frontend URL to `allow_origins` in `main.py` |
| `ImportError` from models/__init__.py | Model not yet created | Create the missing model file before importing |

---

## Day 1 Complete — Handoff to Day 2

When all 10 checks pass, Day 1 is done. The output is:

- Full project folder structure in place
- SQLite database with all 6 tables created and indexed
- JWT-based auth working (signup, login, protected routes)
- All routers registered (stubs for Days 2–7)
- All module files created (stubs for Days 2–7)
- Frontend scaffold running on port 5173
- AI providers seeded in database

**Day 2 will implement:** `modules/parser/resume_parser.py` + `modules/parser/section_extractor.py` + `routers/parse.py` — the Resume Parser module.

---

*ResumeForge — Day 1 Guide | Generated for Nikunj Shetye*
