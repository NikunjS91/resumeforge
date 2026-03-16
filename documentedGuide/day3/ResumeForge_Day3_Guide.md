# ResumeForge — Day 3 Build Guide
## Job Description Analyzer Module

---

> **Agent Instructions:** Work through Pre-Tasks → Steps 1 → 6 sequentially. Do not skip.
> Read all listed files before writing any code.
> Server and Ollama are already running — do NOT restart either unless something breaks.
> Day 3 is complete only when all 10 verification checks pass.

---

## Current System State

| Service | Status |
|---------|--------|
| Backend (uvicorn) | Running on port 8000, auto-reloads on file save |
| Ollama | Running on port 11434 |
| Models available | `llama3.2:latest`, `mistral:7b` |
| DB | `backend/data/resumeforge.db` — has users, resumes, resume_sections rows |

---

## Before Writing Any Code — Read These Files

| File | Why |
|------|-----|
| `backend/models/job.py` | Job DB model — exact field names you must use |
| `backend/schemas/job.py` | Pydantic schemas — shape the API response |
| `backend/routers/analyze.py` | Current stub — you will replace it |
| `backend/routers/auth.py` | Copy `get_current_user` dependency |
| `backend/routers/parse.py` | Reference for how Day 2 upload endpoint was built |
| `backend/database.py` | Import `get_db` from here |
| `backend/models/ai_provider_config.py` | AI provider config — read default model from here |
| `backend/main.py` | Verify analyze router is registered |

---

## Pre-Tasks — Fix Two Known Issues from Day 2

These are carry-overs from Day 2. Fix them before building anything new.

### Pre-Task A — Remove 200-char Preview Truncation

**File:** `backend/routers/parse.py`

Find this line in the upload endpoint response:

```python
"content_text": s["content_text"][:200],  # preview only
```

Replace with:

```python
"content_text": s["content_text"],
```

**Why:** The full content is stored in the DB but was being truncated in the API response, hiding education institutions, all experience bullets, and leadership entries.

### Pre-Task B — Fix PDF Hyphenation Artifact

**File:** `backend/modules/parse/extractor.py`

Add this import at the top of the file:

```python
import re
```

In `extract_pdf()`, add this line immediately after `raw_text = "\n".join(all_lines).strip()`:

```python
# Rejoin words hyphenated across PDF lines (e.g. "CloudForma-\ntion" → "CloudFormation")
raw_text = re.sub(r'-\n(\w)', r'\1', raw_text)
```

### Pre-Task Verification

```bash
# Re-upload the resume and confirm content_text is no longer truncated
# and no hyphenation artifacts in skills section
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for s in data['sections']:
    print(f'[{s[\"section_type\"]}] chars={len(s[\"content_text\"])}')
    if s['section_type'] == 'skills':
        print('  Skills preview:', s['content_text'][:120])
"
```

**Expected:** Each section has `chars > 200`. Skills preview should NOT contain `CloudForma-` hyphen artifact.

---

## What Day 3 Builds

The Job Description Analyzer takes a raw job description (pasted as plain text) and:
1. Extracts structured metadata (company, role, location, seniority, remote status)
2. Identifies required skills and nice-to-have skills
3. Saves everything to the `jobs` table
4. Returns a clean structured response

**New route:** `POST /api/analyze/job`
**Auth:** JWT required
**Input:** Plain text job description
**Output:** Structured job JSON with extracted skills

---

## Step 1 — Install Dependencies

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate

# Already installed but verify
pip list | grep -E "requests|pydantic"

# No new pip installs needed for Day 3
# We use Ollama (already running) for LLM extraction
```

---

## Step 2 — Build the JD Analyzer Module

**Create:** `backend/modules/analyze/__init__.py` (empty)

**Create:** `backend/modules/analyze/jd_analyzer.py`

This module takes raw JD text and returns structured data. It uses a two-phase approach:
- **Phase 1 — Regex extraction:** Pull company name, job title, location, remote status, seniority from common patterns
- **Phase 2 — Ollama LLM extraction:** Extract required skills, nice-to-have skills, and fill gaps regex missed

```python
import re
import json
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


# ─── OLLAMA HELPER ───────────────────────────────────────────────────────────

def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def ollama_extract(prompt: str) -> str | None:
    """Send prompt to Ollama, return response text or None on failure."""
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": DEFAULT_MODEL, "prompt": prompt, "stream": False},
            timeout=60
        )
        return r.json().get("response", "").strip()
    except Exception as e:
        logger.warning(f"Ollama extract error: {e}")
        return None


# ─── PHASE 1: REGEX EXTRACTION ───────────────────────────────────────────────

SENIORITY_PATTERNS = [
    (r'\b(intern|internship)\b', 'intern'),
    (r'\b(junior|jr\.?|entry.?level|associate)\b', 'junior'),
    (r'\b(mid.?level|intermediate)\b', 'mid'),
    (r'\b(senior|sr\.?|lead|staff|principal)\b', 'senior'),
    (r'\b(manager|director|vp|vice president|head of|architect)\b', 'manager'),
]

REMOTE_PATTERNS = [
    r'\bremote\b',
    r'\bwork from home\b',
    r'\bwfh\b',
    r'\bhybrid\b',
    r'\bfully remote\b',
]


def extract_regex(jd_text: str) -> dict:
    """Extract structured fields from JD using regex patterns."""
    lower = jd_text.lower()
    result = {
        "company_name":  None,
        "job_title":     None,
        "location":      None,
        "is_remote":     False,
        "seniority_level": None,
        "salary_range":  None,
    }

    # Remote detection
    result["is_remote"] = any(re.search(p, lower) for p in REMOTE_PATTERNS)

    # Seniority detection
    for pattern, level in SENIORITY_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            result["seniority_level"] = level
            break

    # Salary range (USD patterns)
    salary_match = re.search(
        r'\$[\d,]+(?:k)?(?:\s*[-–]\s*\$?[\d,]+(?:k)?)?(?:\s*(?:per\s+)?(?:year|yr|annually|month|hour|hr))?',
        jd_text, re.IGNORECASE
    )
    if salary_match:
        result["salary_range"] = salary_match.group(0).strip()

    return result


# ─── PHASE 2: LLM EXTRACTION ─────────────────────────────────────────────────

def extract_llm(jd_text: str, regex_result: dict) -> dict:
    """
    Use Ollama to extract company name, job title, location,
    required skills, and nice-to-have skills.
    Returns dict to merge with regex_result.
    """
    if not ollama_available():
        logger.warning("Ollama unavailable — skipping LLM extraction for JD")
        return {}

    prompt = (
        "Extract structured information from this job description.\n"
        "Return ONLY valid JSON — no explanation, no markdown, no backticks.\n"
        "Use this exact format:\n"
        "{\n"
        '  "company_name": "string or null",\n'
        '  "job_title": "string or null",\n'
        '  "location": "string or null",\n'
        '  "required_skills": ["skill1", "skill2", ...],\n'
        '  "nice_to_have_skills": ["skill1", "skill2", ...]\n'
        "}\n\n"
        "Rules:\n"
        "- required_skills: explicitly required, must-have, or listed under 'Requirements'\n"
        "- nice_to_have_skills: preferred, bonus, or listed under 'Nice to have' / 'Preferred'\n"
        "- Keep skills as short clean strings (e.g. 'Python', 'AWS', 'Docker', 'React')\n"
        "- Extract up to 20 required skills and 10 nice-to-have skills\n"
        "- If a field is not found, use null for strings or [] for lists\n\n"
        f"Job Description:\n{jd_text[:3000]}"
    )

    response = ollama_extract(prompt)
    if not response:
        return {}

    try:
        # Strip markdown fences if present
        if "```" in response:
            parts = response.split("```")
            response = parts[1] if len(parts) > 1 else parts[0]
            if response.startswith("json"):
                response = response[4:]

        data = json.loads(response.strip())
        return {
            "company_name":       data.get("company_name"),
            "job_title":          data.get("job_title"),
            "location":           data.get("location"),
            "required_skills":    data.get("required_skills", []),
            "nice_to_have_skills": data.get("nice_to_have_skills", []),
        }
    except Exception as e:
        logger.warning(f"LLM JD parse failed: {e} | response: {response[:200]}")
        return {}


# ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────

def analyze_jd(jd_text: str) -> dict:
    """
    Full JD analysis pipeline.
    Phase 1: Regex for seniority, remote, salary.
    Phase 2: Ollama LLM for company, title, location, skills.
    Merges both results — LLM values override regex where both exist.

    Returns dict ready for DB insertion into the jobs table.
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("Job description text cannot be empty")

    # Phase 1 — regex
    result = extract_regex(jd_text)
    logger.info(f"Regex extracted: seniority={result['seniority_level']}, remote={result['is_remote']}")

    # Phase 2 — LLM
    llm_data = extract_llm(jd_text, result)
    if llm_data:
        logger.info(f"LLM extracted: company={llm_data.get('company_name')}, "
                    f"title={llm_data.get('job_title')}, "
                    f"required_skills={len(llm_data.get('required_skills', []))}")
        # LLM overrides regex for overlapping fields
        for key, val in llm_data.items():
            if val:
                result[key] = val
    else:
        result["required_skills"] = []
        result["nice_to_have_skills"] = []

    result["jd_raw_text"] = jd_text.strip()
    return result
```

---

## Step 3 — Build the Analyze Endpoint

**Modify:** `backend/routers/analyze.py` — replace the stub with the full implementation.
Keep `GET /api/analyze/status` intact.

### 3a — Imports & Router Setup

```python
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models.job import Job
from models.user import User
from routers.auth import get_current_user
from modules.analyze.jd_analyzer import analyze_jd

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyze", tags=["Job Analyzer"])
```

### 3b — Request Schema

```python
class JDAnalyzeRequest(BaseModel):
    jd_text: str

    class Config:
        json_schema_extra = {
            "example": {
                "jd_text": "We are looking for a Senior Cloud Engineer at Acme Corp..."
            }
        }
```

### 3c — Keep Existing Status Stub

```python
@router.get("/status")
def analyze_status():
    return {"status": "not implemented yet", "module": "job_analyzer"}
```

### 3d — Full Analyze Endpoint

```python
@router.post("/job")
def analyze_job(
    request: JDAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate input ───────────────────────────────────────────
    if not request.jd_text or len(request.jd_text.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job description is too short. Provide the full JD text (min 50 chars)."
        )

    # ── 2. Run JD analysis pipeline ─────────────────────────────────
    try:
        analysis = analyze_jd(request.jd_text)
    except Exception as e:
        logger.error(f"JD analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

    # ── 3. Auto-generate job name ────────────────────────────────────
    company   = analysis.get("company_name") or "Unknown Company"
    title     = analysis.get("job_title") or "Unknown Role"
    date_str  = datetime.utcnow().strftime("%b %Y")
    auto_name = f"{company} — {title} ({date_str})"

    # ── 4. Save to DB ────────────────────────────────────────────────
    # Read existing Job model fields carefully — serialize JSON fields to string
    job_record = Job(
        user_id           = current_user.id,
        auto_name         = auto_name,
        jd_raw_text       = analysis["jd_raw_text"],
        company_name      = analysis.get("company_name"),
        job_title         = analysis.get("job_title"),
        location          = analysis.get("location"),
        is_remote         = analysis.get("is_remote", False),
        seniority_level   = analysis.get("seniority_level"),
        required_skills_json   = json.dumps(analysis.get("required_skills", [])),
        nicetohave_skills_json = json.dumps(analysis.get("nice_to_have_skills", [])),
        salary_range      = analysis.get("salary_range"),
    )
    db.add(job_record)
    db.commit()
    db.refresh(job_record)
    logger.info(f"Saved job_id={job_record.id} for user_id={current_user.id}")

    # ── 5. Return response ───────────────────────────────────────────
    return {
        "job_id":              job_record.id,
        "auto_name":           auto_name,
        "company_name":        job_record.company_name,
        "job_title":           job_record.job_title,
        "location":            job_record.location,
        "is_remote":           job_record.is_remote,
        "seniority_level":     job_record.seniority_level,
        "salary_range":        job_record.salary_range,
        "required_skills":     analysis.get("required_skills", []),
        "nice_to_have_skills": analysis.get("nice_to_have_skills", []),
        "required_count":      len(analysis.get("required_skills", [])),
        "nicetohave_count":    len(analysis.get("nice_to_have_skills", [])),
    }
```

> **Important:** Before writing, re-read `backend/models/job.py` and check exact column names.
> `required_skills_json` and `nicetohave_skills_json` are `Text` columns — always `json.dumps()` before saving, never pass a list directly.

---

## Step 4 — Update Pydantic Schemas (If Needed)

**File:** `backend/schemas/job.py` — add if not present, never delete existing schemas.

```python
from pydantic import BaseModel
from typing import List, Optional

class JobAnalyzeOut(BaseModel):
    job_id:              int
    auto_name:           str
    company_name:        Optional[str]
    job_title:           Optional[str]
    location:            Optional[str]
    is_remote:           bool
    seniority_level:     Optional[str]
    salary_range:        Optional[str]
    required_skills:     List[str]
    nice_to_have_skills: List[str]
    required_count:      int
    nicetohave_count:    int

    class Config:
        from_attributes = True
```

---

## Step 5 — Verify Day 1 + Day 2 Still Intact

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# All existing routes still respond
for route in /api/parse/status /api/analyze/status /api/tailor/status /api/score/status /api/export/status; do
  echo -n "$route: "
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$route
  echo
done
# Expected: all 200
```

---

## Step 6 — Verification Checklist (All 10 Must Pass)

> **Before checks:** Get a token and have a real job description ready.
> Use any real JD — copy from LinkedIn, Indeed, or use the sample below.

**Sample JD for testing:**
```
Senior Cloud Engineer — Acme Tech, New York, NY (Hybrid)

We are looking for a Senior Cloud Engineer to join our growing infrastructure team.

Requirements:
- 4+ years of experience with AWS (EC2, ECS, RDS, Lambda, S3, CloudWatch)
- Strong proficiency in Python and Bash scripting
- Experience with Docker and Kubernetes
- CI/CD pipeline experience with GitHub Actions or Jenkins
- Infrastructure as Code using Terraform or CloudFormation
- Strong understanding of networking (VPC, subnets, security groups)

Nice to have:
- Experience with Prometheus and Grafana monitoring
- Knowledge of Redis or ElasticSearch
- AWS certifications

Compensation: $130,000 - $160,000 per year
This is a hybrid position with 3 days in office per week.
```

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

### Check 1 — modules/analyze/ directory and files exist

```bash
ls backend/modules/analyze/
# Expected: __init__.py  jd_analyzer.py
```

---

### Check 2 — No auth → 401

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/analyze/job \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "test"}'
# Expected: 401
```

---

### Check 3 — Short JD → 422

```bash
curl -s -X POST http://localhost:8000/api/analyze/job \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "short"}' | python3 -m json.tool
# Expected: 422 with detail about minimum length
```

---

### Check 4 — Valid JD → 200 with structured output

```bash
curl -s -X POST http://localhost:8000/api/analyze/job \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jd_text": "Senior Cloud Engineer — Acme Tech, New York, NY (Hybrid)\n\nRequirements:\n- 4+ years AWS experience (EC2, ECS, RDS, Lambda, S3)\n- Python and Bash scripting\n- Docker and Kubernetes\n- CI/CD with GitHub Actions\n- Terraform or CloudFormation\n\nNice to have:\n- Prometheus and Grafana\n- Redis or ElasticSearch\n\nCompensation: $130,000 - $160,000 per year. Hybrid position."}' \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'job_id:          {data[\"job_id\"]}')
print(f'company:         {data[\"company_name\"]}')
print(f'title:           {data[\"job_title\"]}')
print(f'location:        {data[\"location\"]}')
print(f'remote:          {data[\"is_remote\"]}')
print(f'seniority:       {data[\"seniority_level\"]}')
print(f'salary:          {data[\"salary_range\"]}')
print(f'required skills: {data[\"required_count\"]} — {data[\"required_skills\"]}')
print(f'nice-to-have:    {data[\"nicetohave_count\"]} — {data[\"nice_to_have_skills\"]}')
"
```

**Expected:**
- `job_id`: integer
- `company_name`: `"Acme Tech"` (or similar)
- `job_title`: `"Senior Cloud Engineer"` (or similar)
- `seniority_level`: `"senior"`
- `is_remote`: `false` (hybrid, not fully remote)
- `salary_range`: `"$130,000 - $160,000"`
- `required_skills`: list with AWS, Python, Docker, Kubernetes, Terraform, etc.
- `nice_to_have_skills`: list with Prometheus, Grafana, Redis, etc.

---

### Check 5 — jobs table has new row in DB

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/resumeforge.db')
rows = conn.execute('SELECT id, auto_name, company_name, job_title, seniority_level, is_remote FROM jobs').fetchall()
for r in rows:
    print(r)
conn.close()
"
# Expected: at least 1 row with correct company and title
```

---

### Check 6 — required_skills_json stored correctly in DB

```bash
python3 -c "
import sqlite3, json
conn = sqlite3.connect('data/resumeforge.db')
row = conn.execute('SELECT required_skills_json, nicetohave_skills_json FROM jobs ORDER BY id DESC LIMIT 1').fetchone()
required = json.loads(row[0])
nicetohave = json.loads(row[1])
print(f'Required ({len(required)}): {required}')
print(f'Nice-to-have ({len(nicetohave)}): {nicetohave}')
conn.close()
"
# Expected: valid JSON lists with skill strings
```

---

### Check 7 — Ollama was used for extraction (check server logs)

```bash
tail -20 /tmp/resumeforge.log | grep -i "llm\|ollama\|extracted"
# Expected: log lines showing "LLM extracted: company=Acme Tech, title=Senior Cloud Engineer..."
```

---

### Check 8 — GET /api/analyze/status still returns 200

```bash
curl http://localhost:8000/api/analyze/status
# Expected: {"status": "not implemented yet", "module": "job_analyzer"}
```

---

### Check 9 — Pre-Task A confirmed: no truncation in parse response

```bash
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for s in data['sections']:
    print(f'[{s[\"section_type\"]}] chars={len(s[\"content_text\"])}')
"
# Expected: all sections have chars > 200 (especially education, experience, projects)
```

---

### Check 10 — Pre-Task B confirmed: no hyphenation artifact in skills

```bash
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
for s in data['sections']:
    if s['section_type'] == 'skills':
        has_hyphen = 'orma-' in s['content_text'] or 'Forma-' in s['content_text']
        print('Hyphenation artifact present:', has_hyphen)
        print('Skills preview:', s['content_text'][:150])
"
# Expected: Hyphenation artifact present: False
#           Skills preview shows clean CloudFormation (no hyphen)
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: modules.analyze` | Check `__init__.py` exists in `backend/modules/analyze/` |
| `AttributeError` on Job model fields | Re-read `models/job.py` — use exact column names from the model |
| `json.dumps` error on skills | Confirm `required_skills_json` is a `Text` column — always serialize before saving |
| Ollama returns wrong JSON | Check prompt — the LLM sometimes wraps in backticks. The fence stripper in `extract_llm()` handles this |
| `company_name` is None | Ollama may not have found it in the JD. Check the JD text has a clear company name |
| `seniority_level` is None | Regex didn't find a pattern. Check JD has words like "Senior", "Junior", "Lead" |
| Check 7 shows no Ollama log | Ollama IS running but logs may go to stderr. Check `/tmp/resumeforge.error.log` |

---

## Out of Scope for Day 3

| ❌ Out of Scope | ✅ Planned For |
|----------------|---------------|
| Comparing JD skills against resume skills | Day 5 — ATS Scorer |
| Tailoring resume to match JD | Day 4 — Resume Tailor |
| GET endpoint to list all saved jobs | Day 7 — Frontend |
| PDF export | Day 6 — PDF Exporter |

---

> ✅ **Day 3 complete when all 10 checks pass.**
> Pre-tasks A and B must also pass (checks 9 and 10) before marking complete.
