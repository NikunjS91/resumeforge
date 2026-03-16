import re
import json
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:14b"
TIMEOUT = 180


# ─── OLLAMA HELPERS ──────────────────────────────────────────────────────────

def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def ollama_call(prompt: str) -> str | None:
    """Call qwen3:14b, strip think tags, return clean response."""
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": DEFAULT_MODEL, "prompt": prompt, "stream": False},
            timeout=TIMEOUT
        )
        response = r.json().get("response", "").strip()
        # Strip qwen3 thinking tags
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        return response if response else None
    except Exception as e:
        logger.warning(f"Ollama call error: {e}")
        return None


# ─── SECTION TAILOR ──────────────────────────────────────────────────────────

def tailor_section(
    section_type: str,
    section_content: str,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
) -> dict:
    """
    Tailor a single resume section to match the job description.
    Returns dict with tailored_text and improvement_notes.
    """
    all_skills = required_skills + nice_to_have_skills
    skills_str = ", ".join(all_skills[:20]) if all_skills else "not specified"

    prompt = (
        f"You are an expert resume writer. Rewrite this resume {section_type} section "
        f"to better match a {job_title} role at {company_name}.\n\n"
        f"Target skills to emphasize: {skills_str}\n\n"
        f"Rules:\n"
        f"- Keep all factual information accurate — do NOT invent experience or skills\n"
        f"- Emphasize existing relevant technologies and achievements\n"
        f"- Use strong action verbs (Led, Built, Architected, Optimized, Deployed)\n"
        f"- Keep quantified metrics if they exist (%, numbers, scale)\n"
        f"- Match keywords from the target skills list where truthfully applicable\n"
        f"- Keep roughly the same length as the original\n"
        f"- Return ONLY the rewritten section text, no explanation\n\n"
        f"Original {section_type} section:\n{section_content}"
    )

    tailored = ollama_call(prompt)
    if not tailored:
        logger.warning(f"Failed to tailor {section_type} section — keeping original")
        tailored = section_content

    # Generate improvement notes
    notes_prompt = (
        f"Compare the original and tailored versions of this resume {section_type} section. "
        f"List 2-3 specific improvements made. Be concise.\n\n"
        f"Original:\n{section_content[:500]}\n\n"
        f"Tailored:\n{tailored[:500]}\n\n"
        f"Return ONLY a JSON array of improvement strings like: "
        f'["Added AWS keyword alignment", "Strengthened action verbs"]'
    )
    notes_raw = ollama_call(notes_prompt)
    notes = []
    if notes_raw:
        notes_raw = re.sub(r'<think>.*?</think>', '', notes_raw, flags=re.DOTALL).strip()
        try:
            if "```" in notes_raw:
                notes_raw = notes_raw.split("```")[1].lstrip("json").strip()
            notes = json.loads(notes_raw)
        except Exception:
            notes = [notes_raw[:200]] if notes_raw else []

    return {
        "section_type": section_type,
        "original_text": section_content,
        "tailored_text": tailored,
        "improvement_notes": notes,
    }


# ─── MAIN TAILOR PIPELINE ────────────────────────────────────────────────────

# Sections worth tailoring — contact and education are not tailored
TAILORABLE_SECTIONS = {"experience", "projects", "skills", "summary", "leadership"}


def tailor_resume(
    resume_sections: list,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
) -> dict:
    """
    Full tailoring pipeline.
    - Tailors experience, projects, skills, summary sections
    - Passes through contact and education unchanged
    - Returns full tailored resume dict

    resume_sections: list of dicts with keys:
        section_type, section_label, content_text, position_index
    """
    if not ollama_available():
        raise RuntimeError("Ollama is not available. Cannot tailor resume.")

    tailored_sections = []
    all_improvement_notes = []

    logger.info(f"Tailoring {len(resume_sections)} sections for {job_title} at {company_name}")

    for section in sorted(resume_sections, key=lambda s: s.get("position_index", 0)):
        section_type = section.get("section_type", "other")
        content = section.get("content_text", "")

        if section_type in TAILORABLE_SECTIONS and content.strip():
            logger.info(f"Tailoring section: {section_type}")
            result = tailor_section(
                section_type=section_type,
                section_content=content,
                job_title=job_title,
                company_name=company_name,
                required_skills=required_skills,
                nice_to_have_skills=nice_to_have_skills,
            )
            tailored_sections.append({
                "section_type": section_type,
                "section_label": section.get("section_label", section_type.title()),
                "position_index": section.get("position_index", 0),
                "original_text": result["original_text"],
                "tailored_text": result["tailored_text"],
                "was_tailored": True,
                "improvement_notes": result["improvement_notes"],
            })
            all_improvement_notes.extend(result["improvement_notes"])
        else:
            # Pass through unchanged
            tailored_sections.append({
                "section_type": section_type,
                "section_label": section.get("section_label", section_type.title()),
                "position_index": section.get("position_index", 0),
                "original_text": content,
                "tailored_text": content,
                "was_tailored": False,
                "improvement_notes": [],
            })

    # Build full tailored text
    full_tailored = "\n\n".join(
        f"{s['section_label']}\n{s['tailored_text']}"
        for s in sorted(tailored_sections, key=lambda s: s["position_index"])
        if s["tailored_text"]
    )

    return {
        "tailored_sections": tailored_sections,
        "tailored_full_text": full_tailored,
        "sections_tailored": sum(1 for s in tailored_sections if s["was_tailored"]),
        "total_sections": len(tailored_sections),
        "improvement_notes": all_improvement_notes,
    }
