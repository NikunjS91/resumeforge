# ResumeForge — Project Status

> Last updated: 2026-04-01
> Branch: dev | Main always production-ready

---

## Current Focus

**Day 14 — LaTeX Quality: Post-Processor Approach** — COMPLETE
- Added `post_process_latex()` that runs AFTER Stage 2 in `export.py` (Stage 2 can no longer undo corrections)
- `_build_projects_latex()`: rebuilds all 3 projects from source data — full names, all bullets, Technologies lines, correct order
- `_build_leadership_latex()`: rebuilds Leadership section — never dropped
- `_normalize_project_content()`: handles both raw DB format (lone bullet + wrapped lines) and tailored format (inline bullets)
- `call_nvidia()`: switched to non-streaming — eliminates SSE JSON parsing issues
- Fixed `_replace_latex_section` lambda replacement (Python 3.13 re.error for LaTeX backslashes)
- **All 7 open bugs fixed**: BUG-008, 009, 011, 012, 013, 018, 019
- Verified: 6 experience bullets, 3 Technologies lines, Leadership present, full project names, correct order, no coursework

---

## Overall System Health

| Component | Status | Notes |
|-----------|--------|-------|
| Backend (FastAPI) | Working | Port 8000 |
| Frontend (React/Vite) | Working | Port 5173 |
| Ollama (qwen3:14b) | Working | Port 11434 |
| NVIDIA NIM (llama-3.3-70b) | Working | Cloud API, stream=True |
| PDF Export — surgical path | Working | ~10-20s when master_latex exists |
| PDF Export — generation path | Working but slow | 3-5 min, NIM Stage 1+2 |
| ATS Scorer | Working | Scores 90+ on resume_id=28 |
| Resume Tailoring | Working | Both Ollama and NVIDIA NIM |
| History Tab | Working | Sessions + PDF re-download |
| Auth (JWT) | Working | Login/signup |

---

## Feature Timeline

| Day | Feature | Status |
|-----|---------|--------|
| 1-5 | Auth (JWT), PDF parser, JD analyzer, resume tailor, ATS scorer | Done |
| 6-7 | LaTeX PDF engine (replaces ReportLab), React 5-step pipeline UI | Done |
| 8   | 2-stage LLM generation (Stage1 generate + Stage2 review) | Done |
| 9   | Resume History tab + 3 LaTeX template selector | Done |
| 10  | Anti-hallucination rules, data_validator.py, spacing_normalizer.py | Done |
| 11  | Surgical LaTeX path: master_latex stored in DB, minimal edits per JD | Done |
| 12  | Claude Code context engineering: CLAUDE.md + anti-hallucination rules | Done |
| 13  | Auto-save master LaTeX after first generation (speed fix) | Done |
| 14  | LaTeX quality: post-processor for Projects, Leadership, Coursework | Done |

---

## Bug Tracker Summary

| ID | Bug | Severity | Status |
|----|-----|----------|--------|
| BUG-001 | Wrong model name shown after tailoring | Low | Fixed |
| BUG-002 | Pipeline auto-advances steps 4 & 5 without user input | Medium | Fixed |
| BUG-003 | ATS Score API called twice | Medium | Fixed |
| BUG-004 | Export generates all 3 templates in parallel on load | High | Fixed |
| BUG-005 | ATS Score shows 2 ("Proficiency in React" not matched) | High | Fixed |
| BUG-006 | Hallucinated "Frontend: React" skill row | High | Fixed |
| BUG-007 | Experience subheading order reversed | Medium | Fixed |
| BUG-008 | 2 experience bullets silently dropped | High | Fixed |
| BUG-009 | Technologies lines dropped from all 3 projects | High | Fixed |
| BUG-010 | Per-project GitHub links dropped | Medium | Fixed |
| BUG-011 | Coursework moves to standalone section (experienced candidate) | Low | Fixed |
| BUG-012 | Project bullets cut from 4-5 to 3 per project | High | Fixed |
| BUG-013 | Leadership & Activities section dropped during tailoring | High | Fixed |
| BUG-014 | Tailoring drops/merges bullets | Medium | Fixed |
| BUG-015 | PDF export hangs / never completes | High | Fixed |
| BUG-016 | Export full generation exceeds frontend timeout | High | Fixed |
| BUG-017 | Password field missing autocomplete attribute | Low | Fixed |

| BUG-018 | Projects output in wrong order | Medium | Fixed |
| BUG-019 | Project names truncated/shortened | Medium | Fixed |

**Open Bugs:** 0
**Fixed Bugs:** 19

---

## Performance Benchmarks

| Operation | Expected Time | Actual (current) |
|-----------|-------------|-----------------|
| JD analysis (Ollama) | 30-60s | ~45s |
| JD analysis (NVIDIA) | 5-10s | ~7s |
| Resume tailoring (NVIDIA) | 15-25s | ~20s |
| PDF export — surgical path | 10-20s | ~15s |
| PDF export — generation path | 3-5 min | ~4 min |
| pdflatex compilation | 3-8s | ~5s |

**Achieved (Day 13):** PDF export #2+ dropped from ~4 min → **31s** (surgical path)

---

## Architecture State

```
backend/
  routers/
    auth.py          — JWT, login/signup
    export.py        — PDF export, async job queue, master-latex CRUD
    tailor.py        — Resume tailoring (Ollama + NVIDIA)
    score.py         — ATS scoring
    analyze.py       — JD analysis
    history.py       — Session history + PDF re-download
  modules/
    export/
      latex_generator.py    — Stage 1: LLM generates .tex from scratch
      latex_reviewer.py     — Stage 2: LLM reviews and fixes .tex
      latex_surgeon.py      — Surgical: minimal LLM edits to master .tex
      latex_compiler.py     — pdflatex runner + spacing_normalizer
      spacing_normalizer.py — Post-LLM spacing compression
      data_validator.py     — Source data validation before generation
      resume_rules.py       — UNIVERSAL_RULES, prompt templates
      job_store.py          — In-memory async job store (TTL cleanup)

frontend/src/
  pages/
    Dashboard.jsx    — 5-step pipeline + History tab
    Login.jsx        — JWT auth
  components/
    ExportPanel.jsx  — 3-card template selector, async polling, PDF preview
    ATSScore.jsx     — Before/after ATS comparison circles
    TailorPanel.jsx  — Ollama/NVIDIA selector
  api/
    axios.js         — 3min HTTP timeout, auth interceptor
```

---

## Test Credentials

```
Email:    nikunj@resumeforge.com
Password: securepass123
User ID:  3

resume_id=28  ← ALWAYS use this (Resume_10March.pdf, GPA 3.84)
resume_id=2   ← NEVER use this (wrong GPA 3.5, placeholder URLs)
```

---

## Server Startup

```bash
# Terminal 1 — Backend
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
export PATH="/Library/TeX/texbin:$PATH"
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd /Users/nikunjshetye/Documents/resume-forger/frontend
npm run dev

# Terminal 3 — Ollama
ollama serve
```

---

## Next Up (Day 14 ideas)

- [ ] Verify prompt-level bug fixes (BUG-007 through BUG-013) with a fresh export
- [ ] Add template preview thumbnails to ExportPanel
- [ ] CI/CD: GitHub Actions for lint + test on push to dev
- [ ] Deploy: Dockerize backend + frontend for remote hosting
