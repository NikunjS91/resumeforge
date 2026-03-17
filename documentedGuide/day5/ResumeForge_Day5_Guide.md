# ResumeForge — Day 5 Build Guide
## ATS Scorer Module

---

> **Agent Instructions:** Work through Pre-Tasks → Steps 1 → 6 sequentially. Do not skip.
> Read all listed files before writing any code.
> Day 5 is complete only when all 10 verification checks pass.
> After completion: commit to feature/day5-ats-scorer, merge to dev, then merge dev to main.

---

## Current System State

| Service | Status |
|---------|--------|
| Backend | Port 8000, auto-reloads on file save |
| Ollama | Port 11434, model: `qwen3:14b` |
| Git | On `dev` branch, clean |
| DB | Has users, resumes, resume_sections, jobs, tailoring_sessions rows |

---

## Before Writing Any Code — Read These Files

| File | Why |
|------|-----|
| `backend/models/tailoring_session.py` | Has `ats_score`, `matched_keywords_json`, `missing_keywords_json`, `score_breakdown_json` columns — use these |
| `backend/models/job.py` | `required_skills_json`, `nicetohave_skills_json` stored as Text — always json.loads() |
| `backend/models/resume_section.py` | `content_text`, `section_type` — what we score against |
| `backend/routers/score.py` | Current stub — replace it |
| `backend/routers/tailor.py` | Reference for endpoint pattern |
| `backend/modules/analyze/jd_analyzer.py` | Reference for qwen3:14b call pattern + think tag stripping |

---

## Pre-Tasks — Fix Carry-overs from Day 4

### Pre-Task A — Fix Skills Bleeding (Technologies: lines)

**File:** `backend/modules/parse/section_detector.py`

Find `MULTI_ITEM_SECTIONS` and update the section splitter logic.
The root issue: when inside a `projects` block, lines starting with
`Technologies:`, `Tech Stack:`, `Tools:`, `Stack:` are being treated
as new section headings instead of content lines.

Find the section splitting loop where blocks are being labeled.
Add this guard: if the current section is `projects` and the next
heading candidate starts with any of these prefixes, skip it —
treat it as content of the current project block.

```python
# Add to CONTENT_LINE_SIGNALS if not already present
SKIP_AS_HEADING_IN_PROJECTS = {
    "technologies:",
    "tech stack:",
    "stack:",
    "tools:",
    "frameworks:",
    "languages:",
}

# In the splitting logic, before creating a new section:
# if current_section_type == "projects" and candidate.lower().strip() in SKIP_AS_HEADING_IN_PROJECTS:
#     continue  # treat as content, not a heading
```

**Verify after fix:**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
types = [s['section_type'] for s in d['sections']]
print(f'section_count: {d[\"section_count\"]} (should be 6)')
print(f'skills_count:  {types.count(\"skills\")} (should be 1)')
print(f'unknown_count: {sum(1 for t in types if t == \"unknown\")} (should be 0)')
print(f'types: {types}')
"
# Expected: section_count=6, skills=1, unknown=0
```

### Pre-Task B — Create feature branch

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git checkout dev
git checkout -b feature/day5-ats-scorer
```

---

## What Day 5 Builds

The ATS Scorer compares a resume (or a tailoring session) against a job description
and produces:
- **ATS score** (0-100) — how well the resume matches the JD
- **Matched keywords** — skills from JD found in resume (green)
- **Missing keywords** — required skills NOT found in resume (red)
- **Section breakdown** — per-section match analysis
- Saves results to `tailoring_sessions` table

**New route:** `POST /api/score/ats`
**Input:** `resume_id` + `job_id` (optional: `session_id` to score a tailored version)
**Output:** Score, matched/missing keywords, breakdown

---

## Step 1 — No New Dependencies

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
pip list | grep -E "fastapi|sqlalchemy|requests"
# All present — no new installs needed
```

---

## Step 2 — Build the ATS Scorer Module

**Create:** `backend/modules/score/__init__.py` (empty)

**Create:** `backend/modules/score/ats_scorer.py`

```python
import re
import json
import logging

logger = logging.getLogger(__name__)


# ─── KEYWORD NORMALIZER ──────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def keyword_variants(keyword: str) -> list[str]:
    """
    Generate common variants of a keyword for fuzzy matching.
    e.g. 'GitHub Actions' → ['github actions', 'github-actions', 'githubactions']
    """
    kw = normalize(keyword)
    variants = {kw}
    variants.add(kw.replace(' ', '-'))
    variants.add(kw.replace(' ', ''))
    variants.add(kw.replace('.', ''))
    # Common abbreviations
    abbreviations = {
        'kubernetes': ['k8s'],
        'javascript': ['js'],
        'typescript': ['ts'],
        'postgresql': ['postgres', 'psql'],
        'amazon web services': ['aws'],
        'continuous integration': ['ci'],
        'continuous deployment': ['cd'],
        'infrastructure as code': ['iac'],
    }
    for full, abbrs in abbreviations.items():
        if full in kw:
            variants.update(abbrs)
        for abbr in abbrs:
            if abbr == kw:
                variants.add(full)
    return list(variants)


def keyword_in_text(keyword: str, text: str) -> bool:
    """Check if keyword or any of its variants appear in text."""
    normalized_text = normalize(text)
    for variant in keyword_variants(keyword):
        if variant in normalized_text:
            return True
    return False


# ─── SECTION WEIGHTS ─────────────────────────────────────────────────────────

SECTION_WEIGHTS = {
    "skills":     0.35,   # highest — skills section is most ATS-scanned
    "experience": 0.30,   # second — work experience keywords matter most
    "projects":   0.20,   # third — projects show practical usage
    "summary":    0.10,   # fourth — summary keywords help
    "leadership": 0.03,   # minor
    "education":  0.02,   # minor
    "contact":    0.00,   # not scored
    "unknown":    0.05,   # small weight for unknown sections
}


# ─── MAIN SCORER ─────────────────────────────────────────────────────────────

def score_resume(
    resume_sections: list,
    required_skills: list,
    nice_to_have_skills: list,
    job_title: str = "",
    company_name: str = "",
) -> dict:
    """
    Score a resume against job requirements.

    Args:
        resume_sections: list of dicts with section_type and content_text
        required_skills: list of required skill strings from JD
        nice_to_have_skills: list of nice-to-have skill strings from JD
        job_title: job title string for additional keyword matching
        company_name: company name (informational)

    Returns:
        dict with ats_score, matched_keywords, missing_keywords,
        score_breakdown, recommendation
    """
    if not resume_sections:
        raise ValueError("No resume sections provided")

    if not required_skills:
        return {
            "ats_score": 0,
            "matched_keywords": [],
            "missing_keywords": [],
            "nicetohave_matched": [],
            "nicetohave_missing": nice_to_have_skills or [],
            "score_breakdown": {},
            "recommendation": "No required skills found in job description to score against.",
            "required_count": 0,
            "matched_count": 0,
        }

    # Build full resume text and per-section text
    full_resume_text = " ".join(
        s.get("content_text", "") for s in resume_sections
    )

    # ── Score required skills ───────────────────────────────────────
    matched_required = []
    missing_required = []

    for skill in required_skills:
        if keyword_in_text(skill, full_resume_text):
            matched_required.append(skill)
        else:
            missing_required.append(skill)

    # ── Score nice-to-have skills ───────────────────────────────────
    matched_nicetohave = []
    missing_nicetohave = []

    for skill in nice_to_have_skills:
        if keyword_in_text(skill, full_resume_text):
            matched_nicetohave.append(skill)
        else:
            missing_nicetohave.append(skill)

    # ── Per-section breakdown ────────────────────────────────────────
    all_skills = required_skills + nice_to_have_skills
    breakdown = {}

    for section in resume_sections:
        sec_type = section.get("section_type", "unknown")
        content = section.get("content_text", "")
        label = section.get("section_label", sec_type)

        if not content.strip() or sec_type == "contact":
            continue

        sec_matched = [s for s in all_skills if keyword_in_text(s, content)]
        weight = SECTION_WEIGHTS.get(sec_type, 0.05)

        breakdown[sec_type] = {
            "label": label,
            "matched_skills": sec_matched,
            "matched_count": len(sec_matched),
            "weight": weight,
        }

    # ── Calculate ATS score ──────────────────────────────────────────
    # Base score: % of required skills matched (0-85 points)
    required_match_rate = len(matched_required) / len(required_skills)
    base_score = required_match_rate * 85

    # Bonus: nice-to-have skills matched (0-10 points)
    if nice_to_have_skills:
        nicetohave_rate = len(matched_nicetohave) / len(nice_to_have_skills)
        bonus_score = nicetohave_rate * 10
    else:
        bonus_score = 0

    # Bonus: job title keywords in resume (0-5 points)
    title_bonus = 0
    if job_title:
        title_words = [w for w in job_title.lower().split() if len(w) > 3]
        title_matches = sum(1 for w in title_words if w in normalize(full_resume_text))
        if title_words:
            title_bonus = (title_matches / len(title_words)) * 5

    ats_score = min(100, round(base_score + bonus_score + title_bonus))

    # ── Generate recommendation ──────────────────────────────────────
    if ats_score >= 80:
        recommendation = "Excellent match! Your resume is well-optimized for this role."
    elif ats_score >= 60:
        recommendation = f"Good match. Consider adding these missing skills where applicable: {', '.join(missing_required[:5])}"
    elif ats_score >= 40:
        recommendation = f"Moderate match. Key missing skills: {', '.join(missing_required[:8])}. Tailor your resume more specifically."
    else:
        recommendation = f"Low match. Many required skills are missing: {', '.join(missing_required[:10])}. Consider using the Resume Tailor first."

    return {
        "ats_score":           ats_score,
        "matched_keywords":    matched_required,
        "missing_keywords":    missing_required,
        "nicetohave_matched":  matched_nicetohave,
        "nicetohave_missing":  missing_nicetohave,
        "score_breakdown":     breakdown,
        "recommendation":      recommendation,
        "required_count":      len(required_skills),
        "matched_count":       len(matched_required),
        "match_rate":          round(required_match_rate * 100, 1),
    }
```

---

## Step 3 — Build the Score Endpoint

**Modify:** `backend/routers/score.py` — replace the stub with full implementation.

### 3a — Imports

```python
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models.tailoring_session import TailoringSession
from models.resume import Resume
from models.resume_section import ResumeSection
from models.job import Job
from models.user import User
from routers.auth import get_current_user
from modules.score.ats_scorer import score_resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/score", tags=["ATS Scorer"])
```

### 3b — Request Schema

```python
class ATSScoreRequest(BaseModel):
    resume_id: int
    job_id: int
    session_id: Optional[int] = None  # if provided, score the tailored version

    class Config:
        json_schema_extra = {
            "example": {
                "resume_id": 2,
                "job_id": 1,
                "session_id": None
            }
        }
```

### 3c — Keep Status Stub

```python
@router.get("/status")
def score_status():
    return {"status": "not implemented yet", "module": "ats_scorer"}
```

### 3d — Full ATS Score Endpoint

```python
@router.post("/ats")
def score_ats(
    request: ATSScoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate resume ───────────────────────────────────────────
    resume = db.query(Resume).filter(
        Resume.id == request.resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume {request.resume_id} not found."
        )

    # ── 2. Validate job ──────────────────────────────────────────────
    job = db.query(Job).filter(
        Job.id == request.job_id,
        Job.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {request.job_id} not found."
        )

    # ── 3. Load sections (original or tailored) ──────────────────────
    if request.session_id:
        # Score the tailored version from a tailoring session
        session = db.query(TailoringSession).filter(
            TailoringSession.id == request.session_id,
            TailoringSession.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tailoring session {request.session_id} not found."
            )
        # Parse tailored sections from JSON
        try:
            tailored_data = json.loads(session.tailored_json or "{}")
            sections_data = [
                {
                    "section_type": s.get("section_type"),
                    "section_label": s.get("section_label"),
                    "content_text": s.get("tailored_text", ""),
                    "position_index": s.get("position_index", 0),
                }
                for s in tailored_data.get("sections", [])
            ]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse tailored session data: {e}"
            )
        scoring_source = "tailored"
    else:
        # Score the original resume sections
        db_sections = db.query(ResumeSection).filter(
            ResumeSection.resume_id == resume.id
        ).order_by(ResumeSection.position_index).all()

        if not db_sections:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Resume has no sections. Upload and parse the resume first."
            )

        sections_data = [
            {
                "section_type": s.section_type,
                "section_label": s.section_label,
                "content_text": s.content_text,
                "position_index": s.position_index,
            }
            for s in db_sections
        ]
        scoring_source = "original"

    # ── 4. Parse skills from job ─────────────────────────────────────
    try:
        required_skills = json.loads(job.required_skills_json or "[]")
    except Exception:
        required_skills = []
    try:
        nice_to_have_skills = json.loads(job.nicetohave_skills_json or "[]")
    except Exception:
        nice_to_have_skills = []

    if not required_skills:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job has no required skills. Analyze the job description first."
        )

    # ── 5. Run ATS scorer ────────────────────────────────────────────
    try:
        result = score_resume(
            resume_sections=sections_data,
            required_skills=required_skills,
            nice_to_have_skills=nice_to_have_skills,
            job_title=job.job_title or "",
            company_name=job.company_name or "",
        )
    except Exception as e:
        logger.error(f"ATS scoring failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring failed: {str(e)}"
        )

    # ── 6. Save to DB if session_id provided, else create new record ─
    if request.session_id and session:
        session.ats_score = result["ats_score"]
        session.matched_keywords_json = json.dumps(result["matched_keywords"])
        session.missing_keywords_json = json.dumps(result["missing_keywords"])
        session.score_breakdown_json  = json.dumps(result["score_breakdown"])
        db.commit()
        logger.info(f"Updated tailoring_session {session.id} with ATS score={result['ats_score']}")
    else:
        # Create a new lightweight tailoring session just for the score
        new_session = TailoringSession(
            user_id=current_user.id,
            resume_id=resume.id,
            job_id=job.id,
            tailored_text="",
            tailored_json="{}",
            ai_provider="none",
            ai_model="ats_scorer_v1",
            ats_score=result["ats_score"],
            matched_keywords_json=json.dumps(result["matched_keywords"]),
            missing_keywords_json=json.dumps(result["missing_keywords"]),
            score_breakdown_json=json.dumps(result["score_breakdown"]),
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        logger.info(f"Created score session {new_session.id}, ATS score={result['ats_score']}")

    # ── 7. Return response ───────────────────────────────────────────
    return {
        "resume_id":         resume.id,
        "resume_name":       resume.name,
        "job_id":            job.id,
        "job_title":         job.job_title,
        "company_name":      job.company_name,
        "scoring_source":    scoring_source,
        "session_id":        request.session_id,
        "ats_score":         result["ats_score"],
        "match_rate":        result["match_rate"],
        "required_count":    result["required_count"],
        "matched_count":     result["matched_count"],
        "matched_keywords":  result["matched_keywords"],
        "missing_keywords":  result["missing_keywords"],
        "nicetohave_matched": result["nicetohave_matched"],
        "nicetohave_missing": result["nicetohave_missing"],
        "score_breakdown":   result["score_breakdown"],
        "recommendation":    result["recommendation"],
    }
```

---

## Step 4 — Register Router in main.py

**File:** `backend/main.py`

Check if score router is already imported. If not, add:

```python
from routers.score import router as score_router
app.include_router(score_router)
```

If already registered as a stub, it will auto-update since uvicorn --reload is running.

---

## Step 5 — Verify Day 1-4 Still Intact

```bash
for route in /health /api/parse/status /api/analyze/status /api/tailor/status /api/score/status; do
  echo -n "$route: "
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$route
  echo
done
# Expected: all 200
```

---

## Step 6 — Verification Checklist (All 10 Must Pass)

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

### Check 1 — Module files exist

```bash
ls backend/modules/score/
# Expected: __init__.py  ats_scorer.py
```

---

### Check 2 — No auth → 401

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/score/ats \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 2, "job_id": 1}'
# Expected: 401
```

---

### Check 3 — Invalid resume → 404

```bash
curl -s -X POST http://localhost:8000/api/score/ats \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 9999, "job_id": 1}' | python3 -m json.tool
# Expected: 404
```

---

### Check 4 — Valid score → 200 with all fields

```bash
curl -s -X POST http://localhost:8000/api/score/ats \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 2, "job_id": 1}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'ats_score:        {d[\"ats_score\"]} / 100')
print(f'match_rate:       {d[\"match_rate\"]}%')
print(f'required_count:   {d[\"required_count\"]}')
print(f'matched_count:    {d[\"matched_count\"]}')
print(f'matched:          {d[\"matched_keywords\"]}')
print(f'missing:          {d[\"missing_keywords\"]}')
print(f'nicetohave_match: {d[\"nicetohave_matched\"]}')
print(f'scoring_source:   {d[\"scoring_source\"]}')
print(f'recommendation:   {d[\"recommendation\"]}')
print()
passed = d['ats_score'] > 0 and d['matched_count'] > 0
print('PASS' if passed else 'FAIL')
"
# Expected: ats_score > 0, matched_count > 0, all fields present
```

---

### Check 5 — Score a tailored session (session_id provided)

```bash
# Get latest tailoring session id
SESSION_ID=$(python3 -c "
import sqlite3
conn = sqlite3.connect('backend/data/resumeforge.db')
row = conn.execute('SELECT id FROM tailoring_sessions WHERE user_id=3 AND tailored_text != \"\" ORDER BY id DESC LIMIT 1').fetchone()
print(row[0])
conn.close()
")
echo "Using session_id=$SESSION_ID"

curl -s -X POST http://localhost:8000/api/score/ats \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"resume_id\": 2, \"job_id\": 1, \"session_id\": $SESSION_ID}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'scoring_source: {d[\"scoring_source\"]} (should be tailored)')
print(f'ats_score:      {d[\"ats_score\"]}')
print(f'matched:        {d[\"matched_keywords\"]}')
print(f'missing:        {d[\"missing_keywords\"]}')
"
# Expected: scoring_source=tailored, ats_score present
```

---

### Check 6 — Score saved to tailoring_sessions table

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('backend/data/resumeforge.db')
rows = conn.execute(
  'SELECT id, ats_score, matched_keywords_json, missing_keywords_json FROM tailoring_sessions WHERE ats_score IS NOT NULL ORDER BY id DESC LIMIT 3'
).fetchall()
for r in rows:
  import json
  matched = json.loads(r[2] or '[]')
  missing = json.loads(r[3] or '[]')
  print(f'session {r[0]}: score={r[1]}, matched={len(matched)}, missing={len(missing)}')
conn.close()
"
# Expected: rows with ats_score values, matched/missing keyword lists
```

---

### Check 7 — Pre-task A: Skills count fixed

```bash
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
types = [s['section_type'] for s in d['sections']]
skills_count = types.count('skills')
unknown_count = sum(1 for t in types if t == 'unknown')
print(f'section_count: {d[\"section_count\"]}')
print(f'skills_count:  {skills_count} (should be 1)')
print(f'unknown_count: {unknown_count} (should be 0)')
print('PASS' if skills_count == 1 and unknown_count == 0 else 'FAIL — skills bleeding still present')
"
```

---

### Check 8 — Score comparison: original vs tailored

```bash
# Score original
ORIGINAL=$(curl -s -X POST http://localhost:8000/api/score/ats \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 2, "job_id": 1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['ats_score'])")

# Score tailored (use session from check 5)
TAILORED=$(curl -s -X POST http://localhost:8000/api/score/ats \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"resume_id\": 2, \"job_id\": 1, \"session_id\": $SESSION_ID}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['ats_score'])")

echo "Original ATS score:  $ORIGINAL"
echo "Tailored ATS score:  $TAILORED"
echo "Improvement: $((TAILORED - ORIGINAL)) points"
# Expected: tailored score >= original score
```

---

### Check 9 — GET /api/score/status still returns 200

```bash
curl http://localhost:8000/api/score/status
# Expected: {"status": "not implemented yet", "module": "ats_scorer"}
```

---

### Check 10 — All routes intact

```bash
for route in /health /api/parse/status /api/analyze/status /api/tailor/status /api/score/status /api/export/status; do
  echo -n "$route: "
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$route
  echo
done
# Expected: all 200
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `POST /api/score/ats` returns 404 on route | Check `main.py` — score router may not be registered |
| `Job has no required skills` | Job was analyzed but skills extraction failed. Re-analyze with `POST /api/analyze/job` |
| `ats_score` is 0 | Skills in resume don't match. Try with a freshly tailored session |
| `Resume has no sections` | Re-upload resume via `POST /api/parse/upload` first |

---

## Git — After All 10 Checks Pass

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git add backend/modules/score/
git add backend/routers/score.py
git add backend/modules/parse/section_detector.py
git commit -m "feat: Day 5 — ATS Scorer + skills bleeding fix

- POST /api/score/ats endpoint
- modules/score/ats_scorer.py — keyword matching, section weights, 0-100 scoring
- Supports scoring original resume AND tailored session
- Saves score to tailoring_sessions table
- Pre-task: fix Technologies: lines splitting skills sections
- Section weights: skills=35%, experience=30%, projects=20%, summary=10%"

git push origin feature/day5-ats-scorer

# Merge to dev
git checkout dev
git merge feature/day5-ats-scorer
git push origin dev

# Merge dev to main (stable milestone)
git checkout main
git merge dev
git push origin main
git checkout dev
```

---

> ✅ **Day 5 complete when all 10 checks pass.**
> This is the first time dev gets merged to main since Day 1 — Days 1-5 form a complete, working pipeline.
