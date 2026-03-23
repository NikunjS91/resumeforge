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
        r.raise_for_status()
        response_text = r.json().get("response", "").strip()
        logger.info(f"Ollama response received: {len(response_text)} chars")
        return response_text
    except Exception as e:
        logger.error(f"Ollama extract error: {e}")
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

    # Job title and company extraction - try multiple patterns

    # Pattern 1: "X at Y" (e.g., "Senior Engineer at Google")
    at_match = re.search(r'^(.+?)\s+at\s+(.+?)(?:\.|$)', jd_text, re.IGNORECASE)
    if at_match:
        result["job_title"] = at_match.group(1).strip()
        result["company_name"] = at_match.group(2).strip()
        logger.info(f"Regex pattern 1 (X at Y): title='{result['job_title']}', company='{result['company_name']}'")

    # Pattern 2: "Company: X" or "Company Name: X"
    if not result["company_name"]:
        company_match = re.search(r'company\s*(?:name)?:\s*([A-Z][^\n,]{2,40})', jd_text, re.IGNORECASE)
        if company_match:
            result["company_name"] = company_match.group(1).strip()
            logger.info(f"Regex pattern 2 (Company:): company='{result['company_name']}'")

    # Pattern 3: "Position: X" or "Role: X" or "Job Title: X"
    if not result["job_title"]:
        title_match = re.search(r'(?:position|role|job title|title):\s*([A-Z][^\n,]{5,60})', jd_text, re.IGNORECASE)
        if title_match:
            result["job_title"] = title_match.group(1).strip()
            logger.info(f"Regex pattern 3 (Position:): title='{result['job_title']}'")

    # Pattern 4: "Company is hiring/looking for/seeking a Role"
    if not result["company_name"] or not result["job_title"]:
        hiring_match = re.search(
            r'([A-Z][a-zA-Z\s]{2,30})\s+is\s+(?:hiring|looking for|seeking)\s+(?:a|an)?\s*([A-Z][^\n,]{5,60})',
            jd_text
        )
        if hiring_match:
            if not result["company_name"]:
                result["company_name"] = hiring_match.group(1).strip()
            if not result["job_title"]:
                result["job_title"] = hiring_match.group(2).strip()
            logger.info(f"Regex pattern 4 (X is hiring Y): company='{result['company_name']}', title='{result['job_title']}'")

    # Skills extraction (pattern: "Requirements:" or "Required:" or "Must have:" followed by comma-separated list)
    skills_match = re.search(
        r'(?:requirements?|required|must.?have|skills?|qualifications?)\s*:\s*([^.]+)',
        jd_text, re.IGNORECASE
    )
    if skills_match:
        skills_text = skills_match.group(1).strip()
        # Split by common delimiters
        skills = [s.strip() for s in re.split(r'[,;•\n]', skills_text) if s.strip()]
        result["required_skills"] = [s for s in skills if len(s) > 1 and len(s) < 50][:20]
        logger.info(f"Regex extracted {len(result['required_skills'])} required skills")

    # Nice-to-have skills extraction
    nice_match = re.search(
        r'(?:nice.?to.?have|preferred|bonus|plus|desirable)\s*:\s*([^.]+)',
        jd_text, re.IGNORECASE
    )
    if nice_match:
        nice_text = nice_match.group(1).strip()
        nice_skills = [s.strip() for s in re.split(r'[,;•\n]', nice_text) if s.strip()]
        result["nice_to_have_skills"] = [s for s in nice_skills if len(s) > 1 and len(s) < 50][:10]
        logger.info(f"Regex extracted {len(result['nice_to_have_skills'])} nice-to-have skills")

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
    Phase 1: Regex for seniority, remote, salary, basic company/title/skills.
    Phase 2: Ollama LLM for more accurate extraction (if available).
    Merges both results — LLM values override regex where both exist.

    Returns dict ready for DB insertion into the jobs table.
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("Job description text cannot be empty")

    # Phase 1 — regex (now includes basic company/title/skills extraction)
    result = extract_regex(jd_text)
    logger.info(f"Regex extracted: seniority={result['seniority_level']}, remote={result['is_remote']}, "
                f"company={result.get('company_name')}, title={result.get('job_title')}, "
                f"skills={len(result.get('required_skills', []))}")

    # Phase 2 — LLM (optional enhancement)
    llm_data = extract_llm(jd_text, result)
    if llm_data:
        logger.info(f"LLM extracted: company={llm_data.get('company_name')}, "
                    f"title={llm_data.get('job_title')}, "
                    f"required_skills={len(llm_data.get('required_skills', []))}")
        # LLM overrides regex for overlapping fields (if values are not None/empty)
        for key, val in llm_data.items():
            if val:
                result[key] = val
    else:
        logger.warning("LLM extraction failed or unavailable, using regex results only")
        # Ensure these keys exist even if not set by regex
        if "required_skills" not in result:
            result["required_skills"] = []
        if "nice_to_have_skills" not in result:
            result["nice_to_have_skills"] = []

    result["jd_raw_text"] = jd_text.strip()
    return result
