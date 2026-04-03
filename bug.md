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

**Status:** FIXED
**Severity:** Low
**Found:** 2026-03-31 Playwright test
**Location:** `frontend/src/pages/Login.jsx`

### Description
Browser logs a warning on the login page:
```
[DOM] Input elements should have autocomplete attributes (suggested: "current-password")
```

### Fix Applied
`autoComplete="current-password"` already present on the password input in `Login.jsx:38`. No change needed.

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

---

## Day 15 — New Bugs Found (2026-04-02 Playwright PDF comparison)

> Compared: `Resume_10March.pdf` (original) vs `tailored_Resume_10March_113.tex` (session 113)

---

## BUG-020 — Section Order Wrong (Experience Before Education)

**Status:** FIXED
**Severity:** High
**Found:** 2026-04-02 Playwright session
**Location:** `backend/templates/professional.tex`, `backend/modules/export/latex_generator.py`

### Description
| | Original PDF | Generated PDF |
|---|---|---|
| Order | Education → Skills → Experience → Projects → Leadership | Experience → Skills → Projects → Education → Leadership |

Original is a student resume (Expected May 2026). Education should come first.

### Root Cause
Two compounding issues:
1. `detect_candidate_type()` returns `'experienced'` for any candidate with >200 chars of experience content — ignores that the degree is still in progress ("Expected May 2026")
2. `professional.tex` template hardcodes Experience as the first section via placeholder order
3. `build_stage1_prompt` FINAL REMINDER explicitly says "SECTION ORDER (experienced): Experience → Skills → Projects → Education → Leadership"

---

## BUG-021 — Missing Bachelor's Degree (Bharati Vidyapeeth Entirely Absent)

**Status:** FIXED
**Severity:** High
**Found:** 2026-04-02 Playwright session
**Location:** `backend/modules/export/latex_generator.py` → `build_data_summary`, `post_process_latex`

### Description
Original PDF has two education entries:
1. Pace University — Master of Science | GPA: 3.84/4.0 | Expected May 2026
2. Bharati Vidyapeeth — Bachelor of Technology | GPA: 3.56/4.0 | July 2023

Generated output has only Pace University. Bharati Vidyapeeth is completely absent.

### Root Cause
The PDF parser creates a section boundary at "Relevant Coursework:" and assigns everything after it (including Bharati Vidyapeeth) to a `coursework` section. DB confirms:
- `education` section content_text = Pace University only
- `coursework` section content_text = **Bharati Vidyapeeth + Bachelor's degree**

In `build_data_summary`, line 249-250:
```python
if sec_type == 'coursework' and candidate_type == 'experienced':
    continue  # strips the entire section including Bachelor's data
```
Since the candidate is misclassified as 'experienced' (BUG-020), the coursework section (containing the bachelor's degree) is silently dropped. No post-processor rebuilds education from both sections.

---

## BUG-022 — Duplicate Leadership & Activities Section Header

**Status:** FIXED
**Severity:** Medium
**Found:** 2026-04-02 Playwright session
**Location:** `backend/modules/export/latex_generator.py` → `_build_leadership_latex`, `_replace_latex_section`

### Description
Generated .tex has two consecutive `\resumesection{Leadership \& Activities}` headers (lines 99–100), rendering as a double underlined section title in the PDF.

### Root Cause
`_build_leadership_latex()` starts its output with `\resumesection{Leadership \& Activities}`.
`_replace_latex_section()` preserves the existing `\resumesection` from LLM output as `m.group(1)` and prepends it to `new_content`. Since `new_content` also starts with the section header, the result contains two headers.

---

## BUG-023 — Relevant Coursework Entirely Missing

**Status:** FIXED
**Severity:** Medium
**Found:** 2026-04-02 Playwright session
**Location:** `backend/modules/export/latex_generator.py` → `detect_candidate_type`, `build_data_summary`

### Description
Original PDF shows "Relevant Coursework: Distributed Systems, Cloud Architecture, Microservices, Database Systems, Software Engineering" inline under the Pace University education entry. Generated output has no coursework at all.

### Root Cause
`detect_candidate_type()` returns `'experienced'` → `build_data_summary` strips the `coursework` section entirely for experienced candidates (line 249). The actual coursework subjects are in the section label ("Relevant Coursework: Distributed Systems..."), not passed to the LLM. Also directly linked to BUG-021 (parser puts Bharati Vidyapeeth inside the coursework section).

---

## BUG-024 — CodeChef Leadership Entry Wrong (Dates and Description Stripped)

**Status:** FIXED
**Severity:** High
**Found:** 2026-04-02 Playwright session
**Location:** `backend/modules/tailor/resume_tailor.py`, `backend/modules/export/latex_generator.py`

### Description
Original PDF has two distinct Leadership entries:
1. AWS Cloud Club, Technical Contributor — Sept 2024 – Present (with description)
2. CodeChef Programming Club, Technical Mentor — Bharati Vidyapeeth — Jan 2022 – May 2023 (with "Mentored 30+ students..." bullet)

Generated output has ONE entry (AWS) with CodeChef embedded as a bullet item without dates or description.

### Root Cause (3-part)
**Part 1 — Tailoring strips dates:**  
`'leadership'` is included in `tailorable_types` set in `resume_tailor.py`. NVIDIA NIM rewrites the leadership section and removes the CodeChef dates ("Jan 2022 – May 2023") and description. DB confirms tailored_text = "...CodeChef Programming Club, Technical Mentor — Bharati Vidyapeeth Deemed University" (no date, no mentor bullet).

**Part 2 — `_build_leadership_latex` silently drops dateless lines:**  
The post-processor detects headings by date presence. CodeChef without dates → `has_date = False` → `else: i += 1` (silently skipped). Instead, the CodeChef line falls into the previous entry's description loop and becomes a bullet under AWS Cloud Club.

**Part 3 — `export.py` reads wrong key (`content_text` vs `original_text`):**  
Tailored JSON sections store original data under `original_text`, not `content_text`. The fix to use "original content for leadership" was checking `s.get("content_text", "")` which always returned `""`. The leadership section either passed through with empty content or was filtered out entirely. Fix: use `s.get("original_text", s.get("content_text", ""))` in both sync and async paths in `export.py`.

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

---

## BUG-025 — ATSScore Fires Twice (hasFired Ref Guard Bypassed)

**Status:** OPEN
**Severity:** Medium
**Found:** 2026-04-03 Playwright session
**Location:** `frontend/src/components/ATSScore.jsx`, `frontend/src/pages/Dashboard.jsx`

### Description
During the full pipeline run (Steps 1–5), the ATS scoring API is called **twice** for the same session. Both calls use the same props (resumeId, jobId, sessionId). Observed in browser console:
- First call: at ~293s (correct — triggered by "Check ATS Score →" click)
- Second call: at ~493s (~200s later, during the PDF export phase)

### Observed Symptom
```
🔍 ATSScore: Starting scoreBoth() {resumeId: 50, jobId: 88, sessionId: 116}  ← first
🔍 ATSScore: Starting scoreBoth() {resumeId: 50, jobId: 88, sessionId: 116}  ← second (200s later)
```

### Root Cause
The `hasFired = useRef(false)` guard in `ATSScore.jsx` resets to `false` when the component unmounts and remounts. Something during the export phase (when `step5Active` flips to `true`) causes the ATSScore component to unmount and remount, bypassing the guard. Exact trigger is unconfirmed — likely related to Dashboard's React reconciliation when `ExportPanel` mounts alongside ATSScore.

### Impact
- 2× API calls to `/api/score/ats` per pipeline run
- History page gains an extra `ats_scorer_v1` session entry with no PDF (the orphan score-only row visible in History)

### Fix Applied
Replaced the `hasFired = useRef(false)` guard (which resets on remount) with two module-level maps outside React's lifecycle:
- `_pending: Map<sessionId, Promise>` — stores the in-flight `Promise.all` for both requests
- `_results: Map<sessionId, {original, tailored}>` — stores completed results

**On first mount:** creates the shared promise, subscribes to it.  
**On StrictMode double-invoke / remount while in-flight:** finds existing promise in `_pending`, subscribes to it — no duplicate API calls.  
**On remount after completion:** finds data in `_results`, restores state immediately and calls `onScored` — no API call at all.  
**On error:** deletes from `_pending` to allow retry on next render.  
Also added `cancelled` cleanup flag to prevent setState after unmount.

---

## Open Bugs Summary (Updated 2026-04-03 — Day 16)

| ID | Bug | Layer | Severity | Status |
|----|-----|-------|----------|--------|
| BUG-008 | 2 experience bullets dropped | LaTeX gen | High | **FIXED** — post_process_latex after Stage 2 |
| BUG-009 | Technologies lines missing from all 3 projects | LaTeX gen | High | **FIXED** — _build_projects_latex post-processor |
| BUG-011 | Coursework appears as separate section | LaTeX gen | Medium | **FIXED** — strip from source data |
| BUG-012 | Project bullets cut 4-5→3 per project | LaTeX gen | High | **FIXED** — _build_projects_latex post-processor |
| BUG-013 | Leadership & Activities entirely missing | LaTeX gen | High | **FIXED** — _build_leadership_latex post-processor |
| BUG-018 | Projects in wrong order | LaTeX gen | Medium | **FIXED** — post-processor preserves source order |
| BUG-019 | Project names truncated | LaTeX gen | Medium | **FIXED** — post-processor uses exact names from source |
| BUG-020 | Section order wrong (Experience before Education) | Template + detect | High | **FIXED** — `professional.tex` reordered; `detect_candidate_type` checks Expected date |
| BUG-021 | Missing Bachelor's degree (Bharati Vidyapeeth) | Parser + gen | High | **FIXED** — `_build_education_latex` reads both education + coursework sections |
| BUG-022 | Duplicate Leadership section header | post_process | Medium | **FIXED** — removed `\resumesection` from `_build_leadership_latex` output |
| BUG-023 | Relevant Coursework entirely missing | detect + gen | Medium | **FIXED** — candidate now 'fresher'; coursework inlined in `_build_education_latex` |
| BUG-024 | CodeChef entry wrong (dates stripped by tailor) | Tailor + post_process + export | High | **FIXED** — `leadership` removed from `TAILORABLE_SECTIONS`; `_build_leadership_latex` handles dateless headings; `export.py` now reads `original_text` key (not `content_text`) |
| BUG-025 | ATSScore fires twice — hasFired ref reset on remount during export | ATSScore.jsx | Medium | **FIXED** — module-level promise cache (`_pending`/`_results`); remounts subscribe to same in-flight promise, no duplicate API calls |
