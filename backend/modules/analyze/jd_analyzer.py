import re
import json
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:14b"


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
            timeout=180
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
    r'\bfully remote\b',
    r'\b100% remote\b',
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
        # Strip qwen3 thinking tags
        import re
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

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
