# ResumeForge — Day 2 Build Guide
## Resume Parser Module
**PDF + DOCX Extraction · Regex Section Detection · Ollama LLM Fallback**

---

> **Agent Instructions:** Work through Steps 0 → 8 sequentially. Do not skip steps.
> Read all listed files before writing any code. Report output for all 10 verification checks.
> Day 2 is complete only when all 10 checks PASS.

---

## ⚠️ Prerequisites — Read Before Writing Any Code

| Fact | Detail |
|------|--------|
| Server status | Backend is **already running** on port 8000 from Day 1. Do **NOT** restart uvicorn unless something is broken. It uses `--reload` so file saves auto-reload. |
| Ollama status | Ollama is **NOT running**. The LLM fallback must gracefully skip — log a warning and keep the regex result. Never raise an exception from the fallback. |
| Auth | JWT auth already works. Reuse `get_current_user` from `routers/auth.py`. Do not rewrite it. |
| DB | `resumeforge.db` already exists with all 6 tables from Day 1. Do not drop or recreate tables. |

---

## Step 0 — Read the Existing Codebase First

Before writing a single line of code, read these files in full:

| File | Why You Need It |
|------|----------------|
| `backend/models/resume.py` | Resume DB model — exact field names you must use |
| `backend/models/resume_section.py` | ResumeSection model — one row per detected section |
| `backend/schemas/resume.py` | Pydantic schemas — match the API response shape |
| `backend/routers/parse.py` | Current stub — you will replace the upload route |
| `backend/routers/auth.py` | Copy `get_current_user` dependency from here |
| `backend/database.py` | Import `get_db` session from here |
| `backend/config.py` | Settings/paths — check for any upload path config |
| `backend/main.py` | Verify the parse router is registered correctly |

---

## Step 1 — Install Dependencies

Run inside the activated venv. Add both to `requirements.txt` if not already there.

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate

# Install
pip install pdfplumber python-docx

# Verify
pip list | grep -E "pdfplumber|python-docx"
# Expected:
# pdfplumber    x.x.x
# python-docx   x.x.x

# Add to requirements.txt if missing
grep -q "pdfplumber" requirements.txt || echo "pdfplumber" >> requirements.txt
grep -q "python-docx" requirements.txt || echo "python-docx" >> requirements.txt
```

> **Note:** Do NOT deactivate the venv or restart the server after installing. The running uvicorn process will auto-reload when you save `.py` files.

---

## Step 2 — Create Upload Directory & Module Init

```bash
# File storage directory (files saved at runtime as: data/uploads/{user_id}/{uuid4}.{ext})
mkdir -p /Users/nikunjshetye/Documents/resume-forger/backend/data/uploads

# Ensure parse module is a proper Python package
touch /Users/nikunjshetye/Documents/resume-forger/backend/modules/parse/__init__.py
```

After this step, the structure should look like:

```
backend/
  data/
    resumeforge.db          ← already exists from Day 1
    uploads/                ← NEW: file storage root
  modules/
    parse/
      __init__.py           ← NEW: package marker
      extractor.py          ← NEW: Step 3
      section_detector.py   ← NEW: Step 4
  routers/
    parse.py                ← MODIFY: Step 5
```

---

## Step 3 — Build the Text Extractor

**Create:** `backend/modules/parse/extractor.py`

This module extracts raw text and page count from uploaded files. Returns consistent output for both formats.

### 3a — PDF Extraction (pdfplumber)

```python
import pdfplumber

def extract_pdf(file_path: str) -> dict:
    """Extract raw text and page count from a PDF file."""
    pages_text = []
    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
    raw_text = "\n\n".join(pages_text)
    return {"raw_text": raw_text, "page_count": page_count}
```

### 3b — DOCX Extraction (python-docx)

```python
from docx import Document as DocxDocument

def extract_docx(file_path: str) -> dict:
    """Extract raw text from a DOCX file (paragraphs + table cells)."""
    doc = DocxDocument(file_path)
    lines = []

    # Extract paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            lines.append(para.text.strip())

    # Extract table cell text
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    lines.append(cell.text.strip())

    raw_text = "\n".join(lines)
    # DOCX has no reliable page count — default to 1
    return {"raw_text": raw_text, "page_count": 1}
```

### 3c — Unified Entry Point

```python
def extract(file_path: str, file_format: str) -> dict:
    """Route to correct extractor based on file format."""
    if file_format == "pdf":
        return extract_pdf(file_path)
    elif file_format == "docx":
        return extract_docx(file_path)
    else:
        raise ValueError(f"Unsupported format: {file_format}")
```

---

## Step 4 — Build the Section Detector

**Create:** `backend/modules/parse/section_detector.py`

**Strategy:** Regex heuristics first. If confidence < 0.6 for any block, attempt Ollama LLM reclassification. If Ollama is unavailable → log warning, keep regex result, never crash.

### 4a — Keyword Map

```python
SECTION_KEYWORDS = {
    "contact":        ["contact", "personal info", "personal details", "about me", "reach me"],
    "summary":        ["summary", "objective", "profile", "about", "overview", "career objective"],
    "experience":     ["experience", "work experience", "employment", "work history",
                       "professional experience", "career history"],
    "education":      ["education", "academic", "qualification", "degree", "academics"],
    "skills":         ["skills", "technical skills", "core competencies",
                       "technologies", "expertise", "tech stack"],
    "projects":       ["projects", "personal projects", "key projects",
                       "portfolio", "notable projects"],
    "certifications": ["certifications", "certificates", "licenses",
                       "credentials", "achievements", "awards"],
}

SECTION_TYPES = list(SECTION_KEYWORDS.keys())
```

### 4b — Heading Detection

A line is a section heading if:
- It matches a keyword (case-insensitive) → confidence **1.0**
- It is ALL CAPS and fewer than 60 characters → confidence **0.7**, type `"unknown"`
- Otherwise → not a heading

```python
def classify_line(line: str) -> tuple:
    """Returns (section_type, confidence) or (None, 0.0) if not a heading."""
    stripped = line.strip()
    if not stripped or len(stripped) < 2:
        return None, 0.0

    lower = stripped.lower()

    # Keyword match — high confidence
    for section_type, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return section_type, 1.0

    # ALL CAPS heading — medium confidence
    if stripped.isupper() and len(stripped) < 60:
        return "unknown", 0.7

    return None, 0.0
```

### 4c — Block Splitter

If the first block has no heading, label it `"contact"` — most resumes start with name/contact info.

```python
def split_into_blocks(raw_text: str) -> list:
    """Split text into section blocks using heading detection."""
    lines = raw_text.split("\n")
    blocks = []
    current_heading = None
    current_type = "contact"    # default for leading content
    current_confidence = 0.8
    current_lines = []

    for line in lines:
        section_type, confidence = classify_line(line)
        if section_type is not None:
            # Save previous block
            if current_lines:
                blocks.append({
                    "section_type":   current_type,
                    "section_label":  current_heading or current_type.title(),
                    "content_text":   "\n".join(current_lines).strip(),
                    "confidence":     current_confidence,
                    "detected_by":    "regex",
                })
            # Start new block
            current_heading    = line.strip()
            current_type       = section_type
            current_confidence = confidence
            current_lines      = []
        else:
            current_lines.append(line)

    # Flush last block
    if current_lines:
        blocks.append({
            "section_type":   current_type,
            "section_label":  current_heading or current_type.title(),
            "content_text":   "\n".join(current_lines).strip(),
            "confidence":     current_confidence,
            "detected_by":    "regex",
        })

    return [b for b in blocks if b["content_text"]]  # drop empty blocks
```

### 4d — Ollama LLM Fallback

> ⚠️ **Ollama is NOT currently running.** This function MUST fail gracefully. Use a 2-second timeout. Never raise exceptions. Log a warning and return the original regex result if unavailable.

```python
import requests
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"

def ollama_available() -> bool:
    """Check if Ollama is running with a 2s timeout."""
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def llm_classify(content_text: str) -> str:
    """Ask Ollama to classify a resume block. Returns section_type string."""
    prompt = (
        "Classify this resume section into exactly one of these categories:\n"
        "contact, summary, experience, education, skills, projects, certifications, other\n"
        "Reply with only the single category word, nothing else.\n\n"
        f"Text:\n{content_text[:500]}"
    )
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": DEFAULT_MODEL, "prompt": prompt, "stream": False},
            timeout=30
        )
        result = r.json().get("response", "").strip().lower()
        if result in SECTION_TYPES + ["other"]:
            return result
        return "other"
    except Exception as e:
        logger.warning(f"Ollama classify error: {e}")
        return "other"
```

### 4e — Main Entry Point

```python
def detect_sections(raw_text: str) -> list:
    """
    Full pipeline: regex detection + optional LLM fallback.
    Returns list of section dicts ready for DB insertion.
    """
    blocks = split_into_blocks(raw_text)

    # Identify low-confidence blocks
    low_conf = [b for b in blocks if b["confidence"] < 0.6]

    if low_conf:
        if ollama_available():
            logger.info(f"Ollama available — running LLM fallback on {len(low_conf)} block(s)")
            for block in low_conf:
                new_type = llm_classify(block["content_text"])
                block["section_type"] = new_type
                block["detected_by"]  = "llm"
        else:
            logger.warning(
                f"Ollama unavailable — skipping LLM fallback for {len(low_conf)} low-confidence block(s)"
            )

    # Add position index
    for i, block in enumerate(blocks):
        block["position_index"] = i

    return blocks
```

---

## Step 5 — Build the Upload Endpoint

**Modify:** `backend/routers/parse.py` — replace the stub upload route with the full implementation. **Keep `GET /api/parse/status` intact.**

### 5a — Imports & Router Setup

```python
import os
import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.resume import Resume
from models.resume_section import ResumeSection
from models.user import User
from routers.auth import get_current_user
from modules.parse.extractor import extract
from modules.parse.section_detector import detect_sections

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/parse", tags=["Resume Parser"])

UPLOAD_BASE = Path(__file__).parent.parent / "data" / "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
```

### 5b — Keep Existing Status Stub

```python
# Keep exactly as Day 1 left it
@router.get("/status")
def parse_status():
    return {"status": "not implemented yet", "module": "resume_parser"}
```

### 5c — Full Upload Endpoint

```python
@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate file extension ──────────────────────────
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Only PDF and DOCX allowed."
        )

    # ── 2. Read content & validate size ─────────────────────
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 5MB."
        )

    # ── 3. Save file to disk ────────────────────────────────
    user_dir = UPLOAD_BASE / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    saved_filename = f"{uuid.uuid4()}{ext}"
    file_path = user_dir / saved_filename
    file_path.write_bytes(content)
    logger.info(f"Saved upload: {file_path}")

    # ── 4. Extract text ─────────────────────────────────────
    file_format = ext.lstrip(".")
    extraction  = extract(str(file_path), file_format)
    raw_text    = extraction["raw_text"]
    page_count  = extraction["page_count"]

    # ── 5. Detect sections ──────────────────────────────────
    sections = detect_sections(raw_text)

    # ── 6. Save Resume to DB ────────────────────────────────
    name = Path(file.filename).stem
    resume_record = Resume(
        user_id           = current_user.id,
        name              = name,
        original_filename = file.filename,
        file_format       = file_format,
        file_path         = str(file_path),
        raw_text          = raw_text,
        structured_json   = {
            "section_count": len(sections),
            "sections": [s["section_type"] for s in sections],
        },
        char_count  = len(raw_text),
        page_count  = page_count,
    )
    db.add(resume_record)
    db.flush()  # get resume_record.id before commit

    # ── 7. Save Sections to DB ──────────────────────────────
    for sec in sections:
        db.add(ResumeSection(
            resume_id       = resume_record.id,
            section_type    = sec["section_type"],
            section_label   = sec["section_label"],
            content_text    = sec["content_text"],
            position_index  = sec["position_index"],
            formatting_json = {"detected_by": sec["detected_by"]},
            is_edited       = False,
        ))

    db.commit()
    db.refresh(resume_record)

    # ── 8. Return response ──────────────────────────────────
    return {
        "resume_id":    resume_record.id,
        "name":         resume_record.name,
        "file_format":  resume_record.file_format,
        "char_count":   resume_record.char_count,
        "page_count":   resume_record.page_count,
        "section_count": len(sections),
        "sections": [
            {
                "section_type":   s["section_type"],
                "section_label":  s["section_label"],
                "content_text":   s["content_text"][:200],  # preview only
                "position_index": s["position_index"],
                "detected_by":    s["detected_by"],
            }
            for s in sections
        ]
    }
```

---

## Step 6 — Update Pydantic Schemas (If Needed)

Check `backend/schemas/resume.py`. If there is no response schema matching the upload output, add the following. If compatible schemas already exist, skip this step. **Never delete existing schemas.**

```python
# backend/schemas/resume.py — add if not present
from pydantic import BaseModel
from typing import List

class SectionOut(BaseModel):
    section_type:   str
    section_label:  str
    content_text:   str
    position_index: int
    detected_by:    str

class ResumeUploadOut(BaseModel):
    resume_id:     int
    name:          str
    file_format:   str
    char_count:    int
    page_count:    int
    section_count: int
    sections:      List[SectionOut]

    class Config:
        from_attributes = True
```

> **Note:** The endpoint returns a plain `dict`, so FastAPI serializes it directly without needing the schema at runtime. The schema above is for documentation and future typing only.

---

## Step 7 — Verify Day 1 is Still Intact

Before running the Day 2 checks, confirm nothing from Day 1 broke:

```bash
# Health check — must still return healthy
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Auth login — must still return a JWT token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123"
# Expected: {"access_token": "eyJ...", "token_type": "bearer"}

# DB row counts — Day 1 data must still be there
cd /Users/nikunjshetye/Documents/resume-forger/backend
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
for t in ['users','resumes','resume_sections','jobs','tailoring_sessions','ai_provider_config']:
    r = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t}: {r} rows')
conn.close()
"
# Expected: users>=1, resumes=0, resume_sections=0, ai_provider_config=4
```

---

## Step 8 — Verification Checklist

> **Before Check #7:** Get a JWT token and have your resume PDF path ready.
>
> ```bash
> TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
>   -H "Content-Type: application/x-www-form-urlencoded" \
>   -d "username=nikunj@resumeforge.com&password=securepass123" \
>   | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
> echo $TOKEN
> ```
>
> Replace `/path/to/resume.pdf` in Check #7 with the actual path to your resume PDF.

Run every check below. Report the exact output for each. Fix failures before moving on.

---

### Check 1 — pdfplumber + python-docx installed
```bash
pip list | grep -E "pdfplumber|python-docx"
```
**Expected:** Both packages listed with version numbers.

---

### Check 2 — uploads/ directory exists
```bash
ls /Users/nikunjshetye/Documents/resume-forger/backend/data/uploads/
```
**Expected:** Directory exists (may be empty).

---

### Check 3 — extractor.py exists with correct functions
```bash
grep -n "def extract" /Users/nikunjshetye/Documents/resume-forger/backend/modules/parse/extractor.py
```
**Expected:** Lines showing `extract_pdf`, `extract_docx`, and `extract`.

---

### Check 4 — section_detector.py exists with main function
```bash
grep -n "def " /Users/nikunjshetye/Documents/resume-forger/backend/modules/parse/section_detector.py
```
**Expected:** Lines showing `classify_line`, `split_into_blocks`, `ollama_available`, `llm_classify`, `detect_sections`.

---

### Check 5 — No auth token → 401
```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/parse/upload
```
**Expected:** `401`

---

### Check 6 — Wrong file type → 422
```bash
echo "this is a test" > /tmp/test.txt
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test.txt"
```
**Expected:** `{"detail": "Unsupported file type..."}` with 422 status.

---

### Check 7 — Valid PDF + token → 200 with sections
```bash
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/resume.pdf"
```
**Expected:** JSON response with `resume_id`, `char_count > 0`, and a `sections` array with at least 2 items.

---

### Check 8 — resumes table has new row
```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
rows = conn.execute('SELECT id, name, char_count, page_count, file_format FROM resumes').fetchall()
for r in rows: print(r)
conn.close()
"
```
**Expected:** At least 1 row with `char_count > 0` and `file_format = 'pdf'`.

---

### Check 9 — resume_sections has multiple rows
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
rows = conn.execute('SELECT id, resume_id, section_type, detected_by FROM resume_sections').fetchall()
for r in rows: print(r)
conn.close()
"
```
**Expected:** Multiple rows, all with `resume_id` matching the resume from Check 8. At least one with `section_type` of `skills`, `experience`, or `education`.

---

### Check 10 — GET /api/parse/status still works
```bash
curl http://localhost:8000/api/parse/status
```
**Expected:** `{"status": "not implemented yet", "module": "resume_parser"}` with 200 status.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: pdfplumber` | Run `pip install pdfplumber` inside the venv. Check with `pip list` |
| `ModuleNotFoundError: docx` | Run `pip install python-docx` — NOT `docx`, that is a different package |
| `ImportError` in `routers/parse.py` | Check all import paths are relative to `backend/`. Verify `__init__.py` exists in `modules/parse/` |
| 422 on valid PDF upload | Check if extension comparison uses `.lower()` — `.PDF` vs `.pdf` matters |
| DB error: column not found | Re-read `models/resume.py`. Use the exact field names defined in the model |
| `sections` list is empty | Print `raw_text` to logs after extraction. If empty, the PDF may be image-based (scanned). Try a text-based PDF |
| Server not reloading after file save | Check uvicorn was started with `--reload`. If not, manually restart: `uvicorn main:app --reload --port 8000` |
| Ollama warning in logs | Expected — Ollama is not running. The warning is intentional. Only a problem if it raises an exception |

---

## Out of Scope for Day 2

Do NOT build these today even if they seem related:

| ❌ Out of Scope | ✅ Planned For |
|----------------|---------------|
| Job description analysis | Day 3 — Job Analyzer |
| AI resume tailoring | Day 4 — Resume Tailor |
| ATS keyword scoring | Day 5 — ATS Scorer |
| PDF export | Day 6 — PDF Exporter |
| React frontend upload UI | Day 7 — Frontend |
| GET endpoint to list all resumes | Day 7 / future |
| Resume section editing | Day 7 / future |

---

> ✅ **Day 2 is complete when all 10 verification checks PASS and are reported.**
