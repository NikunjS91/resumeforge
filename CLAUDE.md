# ResumeForge — Project Context

> This file is loaded at the start of every Claude Code session.
> It tells the agent everything about this project so it never needs
> to rediscover the same things.

---

## Project Identity
AI-powered resume tailoring tool. Local-first, privacy-focused.
FastAPI backend + React/Vite/TailwindCSS frontend + SQLite DB.
LLMs: Ollama (qwen3:14b local) + NVIDIA NIM (llama-3.3-70b cloud).
PDF generation: pdflatex (BasicTeX 2026).
Location: /Users/nikunjshetye/Documents/resume-forger
GitHub: https://github.com/NikunjS91/resumeforge

---

## Server Startup (ALL 3 required every session — they stop when terminal closes)

```bash
# Terminal 1 — Backend (MUST export PATH before uvicorn)
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
export PATH="/Library/TeX/texbin:$PATH"
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd /Users/nikunjshetye/Documents/resume-forger/frontend
npm run dev  # runs on port 5173

# Terminal 3 — Ollama
ollama serve  # port 11434, model: qwen3:14b
```

---

## Critical Facts (Agent MUST know these — wrong answers break everything)

### Test Credentials
- Email: nikunj@resumeforge.com
- Password: securepass123
- User ID: 3

### Resume IDs
- resume_id=28 → Resume_10March.pdf → CORRECT DATA (GPA 3.84, real URLs, 3 projects)
- resume_id=2  → ResumeWorded.pdf  → WRONG DATA (GPA 3.5, placeholder URLs)
- **ALWAYS use resume_id=28 for testing. NEVER use resume_id=2.**

### Nikunj's Correct Resume Data (DO NOT change these)
- GPA: 3.84/4.0 (Pace University MS CS)
- LinkedIn: https://www.linkedin.com/in/nikunj-shetye
- GitHub: https://github.com/NikunjS91
- Job Title: Cloud Infrastructure Engineer (NOT Data Analyst)
- Real metrics: 35%, 40%, 45%, 60%, 99.9%, 76%, 30%, 95%
- Projects: Job Application Tracker, TrueSight, Sentiment Analysis

### Port Map
- Backend API: http://localhost:8000
- Frontend: http://localhost:5173
- Ollama: http://localhost:11434
- Swagger: http://localhost:8000/docs

---

## Architecture Overview

```
backend/
  main.py                       ← load_dotenv() at top
  config.py                     ← extra="ignore" for pydantic
  routers/
    auth.py                     ← JWT login/signup
    export.py                   ← PDF export (2 paths: surgical or generate)
    history.py                  ← GET /api/history/ + /pdf
    analyze.py                  ← JD analysis
    tailor.py                   ← Resume tailoring
    score.py                    ← ATS scoring
  modules/
    export/
      latex_surgeon.py          ← Day 11: surgical edits to master LaTeX
      latex_generator.py        ← Stage 1: LLM generates .tex from scratch
      latex_reviewer.py         ← Stage 2: LLM reviews and fixes .tex
      latex_compiler.py         ← runs pdflatex, calls spacing_normalizer
      spacing_normalizer.py     ← post-LLM spacing compression
      data_validator.py         ← validates source before LLM generation
      resume_rules.py           ← UNIVERSAL_RULES, TEMPLATES dict
    analyze/
      jd_analyzer.py            ← regex fallback + Ollama LLM
    tailor/
      resume_tailor.py          ← NVIDIA NIM stream=True
    parse/
      section_detector.py       ← Technologies: bleeding fix
  templates/
    professional.tex            ← Classic (dark navy)
    minimal.tex                 ← No colors (ATS-safe)
    modern.tex                  ← Blue accent bar
  data/
    resumeforge.db              ← SQLite database
    exports/                    ← generated .tex and .pdf files

frontend/src/
  pages/
    Dashboard.jsx               ← Pipeline + History tabs
    Login.jsx                   ← JWT auth
  components/
    ResumeUpload.jsx
    JobInput.jsx
    TailorPanel.jsx             ← Ollama / NVIDIA NIM selector
    ATSScore.jsx                ← before/after comparison circles
    ExportPanel.jsx             ← 3-card template selector + PDF preview
  api/
    axios.js                    ← 3min timeout, auth interceptor
```

---

## What Was Built (Day by Day)

| Day | Feature |
|-----|---------|
| 1-5 | Auth (JWT), PDF parser, JD analyzer, resume tailor, ATS scorer |
| 6-7 | LaTeX PDF engine (replaces ReportLab), React 5-step pipeline UI |
| 8   | 2-stage LLM generation (Stage1 generate + Stage2 review) |
| 9   | Resume History tab + 3 LaTeX template selector |
| 10  | Anti-hallucination rules, data_validator.py, spacing_normalizer.py |
| 11  | Surgical LaTeX path: master_latex stored in DB, minimal edits per JD |

---

## GOTCHAS — Things the Agent Has Gotten Wrong Before

### ❌ PATH issue (breaks PDF export)
pdflatex is NOT in PATH by default on macOS with BasicTeX.
ALWAYS run this before starting uvicorn:
```bash
export PATH="/Library/TeX/texbin:$PATH"
```
If you forget this, all PDF exports return 500 error.

### ❌ Wrong resume ID
Never test with resume_id=2. It has wrong GPA (3.5), placeholder URLs, no real projects.
Always use resume_id=28 for any quality testing.

### ❌ NVIDIA NIM streaming
resume_tailor.py MUST use stream=True when calling NVIDIA NIM.
Without stream=True the request hangs and times out after 3 minutes.

### ❌ LLM ignoring rules in prompts
Long paragraphs of rules get ignored. Rules MUST use:
- ════ separators between sections
- Numbered single-line rules
- FINAL REMINDER block after the data
See latex_generator.py build_stage1_prompt() for the correct pattern.

### ❌ Checking PDF before checking .tex
After any export change, ALWAYS check the generated .tex file first:
```bash
LATEST=$(ls -t backend/data/exports/*.tex | head -1)
grep -E "GPA|linkedin|github|[0-9]+%" "$LATEST" | head -10
```
If the .tex is wrong, the PDF will be wrong. Fix upstream, not downstream.

### ❌ master_latex column
Added via ALTER TABLE in Day 11. If you get "no such column: master_latex":
```bash
cd backend && python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
conn.execute('ALTER TABLE resumes ADD COLUMN master_latex TEXT')
conn.commit()
print('Added')
conn.close()
"
```

### ❌ Frontend port conflict
If port 5173 is in use, Vite uses 5174 or 5175.
Check with: `lsof -i :5173 -i :5174 -i :5175 | grep LISTEN`

---

## Standard Verification Pattern

Use after ANY backend change:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Health check
curl -s http://localhost:8000/health

# ATS score on correct resume (should be 90+)
curl -s -X POST http://localhost:8000/api/score/ats \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 28, "job_id": 1}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('ATS:', d.get('ats_score'))"

# History check
curl -s http://localhost:8000/api/history/ \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Sessions:', d.get('total'))"
```

---

## Git Branch Strategy

```
main     ← production-ready, always working
dev      ← integration branch
feature/ ← one branch per day's work
```

Merge order: feature → dev → main
Always run verification checks before merging to main.

---

## Wait Times (Don't assume it's broken)

| Operation | Expected Time |
|-----------|-------------|
| JD analysis (Ollama) | 30-60s |
| JD analysis (NVIDIA) | 5-10s |
| Resume tailoring (NVIDIA) | 15-25s |
| PDF export surgical path | 10-20s |
| PDF export generation path | 30-90s |
| pdflatex compilation | 3-8s |

---

## Key API Endpoints

| Method | Route | What it does |
|--------|-------|-------------|
| POST | /auth/login | Returns JWT token |
| POST | /api/parse/upload | Upload + parse resume PDF/DOCX |
| POST | /api/analyze/job | Extract skills from JD text |
| POST | /api/tailor/resume | Tailor resume to job (NVIDIA/Ollama) |
| POST | /api/score/ats | Score resume against job |
| POST | /api/export/pdf | Generate PDF (surgical or full generation) |
| POST | /api/export/master-latex | Store perfect .tex as master resume |
| GET  | /api/export/master-latex/{id} | Check if master exists |
| GET  | /api/history/ | All tailoring sessions |
| GET  | /api/history/{id}/pdf | Re-download session PDF |
