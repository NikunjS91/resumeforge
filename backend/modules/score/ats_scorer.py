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
    e.g. 'Proficiency in React' → also checks 'react'
    """
    kw = normalize(keyword)
    variants = {kw}
    variants.add(kw.replace(' ', '-'))
    variants.add(kw.replace(' ', ''))
    variants.add(kw.replace('.', ''))

    # Extract core skill from phrases like "Proficiency in React", "Experience with AWS"
    # e.g. "proficiency in react" → "react", "experience with docker" → "docker"
    core_match = re.match(
        r'^(?:proficiency|experience|knowledge|familiarity|expertise|ability|'
        r'understanding|skills?|working knowledge)\s+(?:in|with|of|using|on|for|across)\s+(.+)$',
        kw
    )
    if core_match:
        core = core_match.group(1).strip()
        variants.add(core)
        variants.add(core.replace(' ', '-'))
        variants.add(core.replace(' ', ''))

    # "2+ years of Python" or "3 years experience in AWS" → "python" / "aws"
    years_match = re.match(r'^\d+\+?\s+years?\s+(?:of\s+)?(?:experience\s+(?:in|with)\s+)?(.+)$', kw)
    if years_match:
        core = years_match.group(1).strip()
        variants.add(core)

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
