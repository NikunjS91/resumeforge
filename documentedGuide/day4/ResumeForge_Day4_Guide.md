# ResumeForge — Day 4 Build Guide
## Resume Tailor Module

---

> **Agent Instructions:** Work through Pre-Task → Steps 1 → 6 sequentially. Do not skip.
> Read all listed files before writing any code.
> Server and Ollama must be running before verification.
> Day 4 is complete only when all 10 verification checks pass.
> After completion: commit to feature/day4-resume-tailor branch, merge to dev.

---

## Current System State

| Service | Status |
|---------|--------|
| Backend | Port 8000, auto-reloads on file save |
| Ollama | Port 11434, model: `qwen3:14b` |
| DB | `backend/data/resumeforge.db` — users, resumes, resume_sections, jobs tables populated |
| Git | Working on `dev` branch |

---

## Before Writing Any Code — Read These Files

| File | Why |
|------|-----|
| `backend/models/tailoring_session.py` | TailoringSession model — exact field names |
| `backend/models/resume.py` | Resume model — how to read resume data |
| `backend/models/job.py` | Job model — how to read JD data |
| `backend/schemas/tailoring_session.py` | Existing schemas — do not duplicate |
| `backend/routers/tailor.py` | Current stub — you will replace it |
| `backend/routers/auth.py` | Copy `get_current_user` dependency |
| `backend/routers/analyze.py` | Reference for Day 3 endpoint pattern |
| `backend/database.py` | Import `get_db` from here |
| `backend/modules/analyze/jd_analyzer.py` | Reference — see how qwen3:14b is called |
| `backend/modules/parse/section_detector.py` | Reference — see think-tag stripping + 180s timeout |

---

## Pre-Task — Fix `is_remote` Bug (Carry-over from Day 3)

**File:** `backend/modules/analyze/jd_analyzer.py`

In `REMOTE_PATTERNS`, remove `r'\bhybrid\b'` — hybrid means office + remote, not fully remote:

```python
REMOTE_PATTERNS = [
    r'\bremote\b',
    r'\bwork from home\b',
    r'\bwfh\b',
    r'\bfully remote\b',
    r'\b100% remote\b',
]
```

Also create the Day 4 feature branch before writing any code:

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git checkout dev
git checkout -b feature/day4-resume-tailor
```

---

## What Day 4 Builds

The Resume Tailor takes a `resume_id` + `job_id` and uses qwen3:14b to intelligently rewrite the resume's experience, projects, and skills sections to better match the job description — highlighting relevant keywords, quantified achievements, and matching technologies.

**New route:** `POST /api/tailor/resume`
**Input:** `resume_id` + `job_id`
**Output:** Tailored resume text + per-section rewrites + ATS improvement notes
**Saves to:** `tailoring_sessions` table

---

## Step 1 — No New Dependencies

Day 4 uses only what's already installed. Verify:

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
pip list | grep -E "sqlalchemy|fastapi|requests"
```

---

## Step 2 — Build the Tailor Module

**Create:** `backend/modules/tailor/__init__.py` (empty)

**Create:** `backend/modules/tailor/resume_tailor.py`

```python
import re
import json
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:14b"
TIMEOUT = 180


# ─── OLLAMA HELPERS ──────────────────────────────────────────────────────────

def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def ollama_call(prompt: str) -> str | None:
    """Call qwen3:14b, strip think tags, return clean response."""
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": DEFAULT_MODEL, "prompt": prompt, "stream": False},
            timeout=TIMEOUT
        )
        response = r.json().get("response", "").strip()
        # Strip qwen3 thinking tags
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        return response if response else None
    except Exception as e:
        logger.warning(f"Ollama call error: {e}")
        return None


# ─── SECTION TAILOR ──────────────────────────────────────────────────────────

def tailor_section(
    section_type: str,
    section_content: str,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
) -> dict:
    """
    Tailor a single resume section to match the job description.
    Returns dict with tailored_text and improvement_notes.
    """
    all_skills = required_skills + nice_to_have_skills
    skills_str = ", ".join(all_skills[:20]) if all_skills else "not specified"

    prompt = (
        f"You are an expert resume writer. Rewrite this resume {section_type} section "
        f"to better match a {job_title} role at {company_name}.\n\n"
        f"Target skills to emphasize: {skills_str}\n\n"
        f"Rules:\n"
        f"- Keep all factual information accurate — do NOT invent experience or skills\n"
        f"- Emphasize existing relevant technologies and achievements\n"
        f"- Use strong action verbs (Led, Built, Architected, Optimized, Deployed)\n"
        f"- Keep quantified metrics if they exist (%, numbers, scale)\n"
        f"- Match keywords from the target skills list where truthfully applicable\n"
        f"- Keep roughly the same length as the original\n"
        f"- Return ONLY the rewritten section text, no explanation\n\n"
        f"Original {section_type} section:\n{section_content}"
    )

    tailored = ollama_call(prompt)
    if not tailored:
        logger.warning(f"Failed to tailor {section_type} section — keeping original")
        tailored = section_content

    # Generate improvement notes
    notes_prompt = (
        f"Compare the original and tailored versions of this resume {section_type} section. "
        f"List 2-3 specific improvements made. Be concise.\n\n"
        f"Original:\n{section_content[:500]}\n\n"
        f"Tailored:\n{tailored[:500]}\n\n"
        f"Return ONLY a JSON array of improvement strings like: "
        f'["Added AWS keyword alignment", "Strengthened action verbs"]'
    )
    notes_raw = ollama_call(notes_prompt)
    notes = []
    if notes_raw:
        notes_raw = re.sub(r'<think>.*?</think>', '', notes_raw, flags=re.DOTALL).strip()
        try:
            if "```" in notes_raw:
                notes_raw = notes_raw.split("```")[1].lstrip("json").strip()
            notes = json.loads(notes_raw)
        except Exception:
            notes = [notes_raw[:200]] if notes_raw else []

    return {
        "section_type": section_type,
        "original_text": section_content,
        "tailored_text": tailored,
        "improvement_notes": notes,
    }


# ─── MAIN TAILOR PIPELINE ────────────────────────────────────────────────────

# Sections worth tailoring — contact and education are not tailored
TAILORABLE_SECTIONS = {"experience", "projects", "skills", "summary", "leadership"}


def tailor_resume(
    resume_sections: list,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
) -> dict:
    """
    Full tailoring pipeline.
    - Tailors experience, projects, skills, summary sections
    - Passes through contact and education unchanged
    - Returns full tailored resume dict

    resume_sections: list of dicts with keys:
        section_type, section_label, content_text, position_index
    """
    if not ollama_available():
        raise RuntimeError("Ollama is not available. Cannot tailor resume.")

    tailored_sections = []
    all_improvement_notes = []

    logger.info(f"Tailoring {len(resume_sections)} sections for {job_title} at {company_name}")

    for section in sorted(resume_sections, key=lambda s: s.get("position_index", 0)):
        section_type = section.get("section_type", "other")
        content = section.get("content_text", "")

        if section_type in TAILORABLE_SECTIONS and content.strip():
            logger.info(f"Tailoring section: {section_type}")
            result = tailor_section(
                section_type=section_type,
                section_content=content,
                job_title=job_title,
                company_name=company_name,
                required_skills=required_skills,
                nice_to_have_skills=nice_to_have_skills,
            )
            tailored_sections.append({
                "section_type": section_type,
                "section_label": section.get("section_label", section_type.title()),
                "position_index": section.get("position_index", 0),
                "original_text": result["original_text"],
                "tailored_text": result["tailored_text"],
                "was_tailored": True,
                "improvement_notes": result["improvement_notes"],
            })
            all_improvement_notes.extend(result["improvement_notes"])
        else:
            # Pass through unchanged
            tailored_sections.append({
                "section_type": section_type,
                "section_label": section.get("section_label", section_type.title()),
                "position_index": section.get("position_index", 0),
                "original_text": content,
                "tailored_text": content,
                "was_tailored": False,
                "improvement_notes": [],
            })

    # Build full tailored text
    full_tailored = "\n\n".join(
        f"{s['section_label']}\n{s['tailored_text']}"
        for s in sorted(tailored_sections, key=lambda s: s["position_index"])
        if s["tailored_text"]
    )

    return {
        "tailored_sections": tailored_sections,
        "tailored_full_text": full_tailored,
        "sections_tailored": sum(1 for s in tailored_sections if s["was_tailored"]),
        "total_sections": len(tailored_sections),
        "improvement_notes": all_improvement_notes,
    }
```

---

## Step 3 — Build the Tailor Endpoint

**Modify:** `backend/routers/tailor.py` — replace the stub with full implementation.
Keep `GET /api/tailor/status` intact.

### 3a — Imports & Router

```python
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models.tailoring_session import TailoringSession
from models.resume import Resume
from models.resume_section import ResumeSection
from models.job import Job
from models.user import User
from routers.auth import get_current_user
from modules.tailor.resume_tailor import tailor_resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tailor", tags=["Resume Tailor"])
```

### 3b — Request Schema

```python
class TailorRequest(BaseModel):
    resume_id: int
    job_id: int

    class Config:
        json_schema_extra = {
            "example": {
                "resume_id": 1,
                "job_id": 1
            }
        }
```

### 3c — Keep Status Stub

```python
@router.get("/status")
def tailor_status():
    return {"status": "not implemented yet", "module": "resume_tailor"}
```

### 3d — Full Tailor Endpoint

```python
@router.post("/resume")
def tailor_resume_endpoint(
    request: TailorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate resume belongs to user ──────────────────────────
    resume = db.query(Resume).filter(
        Resume.id == request.resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume {request.resume_id} not found or does not belong to you."
        )

    # ── 2. Validate job belongs to user ─────────────────────────────
    job = db.query(Job).filter(
        Job.id == request.job_id,
        Job.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {request.job_id} not found or does not belong to you."
        )

    # ── 3. Load resume sections ──────────────────────────────────────
    sections = db.query(ResumeSection).filter(
        ResumeSection.resume_id == resume.id
    ).order_by(ResumeSection.position_index).all()

    if not sections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Resume has no sections. Please upload and parse the resume first."
        )

    # ── 4. Parse skills from job ─────────────────────────────────────
    # Skills stored as JSON strings in DB — deserialize
    try:
        required_skills = json.loads(job.required_skills_json or "[]")
    except Exception:
        required_skills = []
    try:
        nice_to_have_skills = json.loads(job.nicetohave_skills_json or "[]")
    except Exception:
        nice_to_have_skills = []

    # ── 5. Build sections list for tailor module ─────────────────────
    sections_data = [
        {
            "section_type": s.section_type,
            "section_label": s.section_label,
            "content_text": s.content_text,
            "position_index": s.position_index,
        }
        for s in sections
    ]

    # ── 6. Run tailoring pipeline ────────────────────────────────────
    logger.info(
        f"Starting tailor: resume_id={resume.id}, job_id={job.id}, "
        f"user_id={current_user.id}, sections={len(sections_data)}"
    )
    try:
        result = tailor_resume(
            resume_sections=sections_data,
            job_title=job.job_title or "the role",
            company_name=job.company_name or "the company",
            required_skills=required_skills,
            nice_to_have_skills=nice_to_have_skills,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Tailoring failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tailoring failed: {str(e)}"
        )

    # ── 7. Save to tailoring_sessions table ──────────────────────────
    # Read existing TailoringSession model fields before writing
    session_record = TailoringSession(
        user_id=current_user.id,
        resume_id=resume.id,
        job_id=job.id,
        tailored_text=result["tailored_full_text"],
        tailored_json=json.dumps({
            "sections": result["tailored_sections"],
            "improvement_notes": result["improvement_notes"],
        }),
        ai_provider="ollama",
        ai_model=DEFAULT_MODEL,
    )

    # Import DEFAULT_MODEL at top of file or inline here
    from modules.tailor.resume_tailor import DEFAULT_MODEL

    db.add(session_record)
    db.commit()
    db.refresh(session_record)
    logger.info(f"Saved tailoring_session_id={session_record.id}")

    # ── 8. Return response ───────────────────────────────────────────
    return {
        "session_id": session_record.id,
        "resume_id": resume.id,
        "job_id": job.id,
        "resume_name": resume.name,
        "job_title": job.job_title,
        "company_name": job.company_name,
        "ai_model": DEFAULT_MODEL,
        "sections_tailored": result["sections_tailored"],
        "total_sections": result["total_sections"],
        "improvement_notes": result["improvement_notes"],
        "tailored_sections": [
            {
                "section_type": s["section_type"],
                "section_label": s["section_label"],
                "position_index": s["position_index"],
                "was_tailored": s["was_tailored"],
                "tailored_text": s["tailored_text"],
                "improvement_notes": s["improvement_notes"],
            }
            for s in result["tailored_sections"]
        ],
    }
```

> **Important:** Before writing, re-read `backend/models/tailoring_session.py` and confirm exact column names.
> `tailored_json` is a `Text` column — always `json.dumps()` before saving.
> `pdf_path` column exists in the model but leave it as `None` (set in Day 6).
> `ats_score`, `matched_keywords_json`, `missing_keywords_json`, `score_breakdown_json` — leave as `None` (set in Day 5).

---

## Step 4 — Update Pydantic Schemas (If Needed)

**File:** `backend/schemas/tailoring_session.py` — add if not present.

```python
from pydantic import BaseModel
from typing import List, Optional, Any

class TailoredSectionOut(BaseModel):
    section_type:      str
    section_label:     str
    position_index:    int
    was_tailored:      bool
    tailored_text:     str
    improvement_notes: List[str]

class TailorOut(BaseModel):
    session_id:        int
    resume_id:         int
    job_id:            int
    resume_name:       str
    job_title:         Optional[str]
    company_name:      Optional[str]
    ai_model:          str
    sections_tailored: int
    total_sections:    int
    improvement_notes: List[str]
    tailored_sections: List[TailoredSectionOut]

    class Config:
        from_attributes = True
```

---

## Step 5 — Verify Day 1 + 2 + 3 Still Intact

```bash
# All routes still respond
for route in /health /api/parse/status /api/analyze/status /api/tailor/status; do
  echo -n "$route: "
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$route
  echo
done
# Expected: all 200
```

---

## Step 6 — Verification Checklist (All 10 Must Pass)

> **Before checks:** Need a valid `resume_id` and `job_id` in the DB.
> Resume from Day 2 upload (id=1 or check DB).
> Job from Day 3 analyze (id=1 or check DB).

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Check existing IDs
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/resumeforge.db')
resumes = conn.execute('SELECT id, name FROM resumes').fetchall()
jobs = conn.execute('SELECT id, company_name, job_title FROM jobs').fetchall()
print('Resumes:', resumes)
print('Jobs:', jobs)
conn.close()
"
```

---

### Check 1 — Module files exist

```bash
ls backend/modules/tailor/
# Expected: __init__.py  resume_tailor.py
```

---

### Check 2 — No auth → 401

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/tailor/resume \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 1, "job_id": 1}'
# Expected: 401
```

---

### Check 3 — Invalid resume_id → 404

```bash
curl -s -X POST http://localhost:8000/api/tailor/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 9999, "job_id": 1}'
# Expected: 404 with detail message
```

---

### Check 4 — Invalid job_id → 404

```bash
curl -s -X POST http://localhost:8000/api/tailor/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 1, "job_id": 9999}'
# Expected: 404 with detail message
```

---

### Check 5 — Valid request → 200 with tailored sections

```bash
curl -s -X POST http://localhost:8000/api/tailor/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 1, "job_id": 1}' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'session_id:        {data[\"session_id\"]}')
print(f'resume_name:       {data[\"resume_name\"]}')
print(f'job_title:         {data[\"job_title\"]}')
print(f'company_name:      {data[\"company_name\"]}')
print(f'ai_model:          {data[\"ai_model\"]}')
print(f'sections_tailored: {data[\"sections_tailored\"]}')
print(f'total_sections:    {data[\"total_sections\"]}')
print(f'improvement_notes: {data[\"improvement_notes\"]}')
print()
for s in data['tailored_sections']:
    print(f'  [{s[\"position_index\"]}] {s[\"section_type\"]:15} | tailored={s[\"was_tailored\"]}')
print()
passed = data['session_id'] and data['sections_tailored'] > 0
print('PASS' if passed else 'FAIL')
"
```

**Expected:**
- `session_id`: integer
- `sections_tailored`: 3-4 (experience, projects, skills tailored)
- `ai_model`: `qwen3:14b`
- Each tailored section has `was_tailored: true`
- `improvement_notes`: list with at least 1 item

---

### Check 6 — tailoring_sessions table has row

```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/resumeforge.db')
rows = conn.execute(
  'SELECT id, resume_id, job_id, ai_model, ai_provider FROM tailoring_sessions'
).fetchall()
for r in rows: print(r)
conn.close()
"
# Expected: at least 1 row with ai_model=qwen3:14b
```

---

### Check 7 — tailored_json stored correctly

```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/resumeforge.db')
row = conn.execute(
  'SELECT tailored_json FROM tailoring_sessions ORDER BY id DESC LIMIT 1'
).fetchone()
data = json.loads(row[0])
print(f'Sections in JSON: {len(data[\"sections\"])}')
print(f'Notes in JSON:    {len(data[\"improvement_notes\"])}')
conn.close()
"
# Expected: sections > 0, valid JSON
```

---

### Check 8 — tailored experience section differs from original

```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/resumeforge.db')
row = conn.execute(
  'SELECT tailored_json FROM tailoring_sessions ORDER BY id DESC LIMIT 1'
).fetchone()
data = json.loads(row[0])
for s in data['sections']:
    if s['section_type'] == 'experience':
        same = s['original_text'] == s['tailored_text']
        print(f'Experience changed: {not same}')
        print(f'Original length:   {len(s[\"original_text\"])}')
        print(f'Tailored length:   {len(s[\"tailored_text\"])}')
        break
conn.close()
"
# Expected: Experience changed: True
```

---

### Check 9 — GET /api/tailor/status still 200

```bash
curl http://localhost:8000/api/tailor/status
# Expected: {"status": "not implemented yet", "module": "resume_tailor"}
```

---

### Check 10 — is_remote bug fixed (Pre-task verify)

```bash
curl -s -X POST http://localhost:8000/api/analyze/job \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "Software Engineer at TechCorp, San Francisco. Hybrid role 3 days in office. Requirements: Python, Docker, AWS."}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'is_remote: {d[\"is_remote\"]} (should be False)')"
# Expected: is_remote: False
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `RuntimeError: Ollama is not available` | Run `ollama serve` in terminal. Check `curl http://localhost:11434/api/tags` |
| `404 Resume not found` | Check `resumes` table for valid IDs. Use the resume_id returned from Day 2 upload |
| `404 Job not found` | Check `jobs` table for valid IDs. Use the job_id from Day 3 analyze |
| `AttributeError` on TailoringSession | Re-read `models/tailoring_session.py` — use exact column names |
| `tailored_text` same as original | Ollama call failed silently. Check `/tmp/resumeforge.log` for warnings |
| Check 5 takes 5-10 minutes | Expected — qwen3:14b tailors 3-4 sections × ~2min each. Be patient |
| `json.dumps` error | Confirm `tailored_json` is a `Text` column in model |

---

## Out of Scope for Day 4

| ❌ Out of Scope | ✅ Planned For |
|----------------|---------------|
| ATS keyword scoring | Day 5 |
| PDF export of tailored resume | Day 6 |
| Frontend upload/tailor UI | Day 7 |
| GET endpoint to list sessions | Day 7 |
| Resume comparison view | Day 7 |

---

## Git — After All Checks Pass

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git add .
git commit -m "feat: Day 4 — Resume Tailor module with qwen3:14b

- POST /api/tailor/resume endpoint
- modules/tailor/resume_tailor.py — per-section LLM rewriting
- Tailors experience, projects, skills, summary sections
- Saves to tailoring_sessions table
- Pre-task: fixed is_remote hybrid bug in jd_analyzer.py"

git push origin feature/day4-resume-tailor

# Merge to dev when verified
git checkout dev
git merge feature/day4-resume-tailor
git push origin dev
```

---

> ✅ **Day 4 complete when all 10 checks pass and changes are committed to feature/day4-resume-tailor and merged to dev.**
>
> ⚠️ **Note:** Check 5 will take 5-10 minutes — qwen3:14b tailors multiple sections sequentially. This is expected. Do not interrupt the request.
