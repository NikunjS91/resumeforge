# ResumeForge — Day 7 Build Guide
## LaTeX PDF Engine + Overleaf-Style Frontend

---

> **Agent Instructions:** Work through Pre-Tasks → Parts 1 → 2 → 3 in order.
> Read all listed files before writing any code.
> Day 7 is complete only when all verification checks pass.
> After completion: commit to feature/day7-latex-frontend, merge to dev, merge to main.

---

## What Day 7 Builds

Replace the ReportLab PDF builder entirely with a LaTeX engine.
The user's resume data fills a professional LaTeX template, pdflatex compiles it,
and the frontend shows a live PDF preview — exactly like Overleaf.

### Architecture

```
Resume Data (DB sections + tailoring session)
        ↓
LaTeX Template Filler (Python — escapes all special chars)
        ↓
.tex file written to backend/data/exports/
        ↓
pdflatex compiler (runs on Mac — brew install basictex)
        ↓
PDF bytes returned as FileResponse
        ↓
Frontend renders PDF preview (pdf.js iframe)
```

---

## LaTeX Template Structure (from user's resume)

The template has been analyzed and broken into these fillable sections:

```
HEADER          — name, location, phone, email, linkedin, github
EDUCATION       — university, degree, gpa, date, coursework (repeatable)
SKILLS          — category rows: label → comma-separated skills (repeatable)
EXPERIENCE      — company, role, location, dates, bullets (repeatable)
PROJECTS        — name, github_url, bullets + technologies line (repeatable)
LEADERSHIP      — org, role, date, description (repeatable)
```

---

## Before Writing Any Code — Read These Files

```
backend/modules/export/pdf_builder.py     ← replace entirely
backend/routers/export.py                 ← update to call new builder
backend/models/tailoring_session.py       ← pdf_path column
backend/models/resume_section.py          ← section_type, content_text
backend/config.py                         ← path settings
```

---

## Pre-Task A — Install pdflatex

```bash
# Check if already installed
which pdflatex && pdflatex --version

# If not installed:
brew install basictex

# After install, add to PATH:
export PATH=$PATH:/Library/TeX/texbin

# Verify:
pdflatex --version
# Expected: pdfTeX 3.x.x
```

---

## Pre-Task B — Create Feature Branch

```bash
cd /Users/nikunjshetye/Documents/resume-forger
git checkout dev
git checkout -b feature/day7-latex-frontend
```

---

## Part 1 — LaTeX Template + Python Filler

### Step 1 — Create Template Directory and Template File

**Create directory:**
```bash
mkdir -p /Users/nikunjshetye/Documents/resume-forger/backend/templates
```

**Create:** `backend/templates/professional.tex`

This is the base template with placeholders. Copy exactly:

```latex
% ResumeForge Professional Template
% ATS-Optimized | 1 Page | LaTeX
\documentclass[10pt,letterpaper]{article}
\usepackage[utf8]{inputenc}
\usepackage{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{longtable}
\usepackage{array}

\geometry{letterpaper, top=0.4in, bottom=0.4in, left=0.5in, right=0.5in}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\pagestyle{empty}
\linespread{0.88}

\definecolor{namecolor}{HTML}{1a1a2e}
\definecolor{sectioncolor}{HTML}{16213e}
\definecolor{linkcolor}{HTML}{0066cc}

\hypersetup{
    colorlinks=true,
    linkcolor=linkcolor,
    urlcolor=linkcolor,
    pdfborder={0 0 0},
    pdftitle={LATEX_PDF_TITLE},
    pdfauthor={LATEX_AUTHOR_NAME}
}

\newcommand{\resumesection}[1]{
    \vspace{2pt}
    {\color{sectioncolor}\large\textbf{\uppercase{#1}}}
    \vspace{3pt}
    \hrule height 0.5pt
    \vspace{2pt}
}
\newcommand{\resumesubheading}[4]{
    \textbf{#1} \hfill \textit{#2}\\
    \textit{\small #3} \hfill \textit{\small #4}
    \vspace{0.5pt}
}

\setlist[itemize]{
    leftmargin=0.15in, nosep, itemsep=0pt,
    parsep=0pt, topsep=0pt, partopsep=0pt,
    label=\textbullet
}

\begin{document}

%% HEADER
\begin{center}
    {\Huge\color{namecolor}\textbf{LATEX_FULL_NAME}}\\
    \vspace{1pt}
    LATEX_LOCATION $\cdot$
    \href{tel:LATEX_PHONE_RAW}{LATEX_PHONE_DISPLAY} $\cdot$
    \href{mailto:LATEX_EMAIL}{LATEX_EMAIL}\\
    \vspace{0pt}
    \href{LATEX_LINKEDIN_URL}{LinkedIn} $\cdot$
    \href{LATEX_GITHUB_URL}{GitHub}
\end{center}

%% EDUCATION
\resumesection{Education}
LATEX_EDUCATION_BLOCK

%% SKILLS
\resumesection{Technical Skills}
\begin{tabular}{@{}p{1.45in}p{5.25in}@{}}
LATEX_SKILLS_ROWS
\end{tabular}

%% EXPERIENCE
\resumesection{Professional Experience}
LATEX_EXPERIENCE_BLOCK

%% PROJECTS
\resumesection{Projects}
LATEX_PROJECTS_BLOCK

%% LEADERSHIP
\resumesection{Leadership \& Activities}
LATEX_LEADERSHIP_BLOCK

\end{document}
```

---

### Step 2 — Create the LaTeX Filler Module

**Create:** `backend/modules/export/__init__.py` (if not exists — empty)

**Create:** `backend/modules/export/latex_filler.py`

```python
"""
LaTeX template filler — takes structured resume data and fills the template.
Handles all LaTeX special character escaping.
"""
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path("templates/professional.tex")

# ─── LATEX ESCAPING ──────────────────────────────────────────────────────────

LATEX_ESCAPE_MAP = {
    '&':  r'\&',
    '%':  r'\%',
    '$':  r'\$',
    '#':  r'\#',
    '_':  r'\_',
    '{':  r'\{',
    '}':  r'\}',
    '~':  r'\textasciitilde{}',
    '^':  r'\textasciicircum{}',
    '\\': r'\textbackslash{}',
}

def escape(text: str) -> str:
    """Escape all LaTeX special characters in user content."""
    if not text:
        return ""
    # Process in order to avoid double-escaping
    result = ""
    for char in str(text):
        result += LATEX_ESCAPE_MAP.get(char, char)
    return result


def escape_url(url: str) -> str:
    """URLs don't need standard escaping but need % handled."""
    return url.replace('%', r'\%') if url else ""


# ─── SECTION PARSERS ─────────────────────────────────────────────────────────

def parse_contact(content: str) -> dict:
    """Parse contact section text into structured fields."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    contact = {
        'name': lines[0] if lines else 'Full Name',
        'location': '',
        'phone_raw': '',
        'phone_display': '',
        'email': '',
        'linkedin_url': 'https://linkedin.com',
        'github_url': 'https://github.com',
    }

    full_text = ' '.join(lines)

    # Extract email
    email_match = re.search(r'[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}', full_text)
    if email_match:
        contact['email'] = email_match.group()

    # Extract phone
    phone_match = re.search(r'\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}', full_text)
    if phone_match:
        contact['phone_display'] = phone_match.group()
        contact['phone_raw'] = re.sub(r'[^\d]', '', phone_match.group())

    # Extract LinkedIn
    linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', full_text)
    if linkedin_match:
        contact['linkedin_url'] = 'https://www.' + linkedin_match.group()

    # Extract GitHub
    github_match = re.search(r'github\.com/[\w-]+', full_text)
    if github_match:
        contact['github_url'] = 'https://' + github_match.group()

    # Location — look for "City, ST" pattern
    location_match = re.search(r'([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})', full_text)
    if location_match:
        contact['location'] = location_match.group()

    return contact


def build_education_block(content: str) -> str:
    """Convert education section text to LaTeX."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    blocks = []
    current = []

    for line in lines:
        if any(kw in line.lower() for kw in ['university', 'college', 'institute', 'school']):
            if current:
                blocks.append('\n'.join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append('\n'.join(current))

    latex_blocks = []
    for block in blocks:
        block_lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not block_lines:
            continue
        latex = escape(block_lines[0])  # University name + location
        for bl in block_lines[1:]:
            latex += f'\\\\\n{escape(bl)}'
        latex_blocks.append(latex)

    return '\n\\vspace{2pt}\n'.join(latex_blocks)


def build_skills_rows(content: str) -> str:
    """Convert skills section text to LaTeX tabular rows."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    rows = []

    for line in lines:
        if ':' in line:
            parts = line.split(':', 1)
            label = escape(parts[0].strip())
            skills = escape(parts[1].strip())
            suffix = r'\\[1.5pt]' if line != lines[-1] else r'\\'
            rows.append(f'\\textbf{{{label}}} & {skills} {suffix}')
        elif line:
            rows.append(f'& {escape(line)} \\\\')

    return '\n'.join(rows)


def build_experience_block(content: str) -> str:
    """Convert experience section to LaTeX."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    latex_lines = []
    in_itemize = False

    for line in lines:
        if re.match(r'^[A-Z].*\d{4}', line) and not line.startswith('•'):
            # Looks like a job header
            if in_itemize:
                latex_lines.append('\\end{itemize}')
                in_itemize = False
            # Try to parse: "Role  Company  Location  Dates"
            latex_lines.append(f'\\textbf{{{escape(line)}}}')
        elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
            if not in_itemize:
                latex_lines.append('\\begin{itemize}')
                in_itemize = True
            bullet_text = escape(line.lstrip('•-* ').strip())
            latex_lines.append(f'    \\item {bullet_text}')
        else:
            if in_itemize:
                latex_lines.append('\\end{itemize}')
                in_itemize = False
            latex_lines.append(escape(line) + '\\\\')

    if in_itemize:
        latex_lines.append('\\end{itemize}')

    return '\n'.join(latex_lines)


def build_projects_block(content: str) -> str:
    """Convert projects section to LaTeX."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    latex_lines = []
    in_itemize = False
    first_project = True

    for line in lines:
        is_tech_line = any(line.lower().startswith(p) for p in
                           ['technologies:', 'tech stack:', 'tools:', 'stack:'])
        is_bullet = line.startswith('•') or line.startswith('-') or line.startswith('*')
        is_project_header = (not is_bullet and not is_tech_line
                             and len(line) > 5 and not line[0].isdigit()
                             and not line.startswith('http'))

        if is_project_header and (line.isupper() or 'github' in line.lower()
                                  or any(c.isupper() for c in line[:3])):
            if in_itemize:
                latex_lines.append('\\end{itemize}')
                in_itemize = False
            if not first_project:
                latex_lines.append('\\vspace{2pt}')
            first_project = False
            latex_lines.append(f'\\textbf{{{escape(line)}}}\\\\')
        elif is_tech_line:
            # Bold technologies line inside itemize
            if in_itemize:
                parts = line.split(':', 1)
                tech_text = escape(parts[1].strip()) if len(parts) > 1 else escape(line)
                latex_lines.append(f'    \\item \\textbf{{Technologies:}} {tech_text}')
            else:
                latex_lines.append(escape(line) + '\\\\')
        elif is_bullet:
            if not in_itemize:
                latex_lines.append('\\begin{itemize}')
                in_itemize = True
            bullet_text = escape(line.lstrip('•-* ').strip())
            latex_lines.append(f'    \\item {bullet_text}')
        else:
            if in_itemize:
                latex_lines.append('\\end{itemize}')
                in_itemize = False
            latex_lines.append(escape(line) + '\\\\')

    if in_itemize:
        latex_lines.append('\\end{itemize}')

    return '\n'.join(latex_lines)


def build_leadership_block(content: str) -> str:
    """Convert leadership section to LaTeX."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    # Filter out contact-pattern lines (phone, email, linkedin, github)
    contact_patterns = [
        r'[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}',   # email
        r'\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}',  # phone
        r'linkedin\.com',
        r'github\.com',
    ]
    filtered = []
    for line in lines:
        is_contact = any(re.search(p, line) for p in contact_patterns)
        if not is_contact:
            filtered.append(line)

    latex_lines = []
    first = True
    for line in filtered:
        if not first:
            latex_lines.append('\\vspace{2pt}')
        first = False
        latex_lines.append(f'\\textbf{{{escape(line)}}}\\\\')
    return '\n'.join(latex_lines)


# ─── MAIN FILLER ─────────────────────────────────────────────────────────────

def fill_template(sections: list, job_title: str = "", company_name: str = "") -> str:
    """
    Fill the LaTeX template with resume data.

    Args:
        sections: list of dicts with section_type, section_label, content_text, position_index
        job_title: used in PDF metadata
        company_name: used in PDF metadata

    Returns:
        str: complete .tex file content ready for pdflatex
    """
    template = TEMPLATE_PATH.read_text(encoding='utf-8')

    # Sort by position
    sorted_sections = sorted(sections, key=lambda s: s.get('position_index', 0))

    # Deduplicate — keep first of each type (allow multiple experience/projects)
    ALLOW_MULTIPLE = {'experience', 'projects'}
    seen = set()
    deduped = []
    for s in sorted_sections:
        st = s.get('section_type', 'other')
        if st in ALLOW_MULTIPLE:
            deduped.append(s)
        elif st not in seen:
            seen.add(st)
            deduped.append(s)
    sorted_sections = deduped

    # Extract each section
    def get_content(section_type: str) -> str:
        for s in sorted_sections:
            if s.get('section_type') == section_type:
                return s.get('content_text', '')
        return ''

    contact_content  = get_content('contact')
    education_content = get_content('education')
    skills_content   = get_content('skills')
    experience_content = get_content('experience')
    projects_content = get_content('projects')
    leadership_content = get_content('leadership') or get_content('unknown')

    # Parse contact
    contact = parse_contact(contact_content)
    author_name = contact['name']
    title = f"{author_name} - {job_title}" if job_title else author_name

    # Fill template
    filled = template
    filled = filled.replace('LATEX_PDF_TITLE',       escape(title))
    filled = filled.replace('LATEX_AUTHOR_NAME',     escape(author_name))
    filled = filled.replace('LATEX_FULL_NAME',       escape(contact['name']))
    filled = filled.replace('LATEX_LOCATION',        escape(contact['location']))
    filled = filled.replace('LATEX_PHONE_RAW',       contact['phone_raw'])
    filled = filled.replace('LATEX_PHONE_DISPLAY',   escape(contact['phone_display']))
    filled = filled.replace('LATEX_EMAIL',           contact['email'])
    filled = filled.replace('LATEX_LINKEDIN_URL',    escape_url(contact['linkedin_url']))
    filled = filled.replace('LATEX_GITHUB_URL',      escape_url(contact['github_url']))
    filled = filled.replace('LATEX_EDUCATION_BLOCK', build_education_block(education_content))
    filled = filled.replace('LATEX_SKILLS_ROWS',     build_skills_rows(skills_content))
    filled = filled.replace('LATEX_EXPERIENCE_BLOCK', build_experience_block(experience_content))
    filled = filled.replace('LATEX_PROJECTS_BLOCK',  build_projects_block(projects_content))
    filled = filled.replace('LATEX_LEADERSHIP_BLOCK', build_leadership_block(leadership_content))

    return filled
```

---

### Step 3 — Create the PDF Compiler

**Create:** `backend/modules/export/latex_compiler.py`

```python
"""
Runs pdflatex to compile a .tex file into a PDF.
"""
import subprocess
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("data/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Find pdflatex binary
PDFLATEX_PATHS = [
    '/Library/TeX/texbin/pdflatex',
    '/usr/local/bin/pdflatex',
    '/usr/bin/pdflatex',
]

def find_pdflatex() -> str | None:
    """Find pdflatex binary on the system."""
    for path in PDFLATEX_PATHS:
        if Path(path).exists():
            return path
    # Try which
    result = shutil.which('pdflatex')
    return result


def compile_latex(tex_content: str, output_stem: str) -> str:
    """
    Write .tex file and compile to PDF.

    Args:
        tex_content: complete .tex file content
        output_stem: filename stem e.g. "resume_session_5" (no extension)

    Returns:
        str: full path to compiled PDF

    Raises:
        RuntimeError: if pdflatex not found or compilation fails
    """
    pdflatex = find_pdflatex()
    if not pdflatex:
        raise RuntimeError(
            "pdflatex not found. Install with: brew install basictex\n"
            "Then add to PATH: export PATH=$PATH:/Library/TeX/texbin"
        )

    tex_path = EXPORT_DIR / f"{output_stem}.tex"
    pdf_path = EXPORT_DIR / f"{output_stem}.pdf"

    # Write .tex file
    tex_path.write_text(tex_content, encoding='utf-8')
    logger.info(f"Wrote .tex file: {tex_path}")

    # Compile with pdflatex (run twice for correct page refs)
    for run in range(2):
        result = subprocess.run(
            [pdflatex,
             '-interaction=nonstopmode',
             '-output-directory', str(EXPORT_DIR),
             str(tex_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 and run == 1:
            logger.error(f"pdflatex error:\n{result.stdout[-2000:]}")
            raise RuntimeError(f"pdflatex compilation failed. Check .tex syntax.")

    if not pdf_path.exists():
        raise RuntimeError("PDF was not created after compilation.")

    # Clean up auxiliary files
    for ext in ['.aux', '.log', '.out']:
        aux = EXPORT_DIR / f"{output_stem}{ext}"
        if aux.exists():
            aux.unlink()

    logger.info(f"Compiled PDF: {pdf_path} ({pdf_path.stat().st_size} bytes)")
    return str(pdf_path)
```

---

### Step 4 — Update routers/export.py

**Replace** the existing `export.py` entirely:

```python
import json
import logging
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
from modules.export.latex_filler import fill_template
from modules.export.latex_compiler import compile_latex

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["PDF Exporter"])


@router.get("/status")
def export_status():
    return {"status": "operational", "module": "latex_pdf_exporter"}


class ExportRequest(BaseModel):
    resume_id: Optional[int] = None
    session_id: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {"resume_id": None, "session_id": 5}
        }


@router.post("/pdf")
def export_pdf(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate ──────────────────────────────────────────────────────────
    if not request.session_id and not request.resume_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either session_id (tailored) or resume_id (original)."
        )

    sections_data  = []
    job_title      = ""
    company_name   = ""
    resume_name    = "resume"
    output_stem    = ""
    session        = None

    # ── 2. Load from tailoring session ───────────────────────────────────────
    if request.session_id:
        session = db.query(TailoringSession).filter(
            TailoringSession.id == request.session_id,
            TailoringSession.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(status_code=404,
                detail=f"Tailoring session {request.session_id} not found.")

        try:
            tailored_data = json.loads(session.tailored_json or "{}")
            sections_data = [
                {
                    "section_type":   s.get("section_type"),
                    "section_label":  s.get("section_label", ""),
                    "content_text":   s.get("tailored_text", s.get("content_text", "")),
                    "position_index": s.get("position_index", 0),
                }
                for s in tailored_data.get("sections", [])
                if s.get("tailored_text", s.get("content_text", "")).strip()
            ]
        except Exception as e:
            raise HTTPException(status_code=500,
                detail=f"Failed to parse tailoring session: {e}")

        job = db.query(Job).filter(Job.id == session.job_id).first()
        if job:
            job_title    = job.job_title or ""
            company_name = job.company_name or ""

        resume = db.query(Resume).filter(Resume.id == session.resume_id).first()
        resume_name = resume.name if resume else "resume"
        output_stem = f"tailored_{resume_name}_{request.session_id}"

    # ── 3. Load from original resume ─────────────────────────────────────────
    else:
        resume = db.query(Resume).filter(
            Resume.id == request.resume_id,
            Resume.user_id == current_user.id
        ).first()
        if not resume:
            raise HTTPException(status_code=404,
                detail=f"Resume {request.resume_id} not found.")

        db_sections = db.query(ResumeSection).filter(
            ResumeSection.resume_id == resume.id
        ).order_by(ResumeSection.position_index).all()

        if not db_sections:
            raise HTTPException(status_code=422,
                detail="Resume has no sections. Upload and parse the resume first.")

        sections_data = [
            {
                "section_type":   s.section_type,
                "section_label":  s.section_label,
                "content_text":   s.content_text,
                "position_index": s.position_index,
            }
            for s in db_sections
        ]
        resume_name = resume.name
        output_stem = f"original_{resume_name}_{request.resume_id}"

    # ── 4. Fill LaTeX template ────────────────────────────────────────────────
    try:
        tex_content = fill_template(
            sections=sections_data,
            job_title=job_title,
            company_name=company_name,
        )
    except Exception as e:
        logger.error(f"Template fill error: {e}")
        raise HTTPException(status_code=500,
            detail=f"Failed to fill LaTeX template: {e}")

    # ── 5. Compile to PDF ─────────────────────────────────────────────────────
    try:
        pdf_path = compile_latex(tex_content, output_stem)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"PDF compile error: {e}")
        raise HTTPException(status_code=500,
            detail=f"PDF compilation failed: {e}")

    # ── 6. Save pdf_path to DB ────────────────────────────────────────────────
    if session:
        session.pdf_path = pdf_path
        db.commit()

    # ── 7. Return PDF ─────────────────────────────────────────────────────────
    download_name = f"ResumeForge_{resume_name}.pdf"
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
    )
```

---

## Part 2 — React Frontend with PDF Preview

### Step 5 — Scaffold Frontend

```bash
cd /Users/nikunjshetye/Documents/resume-forger
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install axios react-router-dom
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**tailwind.config.js:**
```js
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

**src/index.css** — add at top:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**vite.config.js:**
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
    }
  }
})
```

---

### Step 6 — Frontend File Structure

```
frontend/src/
  api/
    axios.js          — axios instance with auto auth header
  pages/
    Login.jsx         — login page
    Dashboard.jsx     — main 5-step pipeline
  components/
    ResumeUpload.jsx  — upload + parse resume
    JobInput.jsx      — paste JD + analyze
    TailorPanel.jsx   — tailor with ollama/nvidia selector
    ATSScore.jsx      — score badge with matched/missing keywords
    ExportPanel.jsx   — download buttons + PDF preview
  App.jsx
  main.jsx
```

---

### Step 7 — src/api/axios.js

```jsx
import axios from 'axios'

const api = axios.create({ baseURL: '/' })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default api
```

---

### Step 8 — pages/Login.jsx

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function Login() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    try {
      const res = await axios.post('/auth/login',
        new URLSearchParams({ username: email, password }),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }}
      )
      localStorage.setItem('token', res.data.access_token)
      navigate('/dashboard')
    } catch {
      setError('Invalid credentials')
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 to-blue-100 flex items-center justify-center">
      <div className="bg-white p-8 rounded-2xl shadow-lg w-full max-w-md">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-indigo-700">⚡ ResumeForge</h1>
          <p className="text-gray-500 mt-1">AI-powered resume tailoring — fully local</p>
        </div>
        {error && <p className="text-red-500 text-sm mb-4 text-center bg-red-50 py-2 rounded-lg">{error}</p>}
        <form onSubmit={handleLogin} className="space-y-4">
          <input type="email" placeholder="Email" value={email}
            onChange={e => setEmail(e.target.value)} required
            className="w-full border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
          <input type="password" placeholder="Password" value={password}
            onChange={e => setPassword(e.target.value)} required
            className="w-full border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-400 text-sm" />
          <button type="submit"
            className="w-full bg-indigo-600 text-white py-3 rounded-xl font-semibold hover:bg-indigo-700 transition text-sm">
            Sign In
          </button>
        </form>
      </div>
    </div>
  )
}
```

---

### Step 9 — pages/Dashboard.jsx

```jsx
import { useState } from 'react'
import ResumeUpload from '../components/ResumeUpload'
import JobInput     from '../components/JobInput'
import TailorPanel  from '../components/TailorPanel'
import ATSScore     from '../components/ATSScore'
import ExportPanel  from '../components/ExportPanel'

const STEPS = [
  { num: 1, label: 'Upload Resume' },
  { num: 2, label: 'Analyze JD' },
  { num: 3, label: 'Tailor' },
  { num: 4, label: 'ATS Score' },
  { num: 5, label: 'Export PDF' },
]

export default function Dashboard() {
  const [resumeId,  setResumeId]  = useState(null)
  const [jobId,     setJobId]     = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [atsScore,  setAtsScore]  = useState(null)

  const currentStep = !resumeId ? 1 : !jobId ? 2 : !sessionId ? 3 : atsScore === null ? 4 : 5

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Nav */}
      <nav className="bg-indigo-700 text-white px-8 py-4 flex items-center justify-between shadow-md">
        <h1 className="text-xl font-bold">⚡ ResumeForge</h1>
        <button onClick={() => { localStorage.removeItem('token'); window.location.href = '/' }}
          className="text-sm opacity-75 hover:opacity-100 transition">
          Sign out
        </button>
      </nav>

      <div className="max-w-3xl mx-auto mt-8 px-4 pb-16">
        {/* Progress bar */}
        <div className="flex items-center mb-8">
          {STEPS.map((s, i) => (
            <div key={s.num} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold border-2 transition
                  ${currentStep > s.num
                    ? 'bg-green-500 border-green-500 text-white'
                    : currentStep === s.num
                      ? 'bg-indigo-600 border-indigo-600 text-white'
                      : 'bg-white border-gray-300 text-gray-400'}`}>
                  {currentStep > s.num ? '✓' : s.num}
                </div>
                <span className="text-xs text-gray-500 mt-1 hidden sm:block">{s.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 ${currentStep > s.num ? 'bg-green-400' : 'bg-gray-200'}`} />
              )}
            </div>
          ))}
        </div>

        {/* Steps */}
        <div className="space-y-5">
          <ResumeUpload onUpload={setResumeId} />
          {resumeId  && <JobInput onAnalyze={setJobId} />}
          {jobId     && <TailorPanel resumeId={resumeId} jobId={jobId} onTailored={setSessionId} />}
          {sessionId && <ATSScore resumeId={resumeId} jobId={jobId} sessionId={sessionId} onScored={setAtsScore} />}
          {sessionId && <ExportPanel resumeId={resumeId} sessionId={sessionId} />}
        </div>
      </div>
    </div>
  )
}
```

---

### Step 10 — components/ResumeUpload.jsx

```jsx
import { useState } from 'react'
import api from '../api/axios'

export default function ResumeUpload({ onUpload }) {
  const [file,    setFile]    = useState(null)
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const handleUpload = async () => {
    if (!file) return
    setLoading(true); setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/parse/upload', form)
      setResult(res.data)
      onUpload(res.data.resume_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Upload failed')
    } finally { setLoading(false) }
  }

  return (
    <Card title="📄 Step 1 — Upload Resume">
      {!result ? (
        <div className="space-y-3">
          <label className="block border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-indigo-300 transition">
            <input type="file" accept=".pdf,.docx" className="hidden"
              onChange={e => setFile(e.target.files[0])} />
            {file
              ? <p className="text-indigo-600 font-medium">{file.name}</p>
              : <><p className="text-gray-400 text-sm">Click to upload PDF or DOCX</p><p className="text-gray-300 text-xs mt-1">Max 10MB</p></>
            }
          </label>
          <button onClick={handleUpload} disabled={!file || loading}
            className="w-full bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition">
            {loading ? 'Parsing resume...' : 'Upload & Parse'}
          </button>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <Success title={`${result.resume_name} parsed`}
          subtitle={`${result.section_count} sections · ${result.char_count?.toLocaleString()} chars`}>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {result.sections?.map(s => (
              <span key={s.position_index}
                className="bg-indigo-100 text-indigo-700 text-xs px-2.5 py-0.5 rounded-full">
                {s.section_label}
              </span>
            ))}
          </div>
        </Success>
      )}
    </Card>
  )
}

// Shared sub-components
function Card({ title, children }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      <h2 className="text-base font-semibold text-gray-800 mb-4">{title}</h2>
      {children}
    </div>
  )
}

function Success({ title, subtitle, children }) {
  return (
    <div className="bg-green-50 border border-green-100 rounded-xl p-4">
      <p className="text-green-700 font-medium text-sm">✅ {title}</p>
      {subtitle && <p className="text-gray-500 text-xs mt-0.5">{subtitle}</p>}
      {children}
    </div>
  )
}

export { Card, Success }
```

---

### Step 11 — components/JobInput.jsx

```jsx
import { useState } from 'react'
import api from '../api/axios'
import { Card, Success } from './ResumeUpload'

export default function JobInput({ onAnalyze }) {
  const [text,    setText]    = useState('')
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const handle = async () => {
    if (!text.trim()) return
    setLoading(true); setError('')
    try {
      const res = await api.post('/api/analyze/job', { jd_text: text })
      setResult(res.data)
      onAnalyze(res.data.job_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Analysis failed')
    } finally { setLoading(false) }
  }

  return (
    <Card title="🔍 Step 2 — Analyze Job Description">
      {!result ? (
        <div className="space-y-3">
          <textarea rows={5} value={text} onChange={e => setText(e.target.value)}
            placeholder="Paste the full job description here..."
            className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none" />
          <button onClick={handle} disabled={!text.trim() || loading}
            className="w-full bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition">
            {loading ? 'Analyzing...' : 'Analyze JD'}
          </button>
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <Success title={`${result.job_title} at ${result.company_name}`}
          subtitle={`${result.required_count} required · ${result.nicetohave_count} nice-to-have`}>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {result.required_skills?.slice(0, 12).map(s => (
              <span key={s} className="bg-blue-100 text-blue-700 text-xs px-2.5 py-0.5 rounded-full">{s}</span>
            ))}
          </div>
        </Success>
      )}
    </Card>
  )
}
```

---

### Step 12 — components/TailorPanel.jsx

```jsx
import { useState } from 'react'
import api from '../api/axios'
import { Card, Success } from './ResumeUpload'

const PROVIDERS = {
  ollama: { label: 'Local — Ollama',    model: 'qwen3:14b',               time: '~2-3 min', color: 'green', private: true },
  nvidia: { label: 'NVIDIA NIM',        model: 'llama-3.3-70b-instruct',  time: '~15-20s',  color: 'blue',  private: false },
}

export default function TailorPanel({ resumeId, jobId, onTailored }) {
  const [provider, setProvider] = useState('ollama')
  const [result,   setResult]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  const handle = async () => {
    setLoading(true); setError('')
    try {
      const res = await api.post('/api/tailor/resume', {
        resume_id: resumeId, job_id: jobId, provider
      })
      setResult(res.data)
      onTailored(res.data.session_id)
    } catch (e) {
      setError(e.response?.data?.detail || 'Tailoring failed')
    } finally { setLoading(false) }
  }

  return (
    <Card title="✂️ Step 3 — Tailor Resume">
      {!result ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(PROVIDERS).map(([key, p]) => (
              <button key={key} onClick={() => setProvider(key)}
                className={`border-2 rounded-xl p-3 text-left transition
                  ${provider === key ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}`}>
                <p className="font-medium text-sm text-gray-800">{p.label}</p>
                <p className="text-xs text-gray-400 mt-0.5">{p.model}</p>
                <div className="flex gap-2 mt-1.5">
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">⏱ {p.time}</span>
                  {p.private && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">🔒 private</span>}
                </div>
              </button>
            ))}
          </div>
          {provider === 'ollama' && (
            <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded-lg">
              ⏱ Local mode takes 2-3 minutes. Keep this tab open and wait.
            </p>
          )}
          <button onClick={handle} disabled={loading}
            className="w-full bg-indigo-600 text-white py-2.5 rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition">
            {loading ? `Tailoring with ${PROVIDERS[provider].label}...` : `Tailor with ${PROVIDERS[provider].label}`}
          </button>
          {loading && (
            <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div className="bg-indigo-500 h-1.5 rounded-full animate-pulse" style={{width: '60%'}} />
            </div>
          )}
          {error && <p className="text-red-500 text-sm">{error}</p>}
        </div>
      ) : (
        <Success title={`Tailored with ${result.ai_model}`}
          subtitle={`${result.sections_tailored} sections improved`}>
          <ul className="mt-2 space-y-1">
            {result.improvement_notes?.slice(0, 3).map((n, i) => (
              <li key={i} className="text-xs text-gray-600">• {n}</li>
            ))}
          </ul>
        </Success>
      )}
    </Card>
  )
}
```

---

### Step 13 — components/ATSScore.jsx

```jsx
import { useState, useEffect } from 'react'
import api from '../api/axios'
import { Card } from './ResumeUpload'

export default function ATSScore({ resumeId, jobId, sessionId, onScored }) {
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { score() }, [sessionId])

  const score = async () => {
    setLoading(true)
    try {
      const res = await api.post('/api/score/ats', {
        resume_id: resumeId, job_id: jobId, session_id: sessionId
      })
      setResult(res.data)
      onScored(res.data.ats_score)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const color = (s) => s >= 80 ? '#22c55e' : s >= 60 ? '#f59e0b' : '#ef4444'
  const ring  = (s) => s >= 80 ? 'border-green-400' : s >= 60 ? 'border-yellow-400' : 'border-red-400'

  return (
    <Card title="📊 Step 4 — ATS Score">
      {loading && <p className="text-gray-400 text-sm">Scoring against job requirements...</p>}
      {result && (
        <div className="flex gap-5 items-start">
          <div className={`w-20 h-20 rounded-full border-4 ${ring(result.ats_score)} flex-shrink-0
            flex items-center justify-center`}>
            <span className="text-2xl font-bold" style={{color: color(result.ats_score)}}>
              {result.ats_score}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-600 mb-2">{result.recommendation}</p>
            <div className="space-y-2">
              {result.matched_keywords?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-green-700 mb-1">✅ Matched ({result.matched_count})</p>
                  <div className="flex flex-wrap gap-1">
                    {result.matched_keywords.map(k => (
                      <span key={k} className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                  </div>
                </div>
              )}
              {result.missing_keywords?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-red-700 mb-1">❌ Missing ({result.missing_keywords.length})</p>
                  <div className="flex flex-wrap gap-1">
                    {result.missing_keywords.map(k => (
                      <span key={k} className="bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}
```

---

### Step 14 — components/ExportPanel.jsx

This component has the PDF preview — loads the PDF in an iframe after download.

```jsx
import { useState } from 'react'
import api from '../api/axios'
import { Card } from './ResumeUpload'

export default function ExportPanel({ resumeId, sessionId }) {
  const [loading,    setLoading]    = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewLabel, setPreviewLabel] = useState('')

  const download = async (type) => {
    setLoading(type)
    try {
      const body = type === 'tailored' ? { session_id: sessionId } : { resume_id: resumeId }
      const res  = await api.post('/api/export/pdf', body, { responseType: 'blob' })
      const blob = new Blob([res.data], { type: 'application/pdf' })
      const url  = URL.createObjectURL(blob)

      // Show preview
      setPreviewUrl(url)
      setPreviewLabel(type === 'tailored' ? 'Tailored Resume' : 'Original Resume')

      // Also trigger download
      const a = document.createElement('a')
      a.href = url
      a.download = type === 'tailored' ? 'tailored_resume.pdf' : 'original_resume.pdf'
      a.click()
    } catch (e) {
      console.error(e)
    } finally { setLoading(null) }
  }

  return (
    <Card title="📥 Step 5 — Export PDF">
      <div className="flex gap-3 mb-4">
        <button onClick={() => download('tailored')} disabled={loading === 'tailored'}
          className="flex-1 bg-indigo-600 text-white py-3 rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 transition">
          {loading === 'tailored' ? '⏳ Generating...' : '⬇ Download Tailored Resume'}
        </button>
        <button onClick={() => download('original')} disabled={loading === 'original'}
          className="flex-1 border-2 border-gray-200 text-gray-700 py-3 rounded-xl text-sm font-medium hover:border-indigo-300 disabled:opacity-40 transition">
          {loading === 'original' ? '⏳ Generating...' : '⬇ Download Original'}
        </button>
      </div>

      {/* PDF Preview — Overleaf-style */}
      {previewUrl && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-700">Preview: {previewLabel}</p>
            <a href={previewUrl} target="_blank" rel="noopener noreferrer"
              className="text-xs text-indigo-600 hover:underline">Open in new tab ↗</a>
          </div>
          <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
            <iframe
              src={previewUrl}
              title="Resume PDF Preview"
              className="w-full"
              style={{ height: '800px' }}
            />
          </div>
        </div>
      )}
    </Card>
  )
}
```

---

### Step 15 — App.jsx

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'

const Private = ({ children }) =>
  localStorage.getItem('token') ? children : <Navigate to="/" />

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"          element={<Login />} />
        <Route path="/dashboard" element={<Private><Dashboard /></Private>} />
      </Routes>
    </BrowserRouter>
  )
}
```

---

### Step 16 — Start Everything

```bash
# Terminal 1 — Backend
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd /Users/nikunjshetye/Documents/resume-forger/frontend
npm run dev
# Opens at http://localhost:5173
```

---

## Verification Checks (All 10 Must Pass)

### Backend Checks

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

SESSION_ID=$(cd /Users/nikunjshetye/Documents/resume-forger/backend && python3 -c "
import sqlite3
conn = sqlite3.connect('data/resumeforge.db')
row = conn.execute('SELECT id FROM tailoring_sessions WHERE user_id=3 AND tailored_text != \"\" ORDER BY id DESC LIMIT 1').fetchone()
print(row[0])
conn.close()
")

# Check 1 — pdflatex installed
pdflatex --version && echo "PASS" || echo "FAIL — run: brew install basictex"

# Check 2 — template file exists
ls /Users/nikunjshetye/Documents/resume-forger/backend/templates/professional.tex && echo "PASS" || echo "FAIL"

# Check 3 — export original PDF
curl -s -X POST http://localhost:8000/api/export/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"resume_id": 2}' -o /tmp/original_latex.pdf
file /tmp/original_latex.pdf | grep -i pdf && echo "PASS" || echo "FAIL"
ls -lh /tmp/original_latex.pdf

# Check 4 — export tailored PDF
curl -s -X POST http://localhost:8000/api/export/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": $SESSION_ID}" -o /tmp/tailored_latex.pdf
file /tmp/tailored_latex.pdf | grep -i pdf && echo "PASS" || echo "FAIL"
ls -lh /tmp/tailored_latex.pdf

# Check 5 — open both in Preview (visual check)
open /tmp/original_latex.pdf
open /tmp/tailored_latex.pdf
# Expected: professional 1-page resume — no duplicates, clean layout

# Check 6 — no skills duplication in original
open /tmp/original_latex.pdf
# Expected: skills section appears ONCE only

# Check 7 — leadership has no contact info
open /tmp/tailored_latex.pdf
# Expected: leadership section has only AWS Club + CodeChef entries

# Check 8 — all routes still healthy
for route in /health /api/parse/status /api/analyze/status /api/tailor/status /api/score/status /api/export/status; do
  echo -n "$route: "
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8000$route
  echo
done
# Expected: all 200
```

### Frontend Checks

```bash
# Check 9 — frontend builds clean
cd /Users/nikunjshetye/Documents/resume-forger/frontend
npm run build
# Expected: no errors, dist/ created

# Check 10 — manual end-to-end flow
# Open http://localhost:5173
# Login → Upload resume → Analyze JD → Tailor → ATS Score → Download PDF
# Expected: PDF preview appears in ExportPanel after download
# Expected: PDF looks identical to LaTeX template structure
```

---

## Git — After All 10 Checks Pass

```bash
cd /Users/nikunjshetye/Documents/resume-forger

# Backend changes
git add backend/modules/export/latex_filler.py
git add backend/modules/export/latex_compiler.py
git add backend/routers/export.py
git add backend/templates/professional.tex

# Frontend
git add frontend/

git commit -m "feat: Day 7 — LaTeX PDF engine + React frontend with PDF preview

Backend:
- Replace ReportLab with pdflatex compiler
- professional.tex template matching user's exact LaTeX structure
- latex_filler.py: escapes all special chars, fills template sections
- latex_compiler.py: runs pdflatex, cleans up aux files
- Section deduplication before template fill
- Contact info filtered from leadership section

Frontend:
- React + Vite + TailwindCSS
- 5-step pipeline: Upload → Analyze → Tailor → Score → Export
- Ollama vs NVIDIA NIM provider selector
- ATS score badge with matched/missing keywords
- PDF preview iframe (Overleaf-style) after export"

git push origin feature/day7-latex-frontend

# Merge to dev
git checkout dev
git merge feature/day7-latex-frontend
git push origin dev

# Merge dev to main — FINAL STABLE RELEASE
git checkout main
git merge dev
git push origin main
git checkout dev
```

---

## Final Project — Complete

### Full API Surface

| Route | Method | Day | Description |
|-------|--------|-----|-------------|
| `/auth/signup` | POST | 1 | Create account |
| `/auth/login` | POST | 1 | JWT token |
| `/auth/me` | GET | 1 | Current user |
| `/api/parse/upload` | POST | 2 | Parse resume PDF/DOCX |
| `/api/analyze/job` | POST | 3 | Extract JD requirements |
| `/api/tailor/resume` | POST | 4 | AI tailoring (ollama/nvidia) |
| `/api/score/ats` | POST | 5 | Keyword ATS score |
| `/api/export/pdf` | POST | 6-7 | LaTeX PDF export |

### Complete User Flow

```
http://localhost:5173
       ↓
   Login Page
       ↓
   Dashboard — 5 steps
       ↓
1  Upload Resume PDF → parsed into 6 clean sections
       ↓
2  Paste Job Description → extracted skills/requirements
       ↓
3  Tailor (Ollama local OR NVIDIA NIM cloud)
       ↓
4  ATS Score — instant keyword match (0-100)
       ↓
5  Export → LaTeX compiled PDF → preview in browser
```

---

> ✅ **ResumeForge is complete when:**
> - LaTeX PDF compiles cleanly — no duplicates, professional 1-page layout
> - Frontend runs at http://localhost:5173
> - Full pipeline works end-to-end in the browser
> - PDF preview shows in ExportPanel after download
> - All code merged to main
