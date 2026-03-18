# ResumeForge — Day 6 Build Guide
## PDF Exporter Module

---

> **Agent Instructions:** Work through Pre-Tasks → Steps 1 → 6 sequentially. Do not skip.
> Read all listed files before writing any code.
> Day 6 is complete only when all 10 verification checks pass.
> After completion: commit to feature/day6-pdf-exporter, merge to dev, merge dev to main.

---

## User Preferences (confirmed before writing this guide)

| Preference | Choice |
|-----------|--------|
| PDF source | Both — session_id (tailored) OR resume_id (original) |
| PDF style | Professional — header bar, section dividers, clean typography |
| Endpoint | `POST /api/export/pdf` with session_id OR resume_id |
| Sections | Contact header, all tailored sections, improvement notes summary |

---

## Current System State

| Service | Status |
|---------|--------|
| Backend | Port 8000, auto-reloads on file save |
| Ollama | Port 11434, model: `qwen3:14b` |
| NVIDIA NIM | Configured in backend/.env as NVIDIA_API_KEY |
| Git | On `dev` branch, clean |

---

## Before Writing Any Code — Read These Files

| File | Why |
|------|-----|
| `backend/models/tailoring_session.py` | Has `pdf_path` column — set this after export |
| `backend/models/resume.py` | `name`, `char_count` fields |
| `backend/models/resume_section.py` | `section_type`, `section_label`, `content_text` |
| `backend/models/job.py` | `company_name`, `job_title` for PDF metadata |
| `backend/routers/export.py` | Current stub — replace it |
| `backend/routers/tailor.py` | Reference for DB access pattern |
| `backend/modules/parse/section_detector.py` | SECTION_KEYWORDS — needed for Pre-Task A |
| `backend/config.py` | Check UPLOAD_DIR or similar path settings |

---

## Pre-Task A — Fix Skills Bleeding (Technologies: lines)

This is the last carry-over from Day 4. Technologies: lines inside projects
are still being split into separate skills sections.

**File:** `backend/modules/parse/section_detector.py`

Find the section splitting logic. The fix is to prevent any line that starts
with `Technologies:`, `Tech Stack:`, `Stack:`, `Tools:`, `Frameworks:`, or
`Languages:` from being treated as a new section heading when we are already
inside a `projects` block.

Specifically, in the function that splits raw text into sections:

1. Track `current_section_type` as you iterate through lines
2. Before creating a new section from a heading candidate, check:

```python
INLINE_CONTENT_PREFIXES = {
    "technologies:", "tech stack:", "stack:",
    "tools:", "frameworks:", "languages:",
    "built with:", "tech:", "techstack:",
}

# If we're in a projects section and the line starts with an inline prefix
# treat it as content, NOT a new section heading
if current_section_type == "projects":
    line_lower = candidate_heading.lower().strip()
    if any(line_lower.startswith(p) for p in INLINE_CONTENT_PREFIXES):
        # append to current block, do NOT create new section
        continue
```

**Verify Pre-Task A:**
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
print(f'section_count: {d[\"section_count\"]} (target: 6)')
print(f'skills_count:  {types.count(\"skills\")} (target: 1)')
print(f'unknown_count: {sum(1 for t in types if t==\"unknown\")} (target: 0)')
print(f'types: {types}')
print('PASS' if d['section_count'] == 6 and types.count('skills') == 1 else 'FAIL')
"
```

**Expected:** section_count=6, skills=1, unknown=0

---

## Pre-Task B — Create feature branch

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git checkout dev
git checkout -b feature/day6-pdf-exporter
```

---

## What Day 6 Builds

### `POST /api/export/pdf`

Accepts either:
- `session_id` — exports the **tailored** resume from a tailoring session
- `resume_id` — exports the **original** parsed resume

Generates a professional PDF with:
- **Header bar** — name, contact info, styled prominently
- **Section dividers** — bold label + horizontal rule between sections
- **Section icons** — small emoji/unicode prefix per section type
- **Improvement notes summary** — only shown when exporting tailored session
- Returns the PDF as a **downloadable file** (binary response)
- Saves the `pdf_path` to `tailoring_sessions` table when session_id provided

---

## Step 1 — Install Dependencies

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
pip install reportlab
pip show reportlab | grep Version
echo "reportlab" >> requirements.txt
```

---

## Step 2 — Build the PDF Exporter Module

**Create:** `backend/modules/export/__init__.py` (empty)

**Create:** `backend/modules/export/pdf_builder.py`

```python
import os
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle
)
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

EXPORT_DIR = Path("data/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Professional color palette
COLOR_HEADER_BG  = colors.HexColor("#1a1a2e")   # dark navy
COLOR_HEADER_FG  = colors.white
COLOR_ACCENT     = colors.HexColor("#4a90d9")    # professional blue
COLOR_DIVIDER    = colors.HexColor("#cccccc")
COLOR_NOTES_BG   = colors.HexColor("#f0f7ff")   # light blue tint
COLOR_BODY       = colors.HexColor("#333333")
COLOR_LABEL      = colors.HexColor("#1a1a2e")

# Section icons (unicode)
SECTION_ICONS = {
    "contact":    "●",
    "education":  "🎓",
    "skills":     "⚙",
    "experience": "💼",
    "projects":   "🚀",
    "leadership": "★",
    "summary":    "▶",
    "unknown":    "●",
}

# ─── STYLES ──────────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "NameStyle",
        parent=base["Normal"],
        fontSize=22,
        textColor=COLOR_HEADER_FG,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    contact_style = ParagraphStyle(
        "ContactStyle",
        parent=base["Normal"],
        fontSize=9,
        textColor=COLOR_HEADER_FG,
        fontName="Helvetica",
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    section_label_style = ParagraphStyle(
        "SectionLabel",
        parent=base["Normal"],
        fontSize=11,
        textColor=COLOR_LABEL,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=base["Normal"],
        fontSize=9.5,
        textColor=COLOR_BODY,
        fontName="Helvetica",
        spaceBefore=1,
        spaceAfter=1,
        leading=13,
    )
    bullet_style = ParagraphStyle(
        "BulletStyle",
        parent=base["Normal"],
        fontSize=9.5,
        textColor=COLOR_BODY,
        fontName="Helvetica",
        leftIndent=12,
        spaceBefore=1,
        spaceAfter=1,
        leading=13,
    )
    notes_header_style = ParagraphStyle(
        "NotesHeader",
        parent=base["Normal"],
        fontSize=10,
        textColor=COLOR_ACCENT,
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=3,
    )
    notes_item_style = ParagraphStyle(
        "NotesItem",
        parent=base["Normal"],
        fontSize=9,
        textColor=COLOR_BODY,
        fontName="Helvetica-Oblique",
        leftIndent=10,
        spaceBefore=1,
        spaceAfter=1,
    )

    return {
        "name": name_style,
        "contact": contact_style,
        "section_label": section_label_style,
        "body": body_style,
        "bullet": bullet_style,
        "notes_header": notes_header_style,
        "notes_item": notes_item_style,
    }


# ─── CONTACT PARSER ──────────────────────────────────────────────────────────

def parse_contact(content_text: str) -> dict:
    """Parse contact section into name and details."""
    lines = [l.strip() for l in content_text.strip().split("\n") if l.strip()]
    name = lines[0] if lines else "Resume"
    details = " · ".join(lines[1:]) if len(lines) > 1 else ""
    return {"name": name, "details": details}


# ─── HEADER BUILDER ──────────────────────────────────────────────────────────

def build_header(story: list, styles: dict, contact: dict, job_title: str = "", company_name: str = ""):
    """Build the professional header bar with name and contact info."""
    # Header background using a Table with colored background
    header_data = [
        [Paragraph(contact["name"], styles["name"])],
    ]
    if contact["details"]:
        header_data.append([Paragraph(contact["details"], styles["contact"])])
    if job_title and company_name:
        target_text = f"Tailored for: {job_title} at {company_name}"
        header_data.append([Paragraph(target_text, styles["contact"])])

    header_table = Table(header_data, colWidths=[7.5 * inch])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), COLOR_HEADER_BG),
        ("TOPPADDING",  (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
        ("LEFTPADDING",  (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))


# ─── SECTION BUILDER ─────────────────────────────────────────────────────────

def build_section(story: list, styles: dict, section_type: str, section_label: str, content_text: str):
    """Build a single resume section with divider and icon."""
    icon = SECTION_ICONS.get(section_type, "●")
    label_text = f"{icon}  {section_label.upper()}"

    story.append(Paragraph(label_text, styles["section_label"]))
    story.append(HRFlowable(
        width="100%", thickness=0.8,
        color=COLOR_ACCENT, spaceAfter=4
    ))

    # Parse content into lines
    lines = content_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 3))
            continue

        # Escape XML special chars for ReportLab
        line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if line.startswith("•") or line.startswith("-") or line.startswith("●"):
            story.append(Paragraph(f"  {line}", styles["bullet"]))
        else:
            story.append(Paragraph(line, styles["body"]))

    story.append(Spacer(1, 6))


# ─── NOTES SUMMARY BUILDER ───────────────────────────────────────────────────

def build_notes_summary(story: list, styles: dict, improvement_notes: list):
    """Build the improvement notes summary section at the bottom."""
    if not improvement_notes:
        return

    # Deduplicate notes
    seen = set()
    unique_notes = []
    for note in improvement_notes:
        if note.lower() not in seen:
            seen.add(note.lower())
            unique_notes.append(note)

    story.append(HRFlowable(width="100%", thickness=1.2, color=COLOR_ACCENT, spaceBefore=10, spaceAfter=6))
    story.append(Paragraph("✨  AI IMPROVEMENT SUMMARY", styles["notes_header"]))

    for note in unique_notes[:8]:  # cap at 8 unique notes
        note_escaped = note.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(f"  • {note_escaped}", styles["notes_item"]))

    story.append(Spacer(1, 8))


# ─── MAIN PDF BUILDER ────────────────────────────────────────────────────────

def build_pdf(
    sections: list,
    output_filename: str,
    job_title: str = "",
    company_name: str = "",
    improvement_notes: list = None,
    is_tailored: bool = False,
) -> str:
    """
    Build a professional PDF resume.

    Args:
        sections: list of dicts with section_type, section_label, content_text, position_index
        output_filename: filename (not full path) e.g. "resume_session_5.pdf"
        job_title: job title for header subtitle
        company_name: company name for header subtitle
        improvement_notes: list of improvement note strings (shown only for tailored)
        is_tailored: whether this is a tailored session export

    Returns:
        str: full path to the generated PDF
    """
    output_path = EXPORT_DIR / output_filename
    styles = build_styles()
    story = []

    # Sort sections by position_index
    sorted_sections = sorted(sections, key=lambda s: s.get("position_index", 0))

    # Extract contact section
    contact_section = next(
        (s for s in sorted_sections if s.get("section_type") == "contact"),
        None
    )
    contact = parse_contact(contact_section.get("content_text", "")) if contact_section else {"name": "Resume", "details": ""}

    # Build document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.6 * inch,
    )

    # 1 — Header
    build_header(story, styles, contact, job_title if is_tailored else "", company_name if is_tailored else "")

    # 2 — Sections (skip contact, already in header)
    SKIP_TYPES = {"contact"}
    for section in sorted_sections:
        sec_type = section.get("section_type", "other")
        if sec_type in SKIP_TYPES:
            continue
        content = section.get("content_text", "").strip()
        if not content:
            continue
        build_section(
            story, styles,
            sec_type,
            section.get("section_label", sec_type.title()),
            content
        )

    # 3 — Improvement notes (tailored only)
    if is_tailored and improvement_notes:
        build_notes_summary(story, styles, improvement_notes)

    # Build PDF
    doc.build(story)
    logger.info(f"PDF built: {output_path} ({output_path.stat().st_size} bytes)")
    return str(output_path)
```

---

## Step 3 — Build the Export Endpoint

**Modify:** `backend/routers/export.py` — replace the stub.

### 3a — Imports

```python
import json
import logging
import os
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models.tailoring_session import TailoringSession
from models.resume import Resume
from models.resume_section import ResumeSection
from models.job import Job
from models.user import User
from routers.auth import get_current_user
from modules.export.pdf_builder import build_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["PDF Exporter"])
```

### 3b — Keep Status Stub

```python
@router.get("/status")
def export_status():
    return {"status": "not implemented yet", "module": "pdf_exporter"}
```

### 3c — Request Schema

```python
class ExportRequest(BaseModel):
    resume_id: Optional[int] = None    # export original resume
    session_id: Optional[int] = None   # export tailored session

    class Config:
        json_schema_extra = {
            "example": {
                "resume_id": None,
                "session_id": 5
            }
        }
```

### 3d — Full Export Endpoint

```python
@router.post("/pdf")
def export_pdf(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate — must provide exactly one of session_id or resume_id ──
    if not request.session_id and not request.resume_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either session_id (tailored export) or resume_id (original export)."
        )

    sections_data = []
    improvement_notes = []
    is_tailored = False
    job_title = ""
    company_name = ""
    resume_name = "resume"

    # ── 2. Load from tailoring session ──────────────────────────────────────
    if request.session_id:
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
                    "section_type":  s.get("section_type"),
                    "section_label": s.get("section_label"),
                    "content_text":  s.get("tailored_text", ""),
                    "position_index": s.get("position_index", 0),
                }
                for s in tailored_data.get("sections", [])
            ]
            improvement_notes = tailored_data.get("improvement_notes", [])
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse tailoring session: {e}"
            )

        is_tailored = True

        # Load job info for header subtitle
        job = db.query(Job).filter(Job.id == session.job_id).first()
        if job:
            job_title = job.job_title or ""
            company_name = job.company_name or ""

        # Load resume name
        resume = db.query(Resume).filter(Resume.id == session.resume_id).first()
        resume_name = resume.name if resume else "resume"
        output_filename = f"tailored_{resume_name}_{request.session_id}.pdf"

    # ── 3. Load from original resume ────────────────────────────────────────
    else:
        resume = db.query(Resume).filter(
            Resume.id == request.resume_id,
            Resume.user_id == current_user.id
        ).first()
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume {request.resume_id} not found."
            )

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
                "section_type":  s.section_type,
                "section_label": s.section_label,
                "content_text":  s.content_text,
                "position_index": s.position_index,
            }
            for s in db_sections
        ]
        resume_name = resume.name
        output_filename = f"original_{resume_name}_{request.resume_id}.pdf"

    # ── 4. Build PDF ─────────────────────────────────────────────────────────
    try:
        pdf_path = build_pdf(
            sections=sections_data,
            output_filename=output_filename,
            job_title=job_title,
            company_name=company_name,
            improvement_notes=improvement_notes,
            is_tailored=is_tailored,
        )
    except Exception as e:
        logger.error(f"PDF build failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(e)}"
        )

    # ── 5. Save pdf_path to tailoring_sessions ───────────────────────────────
    if request.session_id and session:
        session.pdf_path = pdf_path
        db.commit()
        logger.info(f"Saved pdf_path to tailoring_session {session.id}")

    # ── 6. Return PDF as downloadable file ───────────────────────────────────
    if not Path(pdf_path).exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF was not created successfully."
        )

    download_name = f"ResumeForge_{resume_name}.pdf"
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
    )
```

---

## Step 4 — Register Router in main.py (if not already)

**File:** `backend/main.py`

Check if export router is already registered. If not, add:
```python
from routers.export import router as export_router
app.include_router(export_router)
```

---

## Step 5 — Verify Days 1-5 Still Intact

```bash
for route in /health /api/parse/status /api/analyze/status /api/tailor/status /api/score/status /api/export/status; do
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

# Get latest session_id and resume_id for nikunj
SESSION_ID=$(python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
row = conn.execute('SELECT id FROM tailoring_sessions WHERE user_id=3 AND tailored_text != \"\" ORDER BY id DESC LIMIT 1').fetchone()
print(row[0])
conn.close()
")
RESUME_ID=2
echo "Using session_id=$SESSION_ID, resume_id=$RESUME_ID"
```

---

### Check 1 — Module files exist

```bash
ls backend/modules/export/
# Expected: __init__.py  pdf_builder.py
```

---

### Check 2 — No auth → 401

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"session_id": 1}'
# Expected: 401
```

---

### Check 3 — Missing both IDs → 422

```bash
curl -s -X POST http://localhost:8000/api/export/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
# Expected: 422 with detail about providing session_id or resume_id
```

---

### Check 4 — Export original resume → 200 PDF

```bash
curl -s -X POST http://localhost:8000/api/export/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"resume_id\": $RESUME_ID}" \
  -o /tmp/original_resume.pdf

# Verify it's a real PDF
file /tmp/original_resume.pdf
ls -lh /tmp/original_resume.pdf
# Expected: PDF document, > 10KB
```

---

### Check 5 — Export tailored session → 200 PDF

```bash
curl -s -X POST http://localhost:8000/api/export/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": $SESSION_ID}" \
  -o /tmp/tailored_resume.pdf

file /tmp/tailored_resume.pdf
ls -lh /tmp/tailored_resume.pdf
# Expected: PDF document, > 10KB
open /tmp/tailored_resume.pdf
# This should open the PDF in Preview — visually verify it looks professional
```

---

### Check 6 — PDF saved to exports directory

```bash
ls -lh /Users/nikunjshetye/Documents/resume-forger/backend/data/exports/
# Expected: at least 2 PDF files created
```

---

### Check 7 — pdf_path saved to tailoring_sessions table

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
rows = conn.execute('SELECT id, pdf_path FROM tailoring_sessions WHERE pdf_path IS NOT NULL ORDER BY id DESC LIMIT 3').fetchall()
for r in rows:
    print(f'session {r[0]}: {r[1]}')
conn.close()
"
# Expected: at least 1 row with pdf_path set
```

---

### Check 8 — Pre-Task A verified: skills=1, unknown=0

```bash
curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/Users/nikunjshetye/Desktop/nikunj/Resume_10March.pdf" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
types = [s['section_type'] for s in d['sections']]
print(f'section_count: {d[\"section_count\"]} (target: 6)')
print(f'skills_count:  {types.count(\"skills\")} (target: 1)')
print(f'unknown_count: {sum(1 for t in types if t==\"unknown\")} (target: 0)')
print('PASS' if d['section_count'] == 6 and types.count('skills') == 1 else 'FAIL')
"
```

---

### Check 9 — GET /api/export/status still 200

```bash
curl http://localhost:8000/api/export/status
# Expected: {"status": "not implemented yet", "module": "pdf_exporter"}
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
| `ModuleNotFoundError: reportlab` | Run `pip install reportlab` in venv |
| `PDF is 0 bytes` | Check `build_pdf()` for exception — run Check 5 with `-v` flag |
| `422 — no sections` | Re-upload resume first via `POST /api/parse/upload` |
| `404 — session not found` | Check session belongs to user_id=3 in DB |
| `XML syntax error` in PDF | Special chars in resume — check `&`, `<`, `>` escaping in `build_section()` |
| PDF opens blank | Contact section missing — check `parse_contact()` with actual content |

---

## Git — After All 10 Checks Pass

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git add backend/modules/export/
git add backend/routers/export.py
git add backend/modules/parse/section_detector.py
git add backend/requirements.txt
git commit -m "feat: Day 6 — Professional PDF Exporter + skills bleeding final fix

- POST /api/export/pdf — exports original OR tailored resume as PDF
- Professional style: header bar, section dividers, icons
- Sections: contact header, all sections, improvement notes summary
- Saves pdf_path to tailoring_sessions table
- Returns FileResponse for direct download
- Pre-task: final fix for Technologies: lines splitting skills sections"

git push origin feature/day6-pdf-exporter

# Merge to dev
git checkout dev
git merge feature/day6-pdf-exporter
git push origin dev

# Merge dev to main (stable)
git checkout main
git merge dev
git push origin main
git checkout dev
```

---

> ✅ **Day 6 complete when all 10 checks pass and both PDFs open correctly in Preview.**
> The tailored PDF should show the header bar with job title, professional sections, and improvement notes at the bottom.
