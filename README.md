# ResumeForge 🔨

> AI-powered resume tailoring tool — 100% local, 100% free, runs on your machine.

---

## What It Does

Paste any job description → ResumeForge extracts required skills, tailors your resume to match, scores it against ATS keywords, and exports a clean PDF — all powered by a local LLM running on your Mac.

No API costs. No data leaving your machine.

---

## Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (Python) |
| **Database** | SQLite + SQLAlchemy ORM |
| **Local LLM** | Ollama — `qwen3:14b` |
| **PDF Parsing** | pdfplumber (layout-aware extraction) |
| **DOCX Parsing** | python-docx |
| **PDF Export** | ReportLab *(Day 6)* |
| **Frontend** | React + Vite + TailwindCSS *(Day 7)* |
| **Auth** | JWT (stateless) |

---

## Features

| | Feature | Status |
|-|---------|--------|
| ✅ | JWT Authentication (signup, login) | Done |
| ✅ | Resume Parser — PDF + DOCX, layout-aware | Done |
| ✅ | Section Detection — regex + LLM fallback | Done |
| ✅ | Job Description Analyzer — skills extraction | Done |
| 🔄 | Resume Tailor — LLM rewriting per JD | In Progress |
| 🔄 | ATS Scorer — keyword matching, 0-100 score | Planned |
| 🔄 | PDF Exporter — ATS-friendly output | Planned |
| 🔄 | React Frontend — full UI | Planned |

---

## Project Structure

```
resumeforge/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── database.py                # SQLAlchemy session
│   ├── config.py                  # Settings + env vars
│   ├── seed.py                    # AI provider seeding
│   ├── requirements.txt
│   ├── .env                       # NOT committed (gitignored)
│   ├── models/                    # SQLAlchemy DB models
│   │   ├── user.py
│   │   ├── resume.py
│   │   ├── resume_section.py
│   │   ├── job.py
│   │   ├── tailoring_session.py
│   │   └── ai_provider_config.py
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── routers/                   # API route handlers
│   │   ├── auth.py                # POST /auth/signup, /auth/login, GET /auth/me
│   │   ├── parse.py               # POST /api/parse/upload
│   │   ├── analyze.py             # POST /api/analyze/job
│   │   ├── tailor.py              # stub
│   │   ├── score.py               # stub
│   │   └── export.py              # stub
│   ├── modules/                   # Business logic
│   │   ├── parse/
│   │   │   ├── extractor.py       # PDF/DOCX text extraction
│   │   │   └── section_detector.py # Regex + LLM section detection
│   │   └── analyze/
│   │       └── jd_analyzer.py     # JD regex + LLM extraction
│   └── data/
│       ├── resumeforge.db         # SQLite DB (gitignored)
│       └── uploads/               # Uploaded files (gitignored)
├── frontend/                      # React + Vite (Day 7)
└── documentGuide/                 # Day-by-day build guides
```

---

## API Routes

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| POST | `/auth/signup` | No | Create account |
| POST | `/auth/login` | No | Get JWT token |
| GET | `/auth/me` | Yes | Get current user |
| POST | `/api/parse/upload` | Yes | Upload PDF/DOCX resume |
| POST | `/api/analyze/job` | Yes | Analyze job description |
| POST | `/api/tailor/resume` | Yes | Tailor resume to JD *(coming)* |
| POST | `/api/score/ats` | Yes | ATS keyword score *(coming)* |
| POST | `/api/export/pdf` | Yes | Export tailored PDF *(coming)* |

Interactive docs: `http://localhost:8000/docs`

---

## Local Setup

### Prerequisites
- macOS (M-series recommended)
- Python 3.10+
- [Ollama](https://ollama.ai) installed

### 1 — Clone and install

```bash
git clone https://github.com/NikunjS91/resumeforge.git
cd resumeforge/backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY
```

### 3 — Pull the LLM model

```bash
ollama serve          # Start Ollama server
ollama pull qwen3:14b # ~9GB download (best for M3 Pro 18GB)
```

### 4 — Start the backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

---

## Auto-Start on Login (macOS)

Both services can be configured to start automatically using launchd:

```bash
# Backend auto-start
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.resumeforge.backend.plist

# Ollama auto-start
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ollama.serve.plist
```

---

## Branch Strategy

```
main     ← stable, verified builds
dev      ← active development
  └── feature/day4-resume-tailor
  └── feature/day5-ats-scorer
  └── feature/day6-pdf-exporter
  └── feature/day7-frontend
```

---

## Hardware Tested On

| Spec | Value |
|------|-------|
| Machine | MacBook Pro M3 Pro |
| RAM | 18GB unified memory |
| Model | qwen3:14b (~12GB in RAM) |
| Inference speed | ~60 tokens/sec |

---

## Requirements

- macOS / Linux (Windows via WSL)
- 16GB+ RAM recommended (18GB ideal for qwen3:14b)
- 15GB free disk space (model + project)
- Python 3.10+
- Ollama

---

## License

MIT — Free to use, modify, and distribute.
