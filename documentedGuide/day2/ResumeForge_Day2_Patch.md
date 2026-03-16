# ResumeForge — Day 2 Patch Guide
## Parser Accuracy Upgrade: Layout-Aware + Ollama LLM + Full LLM Fallback

---

> **Agent Instructions:** Work through Stage 0 → Stage 1 → Stage 2 → Stage 3 → Stage 4 in order.
> Do not skip stages. Read all listed files before writing any code.
> Server is already running — do NOT restart unless something breaks.
> Patch is complete only when all 5 verification checks in Stage 4 pass.

---

## Why This Patch Exists — Bugs Found After Day 2

After testing with `Resume_10March.pdf`, the parser scored **6.2/10** due to 4 bugs:

| Bug | Problem | Fixed In |
|-----|---------|----------|
| B1 | `pdfplumber extract_text()` merges multi-column skills table into a blob, bleeding into adjacent sections | Stage 1 |
| B2 | Project sub-headings (e.g. `"AI-Powered Job Application Tracker"`) detected as new section headings — projects fragmented into multiple blocks | Stage 1 |
| B3 | `LEADERSHIP & ACTIVITIES` typed as `unknown` — keywords missing from map | Stage 2 |
| B4 | LLM fallback never triggered because Ollama wasn't running | Stage 0 + Stage 3 |

**Target after patch: 9.5/10 — section_count = 6, zero `unknown` types**

---

## Before Writing Any Code — Read These Files

| File | What Changes |
|------|-------------|
| `backend/modules/parse/extractor.py` | Stage 1 — full replacement |
| `backend/modules/parse/section_detector.py` | Stage 2 + 3 — targeted changes only |
| `backend/routers/parse.py` | No changes |
| `backend/data/resumeforge.db` | No changes — existing rows stay |

---

## Stage 0 — Set Up Ollama (Do This Before Any Code)

Ollama must be installed and running before Stage 3 can be tested. Complete all steps below before touching any Python files. You can work on Stages 1 and 2 while the model downloads in the background.

### 0a — Start Ollama Server

Open a new terminal and run:

```bash
ollama serve
```

Keep this terminal open. If you see `Error: address already in use` — Ollama is already running, that is fine.

### 0b — Pull the llama3.2 Model

Open a second terminal and run:

```bash
ollama pull llama3.2
```

This downloads ~2GB. It runs in the background — continue with Stage 1 and 2 while it downloads.

Verify when complete:

```bash
ollama list
# Expected:
# NAME              ID      SIZE    MODIFIED
# llama3.2:latest   ...     2.0 GB  ...

curl http://localhost:11434/api/tags
# Expected: {"models":[{"name":"llama3.2:latest",...}]}
```

### 0c — Set Up launchd So Ollama Auto-Starts on Every Login

This ensures Ollama and the ResumeForge backend both start automatically whenever the Mac is logged in — no manual terminal commands needed ever again.

**Step 1 — Find the ollama binary path:**

```bash
which ollama
# Note the output — either /usr/local/bin/ollama or /opt/homebrew/bin/ollama
```

**Step 2 — Create the plist (run as ONE command, paste entire block):**

```bash
cat > ~/Library/LaunchAgents/com.ollama.serve.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.serve</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ollama</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ollama.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ollama.error.log</string>
</dict>
</plist>
PLIST
```

> **Important:** If `which ollama` returned `/opt/homebrew/bin/ollama`, open the created file and change the path in `<string>/usr/local/bin/ollama</string>` to match before loading.

**Step 3 — Load it (starts immediately and on every future login):**

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ollama.serve.plist
```

**Step 4 — Also fix the ResumeForge backend launchd (if not done yet):**

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.resumeforge.backend.plist
```

**Step 5 — Verify both are registered:**

```bash
launchctl list | grep -E "resumeforge|ollama"
# Expected: two lines, one for each service
```

---

## Stage 1 — Layout-Aware PDF Extraction

**File:** `backend/modules/parse/extractor.py` — replace the ENTIRE file content.

The key change: replace `page.extract_text()` with `page.extract_words()` using bounding boxes. Words are grouped by their Y pixel position to reconstruct visual lines — preventing multi-column skill tables from merging and keeping project sub-headings as single clean lines.

```python
import pdfplumber
from docx import Document as DocxDocument
from collections import defaultdict


# ─── PDF EXTRACTION ──────────────────────────────────────────────────────────

def extract_pdf(file_path: str) -> dict:
    """
    Layout-aware PDF extraction using bounding box word positions.
    Reconstructs lines by grouping words with similar Y coordinates,
    which prevents multi-column skill tables from bleeding into each other.
    """
    all_lines = []
    page_count = 0

    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=False,
            )

            if not words:
                # Fallback to basic extract_text for scanned/image PDFs
                text = page.extract_text()
                if text:
                    all_lines.extend(text.split("\n"))
                continue

            # Group words by their Y position (rounded to nearest 2px)
            lines_by_y = defaultdict(list)
            for word in words:
                y_key = round(word["top"] / 2) * 2
                lines_by_y[y_key].append(word)

            # Sort lines top to bottom, words left to right within each line
            for y_key in sorted(lines_by_y.keys()):
                line_words = sorted(lines_by_y[y_key], key=lambda w: w["x0"])
                line_text = " ".join(w["text"] for w in line_words).strip()
                if line_text:
                    all_lines.append(line_text)

            # Blank line between pages
            all_lines.append("")

    raw_text = "\n".join(all_lines).strip()
    return {"raw_text": raw_text, "page_count": page_count}


# ─── DOCX EXTRACTION ─────────────────────────────────────────────────────────

def extract_docx(file_path: str) -> dict:
    """Extract raw text from a DOCX file (paragraphs + table cells)."""
    doc = DocxDocument(file_path)
    lines = []

    for para in doc.paragraphs:
        if para.text.strip():
            lines.append(para.text.strip())

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    lines.append(cell.text.strip())

    raw_text = "\n".join(lines)
    return {"raw_text": raw_text, "page_count": 1}


# ─── UNIFIED ENTRY POINT ─────────────────────────────────────────────────────

def extract(file_path: str, file_format: str) -> dict:
    """Route to correct extractor based on file format."""
    if file_format == "pdf":
        return extract_pdf(file_path)
    elif file_format == "docx":
        return extract_docx(file_path)
    else:
        raise ValueError(f"Unsupported format: {file_format}")
```

### Sanity Check After Stage 1 (Run Before Moving to Stage 2)

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
python3 -c "
from modules.parse.extractor import extract_pdf
result = extract_pdf('/path/to/Resume_10March.pdf')
lines = result['raw_text'].split('\n')
print(f'Total lines: {len(lines)}')
print(f'Char count: {len(result[\"raw_text\"])}')
print('--- Skills area lines ---')
for i, l in enumerate(lines):
    if any(kw in l for kw in ['SKILL', 'Cloud', 'DevOps', 'Backend', 'IaC', 'Data &']):
        print(f'{i:3}: {l}')
"
```

**Expected:** `TECHNICAL SKILLS` on its own line. Each skill row (`Cloud & AWS EC2, ECS...`, `DevOps & CI/CD...`) on its own line. No project names mixed in.

---

## Stage 2 — Improved Section Detector

**File:** `backend/modules/parse/section_detector.py`

Make 3 targeted changes. Do NOT rewrite the whole file — only replace the specific items listed.

### Change 2a — Replace SECTION_KEYWORDS dict

```python
SECTION_KEYWORDS = {
    "contact":        ["contact", "personal info", "personal details", "about me", "reach me"],
    "summary":        ["summary", "objective", "profile", "about", "overview", "career objective"],
    "experience":     ["experience", "work experience", "employment", "work history",
                       "professional experience", "career history", "internship"],
    "education":      ["education", "academic", "qualification", "degree", "academics", "schooling"],
    "skills":         ["skills", "technical skills", "core competencies", "technologies",
                       "expertise", "tech stack", "tools", "competencies"],
    "projects":       ["projects", "personal projects", "key projects",
                       "portfolio", "notable projects", "work samples"],
    "certifications": ["certifications", "certificates", "licenses",
                       "credentials", "achievements", "awards", "honors"],
    "leadership":     ["leadership", "activities", "volunteer", "extracurricular",
                       "community", "involvement", "clubs", "organizations",
                       "leadership & activities", "activities & leadership"],
}

SECTION_TYPES = list(SECTION_KEYWORDS.keys())
```

### Change 2b — Replace classify_line() with improved version

Add `CONTENT_LINE_SIGNALS` constant immediately above the function:

```python
# Lines containing these signals are content lines, NOT section headings
CONTENT_LINE_SIGNALS = [
    " - ",
    " – ",
    " — ",
    "github",
    "http",
    "www.",
    "@",
    "•",
    "technologies:",
    "jan ", "feb ", "mar ", "apr ", "may ", "jun ",
    "jul ", "aug ", "sep ", "oct ", "nov ", "dec ",
]


def classify_line(line: str) -> tuple:
    """
    Returns (section_type, confidence) or (None, 0.0) if not a section heading.

    Improvements over Day 2 original:
    - Rejects lines with content signals (dates, URLs, bullets, dashes)
    - Prevents project/job sub-headings from splitting sections
    - Handles compound headings like 'LEADERSHIP & ACTIVITIES'
    """
    stripped = line.strip()
    if not stripped or len(stripped) < 2:
        return None, 0.0

    lower = stripped.lower()

    # Lines with content signals are NOT section headings
    for signal in CONTENT_LINE_SIGNALS:
        if signal in lower:
            return None, 0.0

    # Keyword match — high confidence
    for section_type, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return section_type, 1.0

    # ALL CAPS line with no content signals — medium confidence
    # Short (< 60 chars) and no digits (avoids job titles with years)
    if stripped.isupper() and len(stripped) < 60 and not any(c.isdigit() for c in stripped):
        return "unknown", 0.7

    return None, 0.0
```

### Change 2c — Replace split_into_blocks() with context-aware version

Add `MULTI_ITEM_SECTIONS` constant immediately above the function:

```python
# Inside these sections, only keyword matches (conf=1.0) can start a new section.
# ALL CAPS sub-headings (conf=0.7) are treated as content, not boundaries.
MULTI_ITEM_SECTIONS = {"projects", "experience", "education", "certifications", "leadership"}


def split_into_blocks(raw_text: str) -> list:
    """
    Split text into section blocks using heading detection.

    Key improvement: Once inside a MULTI_ITEM_SECTION, only a strong keyword
    match (confidence=1.0) can trigger a new section. ALL CAPS sub-headings
    (project titles, company names) are treated as content, not section splits.
    """
    lines = raw_text.split("\n")
    blocks = []
    current_heading = None
    current_type = "contact"
    current_confidence = 0.8
    current_lines = []

    for line in lines:
        section_type, confidence = classify_line(line)

        # Suppress low-confidence splits inside multi-item sections
        if current_type in MULTI_ITEM_SECTIONS and confidence < 1.0:
            section_type = None

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
            if line.strip():
                current_lines.append(line)

    # Flush final block
    if current_lines:
        blocks.append({
            "section_type":   current_type,
            "section_label":  current_heading or current_type.title(),
            "content_text":   "\n".join(current_lines).strip(),
            "confidence":     current_confidence,
            "detected_by":    "regex",
        })

    return [b for b in blocks if b["content_text"]]
```

---

## Stage 3 — Full LLM Fallback

**File:** `backend/modules/parse/section_detector.py`

> **Only proceed with Stage 3 after `ollama pull llama3.2` has finished downloading.**

### Change 3a — Add import at top of section_detector.py

Add this with the existing imports at the top of the file:

```python
import json as json_lib
```

### Change 3b — Add llm_full_parse() after existing llm_classify() function

```python
def llm_full_parse(raw_text: str) -> list | None:
    """
    Send the ENTIRE resume text to Ollama and ask it to return structured JSON.

    Triggered when overall regex quality is poor:
    - More than 2 blocks are 'unknown', OR
    - Average confidence across all blocks < 0.5

    Returns list of section dicts (same shape as split_into_blocks),
    or None if Ollama is unavailable or returns unparseable output.
    """
    if not ollama_available():
        logger.warning("Ollama unavailable — skipping full LLM parse fallback")
        return None

    prompt = (
        "You are a resume parser. Extract all sections from the resume text below.\n"
        "Return ONLY valid JSON — no explanation, no markdown, no backticks.\n"
        "Use this exact format:\n"
        '{"sections": [{"type": "contact", "label": "Contact", "content": "..."}, ...]}\n\n'
        "Valid section types: contact, summary, experience, education, skills, "
        "projects, certifications, leadership, other\n\n"
        "Rules:\n"
        "- Put ALL projects into ONE section with type 'projects'\n"
        "- Put ALL work experience into ONE section with type 'experience'\n"
        "- Skills and technologies into ONE 'skills' section\n"
        "- Leadership, activities, clubs into ONE 'leadership' section\n"
        "- Preserve full content text for each section\n\n"
        f"Resume:\n{raw_text[:4000]}"
    )

    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": DEFAULT_MODEL, "prompt": prompt, "stream": False},
            timeout=60
        )
        response_text = r.json().get("response", "").strip()

        # Strip markdown code fences if present
        if "```" in response_text:
            parts = response_text.split("```")
            response_text = parts[1] if len(parts) > 1 else parts[0]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        parsed = json_lib.loads(response_text)
        sections = parsed.get("sections", [])

        if not sections:
            logger.warning("LLM full parse returned empty sections list")
            return None

        result = []
        for i, sec in enumerate(sections):
            result.append({
                "section_type":   sec.get("type", "other"),
                "section_label":  sec.get("label", sec.get("type", "other").title()),
                "content_text":   sec.get("content", "").strip(),
                "confidence":     1.0,
                "detected_by":    "llm_full",
                "position_index": i,
            })

        logger.info(f"LLM full parse returned {len(result)} clean sections")
        return result

    except Exception as e:
        logger.warning(f"LLM full parse failed: {e}")
        return None
```

### Change 3c — Replace detect_sections() with 3-stage pipeline

```python
def detect_sections(raw_text: str) -> list:
    """
    Full 3-stage pipeline:

    Stage 1 — Regex detection (layout-aware, improved boundaries)
    Stage 2 — Per-block LLM reclassification for low-confidence blocks (conf < 0.6)
    Stage 3 — Full LLM parse fallback if overall quality is poor:
               * More than 2 blocks are 'unknown', OR
               * Average confidence < 0.5

    Returns list of section dicts ready for DB insertion.
    """
    blocks = split_into_blocks(raw_text)

    if not blocks:
        logger.warning("No blocks detected from raw text")
        return []

    # ── Evaluate overall parse quality ──────────────────────────────────────
    unknown_count  = sum(1 for b in blocks if b["section_type"] == "unknown")
    avg_confidence = sum(b["confidence"] for b in blocks) / len(blocks)
    low_conf       = [b for b in blocks if b["confidence"] < 0.6]

    logger.info(
        f"Regex parse: {len(blocks)} blocks | "
        f"avg_conf={avg_confidence:.2f} | "
        f"unknown={unknown_count} | "
        f"low_conf={len(low_conf)}"
    )

    # ── Stage 3: Full LLM parse if quality is poor ──────────────────────────
    if unknown_count > 2 or avg_confidence < 0.5:
        logger.info("Quality threshold not met — attempting full LLM parse")
        llm_result = llm_full_parse(raw_text)
        if llm_result:
            logger.info("Full LLM parse succeeded — using LLM result")
            return llm_result
        logger.warning("Full LLM parse unavailable/failed — keeping regex result")

    # ── Stage 2: Per-block LLM reclassification ──────────────────────────────
    if low_conf:
        if ollama_available():
            logger.info(f"Reclassifying {len(low_conf)} low-confidence block(s) via Ollama")
            for block in low_conf:
                new_type = llm_classify(block["content_text"])
                block["section_type"] = new_type
                block["detected_by"]  = "llm"
        else:
            logger.warning(
                f"Ollama unavailable — keeping regex result for {len(low_conf)} low-conf block(s)"
            )

    # ── Add position index ───────────────────────────────────────────────────
    for i, block in enumerate(blocks):
        block["position_index"] = i

    return blocks
```

---

## Stage 4 — Verification (All 5 Must Pass)

### Check 1 — Ollama running with model ready

```bash
ollama list
curl -s http://localhost:11434/api/tags
```

**Expected:** `llama3.2:latest` listed at ~2GB.

---

### Check 2 — Layout-aware extraction produces clean lines

```bash
cd /Users/nikunjshetye/Documents/resume-forger/backend
source venv/bin/activate
python3 -c "
from modules.parse.extractor import extract_pdf
result = extract_pdf('/path/to/Resume_10March.pdf')
lines = result['raw_text'].split('\n')
print('Total lines:', len(lines))
for i, l in enumerate(lines):
    if any(kw in l for kw in ['SKILL', 'Cloud &', 'DevOps', 'Backend', 'IaC']):
        print(f'{i:3}: {l}')
"
```

**Expected:** Skills on their own clean lines, no project names mixed in.

---

### Check 3 — Section detection: 6 sections, 0 unknown

```bash
python3 -c "
from modules.parse.extractor import extract_pdf
from modules.parse.section_detector import detect_sections
result = extract_pdf('/path/to/Resume_10March.pdf')
sections = detect_sections(result['raw_text'])
print(f'Total sections: {len(sections)}')
for s in sections:
    print(f'  [{s[\"position_index\"]}] {s[\"section_type\"]:15} | conf={s[\"confidence\"]:.1f} | by={s[\"detected_by\"]:10} | label={s[\"section_label\"]}')
unknown = [s for s in sections if s['section_type'] == 'unknown']
print(f'Unknown: {len(unknown)}')
print('PASS' if len(sections) == 6 and len(unknown) == 0 else 'FAIL')
"
```

**Expected:** 6 sections, 0 unknown, ends with `PASS`.

---

### Check 4 — Both launchd services registered

```bash
launchctl list | grep -E "resumeforge|ollama"
```

**Expected:** Two lines returned.

---

### Check 5 — Full end-to-end API upload

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=nikunj@resumeforge.com&password=securepass123" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://localhost:8000/api/parse/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/Resume_10March.pdf" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'resume_id:     {data[\"resume_id\"]}')
print(f'section_count: {data[\"section_count\"]}')
print(f'char_count:    {data[\"char_count\"]}')
for s in data['sections']:
    print(f'  [{s[\"position_index\"]}] {s[\"section_type\"]:15} | {s[\"detected_by\"]:10} | {s[\"section_label\"]}')
unknown = [s for s in data['sections'] if s['section_type'] == 'unknown']
print(f'Unknown: {len(unknown)}')
print('PASS' if data['section_count'] == 6 and len(unknown) == 0 else 'FAIL')
"
```

**Expected:** `section_count: 6`, `Unknown: 0`, ends with `PASS`.

---

## Score After Patch

| Section | Before | After |
|---------|--------|-------|
| contact | ✅ 10/10 | ✅ 10/10 |
| education | ✅ 10/10 | ✅ 10/10 |
| skills | ❌ 3/10 | ✅ 9/10 |
| experience | ✅ 8/10 | ✅ 10/10 |
| projects | ❌ 4/10 | ✅ 9/10 |
| leadership | ❌ 2/10 | ✅ 9/10 |
| **Overall** | **6.2/10** | **9.5/10** |

---

## What Is NOT Changed in This Patch

- `routers/parse.py` — no changes
- `models/` — no changes
- `schemas/` — no changes
- Existing DB rows — untouched
- Server — do NOT restart, uvicorn auto-reloads on `.py` file saves

---

> ✅ **Patch complete when Check 5 ends with `PASS` — section_count=6, unknown=0**
