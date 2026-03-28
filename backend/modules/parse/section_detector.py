import json as json_lib
import re as _re
import requests
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:14b"

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
                       "leadership & activities", "activities & leadership",
                       "leadership and activities",
                       "activities and leadership"],
}

SECTION_TYPES = list(SECTION_KEYWORDS.keys())


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
    "tech stack:",
    "stack:",
    "tools:",
    "frameworks:",
    "languages:",
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

    # Keyword match — high confidence (word-boundary to avoid substring false positives)
    for section_type, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if _re.search(r'\b' + _re.escape(kw) + r'\b', lower):
                return section_type, 1.0

    # ALL CAPS line with no content signals — medium confidence
    # Short (< 60 chars) and no digits (avoids job titles with years)
    if stripped.isupper() and len(stripped) < 60 and not any(c.isdigit() for c in stripped):
        return "unknown", 0.7

    return None, 0.0


# Inside these sections, only keyword matches (conf=1.0) can start a new section.
# ALL CAPS sub-headings (conf=0.7) are treated as content, not boundaries.
MULTI_ITEM_SECTIONS = {"projects", "experience", "education", "certifications", "leadership"}

# Within a projects block, lines starting with these prefixes are content, NOT new section headings.
INLINE_CONTENT_PREFIXES = {
    "technologies:", "tech stack:", "stack:",
    "tools:", "frameworks:", "languages:",
    "built with:", "tech:", "techstack:",
}


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

        # Within projects, treat inline content prefixes as content not new sections
        if section_type is not None and current_type == "projects":
            line_lower = line.strip().lower()
            if any(line_lower.startswith(p) for p in INLINE_CONTENT_PREFIXES):
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

        # Strip qwen3 thinking tags
        import re
        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()

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
