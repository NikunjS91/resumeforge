# ResumeForge — Bug Report

> Updated: 2026-03-31
> Environment: Frontend (localhost:5173) + Backend (localhost:8000)

---

## BUG-005 — ATS Score Shows 2 for Both Original and Tailored (No Improvement)

**Status:** FIXED
**Severity:** High
**Location:** `backend/modules/score/ats_scorer.py`

### Root Cause
The JD extracted "Proficiency in React" as the skill phrase. `keyword_variants()` only checked for the
exact phrase "proficiency in react" — never just "react" — so every resume scored 0.

### Fix Applied
Enhanced `keyword_variants()` to extract the core skill from common JD phrases:
- "Proficiency in React" → also checks "react"
- "Experience with Docker" → also checks "docker"
- "Knowledge of AWS" → also checks "aws"
- "3+ years of Python" → also checks "python"

---

# Content & Structure Bugs — Original PDF vs System Resumes

> Compared: `Resume_10March.pdf` (ground truth) vs `original_Resume_10March_28.tex` (parser output) vs `tailored_Resume_10March_96.tex` (tailored output)
> All 3 generated templates (Classic, Minimal, Modern) share the same content .tex — content bugs affect ALL templates equally.

---

## LAYER 1 — Parser Bugs (PDF → System .tex)

---

## BUG-007 — Experience Subheading Order Reversed

**Status:** OPEN
**Severity:** Medium
**Layer:** Parser → `backend/modules/parse/section_detector.py`

### Description
Original PDF: **Job Title** is bold top-left, Company is italic below.
System generates: **Company Name** is bold top-left, Job Title is italic below — reversed.

### Fix Applied
Updated `build_template_fill_prompt` in `latex_generator.py`:
- Changed `\resumesubheading{{Company}}{{Dates}}{{Title}}{{Location}}`
- To `\resumesubheading{{Job Title}}{{Dates}}{{Company Name}}{{Location}}`
- Added explicit note: "Job Title MUST be arg #1 (rendered bold)"

**Status: FIXED in prompt — will apply to next generation**

---

## BUG-008 — 2 Experience Bullets Silently Dropped by Parser

**Status:** OPEN
**Severity:** High
**Layer:** LLM generation → `backend/modules/export/latex_generator.py`

### Description
Original PDF has 6 experience bullets. System generates only 4. Missing:
- "Configured AWS load balancing and auto-scaling..." (Lambda/serverless keywords)
- "Developed Python and SQL dashboards..." (data engineering skills)

### Fix Applied
Updated `build_template_fill_prompt` C3:
- Changed from "up to 6 per role" to "include ALL bullets — do NOT cap or drop any bullets"
- Added to FINAL REMINDER checklist

**Status: FIXED in prompt — will apply to next generation**

---

## BUG-009 — Technologies Lines Dropped from All 3 Projects

**Status:** OPEN
**Severity:** High
**Layer:** LLM generation → `backend/modules/export/latex_generator.py`

### Description
Original PDF has `Technologies: React, Node.js, ...` as a bold bullet at the end of each project. All 3 system-generated templates omit these lines completely.

### Fix Applied
Updated `build_template_fill_prompt` C2 to explicitly require:
- "Include Technologies as last bullet: `\item \textbf{Technologies:} React, ...`"

**Status: FIXED in prompt — will apply to next generation**

---

## BUG-010 — Per-Project GitHub Links Dropped

**Status:** OPEN
**Severity:** Medium
**Layer:** LLM generation → `backend/modules/export/latex_generator.py`

### Description
Original PDF shows a GitHub hyperlink aligned right on each project title. System-generated resumes have no per-project GitHub links.

### Fix Applied
Updated `build_template_fill_prompt` C2 to include:
- "If source has a GitHub link for a project, add it as `\href{url}{GitHub}` in the heading"

**Status: FIXED in prompt — will apply to next generation**

---

## BUG-011 — Relevant Coursework Moved from Inline Education to Separate Section

**Status:** FIXED
**Severity:** Low
**Layer:** `backend/modules/export/latex_generator.py`

### Root Cause
`build_template_fill_prompt` accepted `candidate_type` as a parameter but never used it in the
prompt text. The LLM got a generic "For experienced candidates..." line but was never told
whether the current candidate IS experienced. It then guessed based on content and sometimes
kept the coursework block.

### Fix Applied
- Added `coursework_rule` variable computed from `candidate_type`
- Injected `CANDIDATE TYPE: EXPERIENCED — ...` explicitly into FORMAT RULES
- LLM now receives a direct instruction specific to this candidate's type

---

## BUG-012 — Project Bullet Counts Reduced (5→3 per project)

**Status:** OPEN
**Severity:** High
**Layer:** LLM generation → `build_template_fill_prompt`

### Description
Original PDF has 4–5 bullets per project plus a Technologies line. System generates 3 bullets, no Technologies line. Drops: Kafka/Redis notifications, Kanban board, team leadership (58 story points), 50K+ tweets.

### Fix Applied
Updated C2 in `build_template_fill_prompt` to: "Include ALL bullets from source (up to 6 per project)" and added Technologies/GitHub link requirements.

**Status: FIXED in prompt — will apply to next generation**

---

## LAYER 2 — Tailoring Bugs

---

## BUG-013 — Leadership & Activities Section Entirely Dropped During Tailoring

**Status:** OPEN
**Severity:** High
**Layer:** LLM Tailoring → `latex_generator.py` + `resume_rules.py`

### Description
After tailoring, the Leadership & Activities section (AWS Cloud Club + CodeChef mentoring) is completely absent from the output.

### Fix Applied
1. Updated `UNIVERSAL_RULES` in `resume_rules.py`: Added rule 14 — "Leadership & Activities is MANDATORY if it exists in source"
2. Updated `SECTION_ORDER_EXPERIENCED` comment to say "MANDATORY if present in source"
3. Updated `build_stage1_prompt` FINAL REMINDER: Added "LEADERSHIP section is present if source has it — NEVER drop"

**Status: FIXED in prompt — will apply to next generation**

---

## BUG-014 — Tailoring Compounds Parser Bullet Loss

**Status:** FIXED
**Severity:** Medium
**Layer:** `backend/modules/tailor/resume_tailor.py`

### Root Cause
Both tailor prompts (one-shot and per-section) said "Keep roughly the same length" — vague
enough for the LLM to merge or drop bullets. Combined with BUG-008 (generation also dropped
bullets), the net loss was 2 bullets from original PDF.

### Fix Applied
- Added explicit rule to both prompts: "PRESERVE ALL BULLETS — count the bullet points in the
  original and output the SAME count. Do NOT drop, merge, or summarize any bullet points."
- BUG-008 generation-path fix already in place (C3: "include ALL bullets")

---

## ✅ FIXED BUGS

| ID | Bug | Fixed In |
|----|-----|----------|
| BUG-001 | Wrong model name shown after tailoring (qwen3:14b shown for NVIDIA) | `backend/routers/tailor.py` — provider→model map |
| BUG-002 | Pipeline auto-advances through Steps 4 & 5 without user input | `frontend/src/pages/Dashboard.jsx` — explicit Next buttons |
| BUG-003 | ATS Score API called twice (double invocation) | `frontend/src/components/ATSScore.jsx` — useRef guard |
| BUG-004 | Export generates all 3 templates in parallel on load | `frontend/src/components/ExportPanel.jsx` — on-demand per template |
| BUG-006 | Hallucinated "Frontend: React" skill row not in original PDF | `latex_generator.py` prompt + `resume_rules.py` rule 10 |
| BUG-007 | Experience subheading order reversed (company vs job title) | `latex_generator.py` LATEX_EXPERIENCE_BLOCK instruction |
| BUG-008 | 2 experience bullets silently dropped | `latex_generator.py` C3 completeness rule |
| BUG-009 | Technologies lines dropped from all 3 projects | `latex_generator.py` C2 completeness rule |
| BUG-010 | Per-project GitHub links dropped | `latex_generator.py` C2 completeness rule |
| BUG-012 | Project bullets cut from 4-5 to 3 per project | `latex_generator.py` C2 completeness rule |
| BUG-013 | Leadership & Activities entirely dropped during tailoring | `latex_generator.py` FINAL REMINDER + `resume_rules.py` rules |
| BUG-005 | ATS Score shows 2 for both (phrase "Proficiency in React" not matched) | `ats_scorer.py` `keyword_variants()` — extract core skill from phrases |
| BUG-015 | PDF export hangs / never completes | `axios.js` — added 3min timeout; `ExportPanel.jsx` — shows error reason |
| BUG-011 | Coursework standalone section instead of empty (experienced candidate) | `latex_generator.py` — inject `candidate_type` explicitly into prompt |
| BUG-014 | Tailoring drops/merges bullets | `resume_tailor.py` — "PRESERVE ALL BULLETS" rule in both tailor prompts |

---

---

## BUG-015 — PDF Export Hangs / Never Completes on Generation Path

**Status:** FIXED
**Severity:** High
**Location:** `frontend/src/api/axios.js`, `frontend/src/components/ExportPanel.jsx`

### Root Cause
`axios.js` had no timeout configured. The export request would hang indefinitely because
the frontend never cancelled the connection, even if the LLM took >5 minutes.

### Fix Applied
1. Added `timeout: 180000` (3 min) to `axios.create()` in `axios.js`
2. ExportPanel now shows the error reason: "Request timed out" vs server error message
3. Retry button clears the error message before re-attempting

---

---

## BUG-016 — Export Full Generation Path Exceeds 3min Frontend Timeout

**Status:** FIXED
**Severity:** High
**Found:** 2026-03-31 Playwright test
**Location:** `backend/routers/export.py`, `backend/modules/export/job_store.py`, `frontend/src/components/ExportPanel.jsx`

### Root Cause
On the full generation path (no master LaTeX stored), NVIDIA NIM Stage 1 alone took **3min 19s**.
The frontend axios timeout was 3min → client disconnected mid-generation. Backend continued
into Stage 2 + pdflatex for a client that no longer existed.

### Fix Applied — Async job + polling architecture
1. **`job_store.py`** (new) — in-memory job store with TTL cleanup
2. **`POST /api/export/pdf/async`** — loads DB data synchronously, spawns background thread, returns `job_id` immediately
3. **`GET /api/export/status/{job_id}`** — returns `{ status, stage, error }` for polling
4. **`GET /api/export/result/{job_id}`** — streams completed PDF once status is "done"
5. **`ExportPanel.jsx`** — submits async job, polls every 3s, shows per-stage progress in button + spinner:
   - "Submitting..." → "Stage 1: Generating LaTeX..." → "Stage 2: Reviewing LaTeX..." → "Compiling PDF..." → PDF loads
6. Timeout is now 6 min on the poll loop (not a hard HTTP timeout)

---

## BUG-017 — Password Field Missing autocomplete Attribute on Login Page

**Status:** OPEN
**Severity:** Low
**Found:** 2026-03-31 Playwright test
**Location:** `frontend/src/pages/Login.jsx`

### Description
Browser logs a warning on the login page:
```
[DOM] Input elements should have autocomplete attributes (suggested: "current-password")
```
The password `<input>` is missing `autocomplete="current-password"`, which prevents password
managers from working correctly and triggers browser warnings.

### Fix Plan
Add `autoComplete="current-password"` to the password input in `Login.jsx`.

---

## Open Bugs Summary

| ID | Bug | Layer | Severity | Status |
|----|-----|-------|----------|--------|
| BUG-008 | 2 experience bullets still dropped (load balancing + dashboards) | LaTeX generation | High | **RE-OPENED** — prompt rule ignored by LLM |
| BUG-009 | Technologies lines still missing from all 3 projects | LaTeX generation | High | **RE-OPENED** — prompt rule ignored by LLM |
| BUG-011 | Coursework still renders as separate section for experienced candidate | LaTeX generation | Medium | **RE-OPENED** — coursework section in source data overrides rule |
| BUG-012 | Project bullets still cut to 3 (from 4-5) | LaTeX generation | High | **RE-OPENED** — LLM prioritising 1-page fit over completeness |
| BUG-013 | Leadership & Activities still entirely absent | LaTeX generation | High | **RE-OPENED** — LLM fills LATEX_LEADERSHIP_BLOCK with empty string |
| BUG-018 | Projects output in wrong order | LaTeX generation | Medium | **NEW** — source: Tracker→TrueSight→Sentiment; output: TrueSight→Sentiment→Tracker |
| BUG-019 | Project names truncated/shortened | LaTeX generation | Medium | **NEW** — "AI-Powered Job Application Tracker - Cloud Deployed" → "Job Application Tracker" |

---

## BUG-018 — Projects Output in Wrong Order

**Status:** OPEN
**Severity:** Medium
**Found:** 2026-04-01 Playwright comparison
**Location:** `backend/modules/export/latex_generator.py` — `build_data_summary()`

### Description
Original PDF project order: Job Application Tracker → TrueSight → Sentiment Analysis
Generated output order: TrueSight → Sentiment Analysis → Job Application Tracker

The LLM re-orders projects based on keyword relevance to the job description, not source order.

### Fix Plan
Number projects explicitly in the data summary with `[PROJECT 1]`, `[PROJECT 2]`, `[PROJECT 3]`
labels and add a strict ordering rule in the prompt.

---

## BUG-019 — Project Names Truncated

**Status:** OPEN
**Severity:** Medium
**Found:** 2026-04-01 Playwright comparison
**Location:** `backend/modules/export/latex_generator.py` — `build_template_fill_prompt()`

### Description
| Source Name | Generated Name |
|-------------|---------------|
| AI-Powered Job Application Tracker - Cloud Deployed | Job Application Tracker |
| TrueSight - AI-Powered Deepfake Detection System (Capstone Project) | TrueSight |
| Real-Time Sentiment Analysis Platform | Sentiment Analysis |

LLM shortens names to save space when fitting to one page.

### Fix Plan
Annotate each project name in the data summary with `[EXACT NAME — do not shorten]`
and add explicit rule: "Use the EXACT project name from source — never abbreviate."

---

## Root Cause Analysis — Why "Fixed" Bugs Regressed

All 5 re-opened bugs (BUG-008, 009, 011, 012, 013) had prompt-only fixes that the LLM ignored.
The fundamental problem: **llama-3.3-70b ignores soft prose rules when under 1-page pressure**.

When the LLM estimates the output will overflow one page, it silently:
1. Drops bullets (experience and projects) to fit
2. Drops entire sections (leadership) as lowest priority
3. Includes coursework section despite the rule, because it sees "coursework" in source data

**Fix strategy (Day 14):** Replace prompt-only rules with **data preprocessing in Python**:
- Remove coursework from source data for experienced candidates (LLM can't include what it doesn't see)
- Inject explicit bullet counts: `[BULLET COUNT: 6 — output ALL 6]`
- Number and label projects with exact names: `[PROJECT 1 — EXACT NAME: ...]`
- Mark Technologies lines: `[HAS TECHNOLOGIES LINE]`
- Pre-annotate leadership section: `[→ MUST fill LATEX_LEADERSHIP_BLOCK]`

---

## Open Bugs Summary (Updated 2026-04-01)

| ID | Bug | Layer | Severity | Status |
|----|-----|-------|----------|--------|
| BUG-008 | 2 experience bullets dropped (AWS load balancing + Python/SQL dashboards) | LaTeX gen | High | OPEN |
| BUG-009 | Technologies lines missing from all 3 projects | LaTeX gen | High | OPEN |
| BUG-011 | Coursework appears as separate section (experienced candidate) | LaTeX gen | Medium | OPEN |
| BUG-012 | Project bullets cut 4-5→3 per project | LaTeX gen | High | OPEN |
| BUG-013 | Leadership & Activities entirely missing | LaTeX gen | High | OPEN |
| BUG-018 | Projects in wrong order | LaTeX gen | Medium | OPEN |
| BUG-019 | Project names truncated | LaTeX gen | Medium | OPEN |
