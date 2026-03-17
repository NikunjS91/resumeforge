import os
import re
import json
import json as json_lib
import logging
import requests
from openai import OpenAI

logger = logging.getLogger(__name__)

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:14b"
TIMEOUT = 180
ONESHOT_TIMEOUT = 600   # one-shot sends full resume — needs more time

NVIDIA_NIM_BASE  = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL     = "meta/llama-3.3-70b-instruct"
NVIDIA_TIMEOUT   = 60


# ─── OLLAMA HELPERS ──────────────────────────────────────────────────────────

def ollama_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def ollama_call(prompt: str, timeout: int = TIMEOUT) -> str | None:
    """Call qwen3:14b, strip think tags, return clean response."""
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": DEFAULT_MODEL, "prompt": prompt, "stream": False, "think": False},
            timeout=timeout
        )
        response = r.json().get("response", "").strip()
        # Strip qwen3 thinking tags
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()
        return response if response else None
    except Exception as e:
        logger.warning(f"Ollama call error: {e}")
        return None


def nvidia_nim_call(prompt: str) -> str | None:
    """
    Call NVIDIA NIM hosted API using streaming mode.
    Base URL: https://integrate.api.nvidia.com/v1
    Model: meta/llama-3.3-70b-instruct
    """
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        logger.warning("NVIDIA_API_KEY not found in environment")
        return None
    try:
        client = OpenAI(
            base_url=NVIDIA_NIM_BASE,
            api_key=api_key,
        )
        completion = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            top_p=0.7,
            max_tokens=4000,
            stream=True,
        )
        # Collect streamed chunks
        result = ""
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                result += chunk.choices[0].delta.content

        result = result.strip()
        # Strip think tags just in case
        result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
        logger.info(f"NVIDIA NIM streaming call successful — model={NVIDIA_MODEL}, chars={len(result)}")
        return result if result else None
    except Exception as e:
        logger.warning(f"NVIDIA NIM call failed: {e}")
        return None


def tailor_resume_oneshot(
    resume_sections: list,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
    provider: str = "ollama",
) -> list | None:
    """
    Send the ENTIRE resume to qwen3:14b in ONE call.
    Returns list of tailored section dicts or None if failed.

    This replaces 12 sequential calls with 1 call — ~15min → ~2min.
    """
    if not ollama_available():
        return None

    # Build full resume text from sections
    resume_text = "\n\n".join(
        f"{s.get('section_label', s.get('section_type', '').upper())}\n{s.get('content_text', '')}"
        for s in sorted(resume_sections, key=lambda x: x.get('position_index', 0))
        if s.get('content_text', '').strip()
    )

    required_str   = ", ".join(required_skills[:20]) if required_skills else "not specified"
    nicetohave_str = ", ".join(nice_to_have_skills[:10]) if nice_to_have_skills else "none"

    # Sections to tailor — skip contact and education
    tailorable_types = {"experience", "projects", "skills", "summary", "leadership", "unknown"}
    sections_to_tailor = [
        s for s in resume_sections
        if s.get("section_type") in tailorable_types and s.get("content_text", "").strip()
    ]
    section_list = ", ".join(s.get("section_type") for s in sections_to_tailor)

    prompt = (
        "/no_think\n\n"
        f"You are an expert resume tailor. Rewrite the following resume sections "
        f"to better match a {job_title} role at {company_name}.\n\n"
        f"Sections to rewrite: {section_list}\n"
        f"Required skills to emphasize: {required_str}\n"
        f"Nice to have skills: {nicetohave_str}\n\n"
        f"Rules:\n"
        f"- Keep ALL facts accurate — do NOT invent experience or skills\n"
        f"- Use strong action verbs (Led, Built, Architected, Deployed, Optimized)\n"
        f"- Preserve quantified metrics (%, numbers, scale)\n"
        f"- Match keywords from required skills where truthfully applicable\n"
        f"- Keep roughly the same length as the original\n"
        f"- For sections NOT in the list above, return the original text unchanged\n\n"
        f"Return ONLY valid JSON — no explanation, no markdown, no backticks:\n"
        f'{{"sections": [{{"section_type": "skills", "tailored_text": "...", '
        f'"improvement_notes": ["note1", "note2"]}}, ...]}}\n\n'
        f"Full Resume:\n{resume_text[:4000]}"
    )

    # Route to the correct provider
    if provider == "nvidia":
        logger.info("Using NVIDIA NIM for one-shot tailoring")
        response = nvidia_nim_call(prompt)
        if not response:
            logger.warning("NVIDIA NIM failed — falling back to Ollama")
            response = ollama_call(prompt, timeout=ONESHOT_TIMEOUT)
    else:
        response = ollama_call(prompt, timeout=ONESHOT_TIMEOUT)
    if not response:
        logger.warning("One-shot tailor failed — Ollama returned empty response")
        return None

    try:
        # Strip markdown fences if present
        if "```" in response:
            parts = response.split("```")
            response = parts[1] if len(parts) > 1 else parts[0]
            if response.startswith("json"):
                response = response[4:]

        data = json_lib.loads(response.strip())
        tailored_map = {
            s["section_type"]: s
            for s in data.get("sections", [])
        }

        # Build result aligned to original sections
        result = []
        for sec in sorted(resume_sections, key=lambda x: x.get("position_index", 0)):
            sec_type = sec.get("section_type", "other")
            tailored = tailored_map.get(sec_type)

            if tailored and sec_type in tailorable_types:
                result.append({
                    "section_type":   sec_type,
                    "section_label":  sec.get("section_label", sec_type.title()),
                    "position_index": sec.get("position_index", 0),
                    "original_text":  sec.get("content_text", ""),
                    "tailored_text":  tailored.get("tailored_text", sec.get("content_text", "")),
                    "was_tailored":   True,
                    "improvement_notes": tailored.get("improvement_notes", []),
                })
            else:
                result.append({
                    "section_type":   sec_type,
                    "section_label":  sec.get("section_label", sec_type.title()),
                    "position_index": sec.get("position_index", 0),
                    "original_text":  sec.get("content_text", ""),
                    "tailored_text":  sec.get("content_text", ""),
                    "was_tailored":   False,
                    "improvement_notes": [],
                })

        logger.info(f"One-shot tailor returned {len(result)} sections")
        return result

    except Exception as e:
        logger.warning(f"One-shot parse failed: {e} | response: {response[:200]}")
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
TAILORABLE_SECTIONS = {
    "experience",
    "projects",
    "skills",
    "summary",
    "leadership",
    "unknown",      # catches any unrecognised but valuable sections
}


def tailor_resume(
    resume_sections: list,
    job_title: str,
    company_name: str,
    required_skills: list,
    nice_to_have_skills: list,
    provider: str = "ollama",
) -> dict:
    """
    Full tailoring pipeline — one-shot approach for speed.

    Strategy:
    1. Try one-shot: send full resume in ONE LLM call → ~2 minutes
    2. If one-shot fails: fall back to per-section → ~15 minutes
    """
    if not ollama_available():
        raise RuntimeError("Ollama is not available. Cannot tailor resume.")

    logger.info(
        f"Starting one-shot tailor for {job_title} at {company_name} "
        f"({len(resume_sections)} sections)"
    )

    # ── Try one-shot first ───────────────────────────────────────────
    tailored_sections = tailor_resume_oneshot(
        resume_sections=resume_sections,
        job_title=job_title,
        company_name=company_name,
        required_skills=required_skills,
        nice_to_have_skills=nice_to_have_skills,
        provider=provider,
    )

    # ── Fallback to per-section if one-shot failed ───────────────────
    if not tailored_sections:
        logger.warning("One-shot failed — falling back to per-section tailoring")
        tailored_sections = []
        for section in sorted(resume_sections, key=lambda s: s.get("position_index", 0)):
            section_type = section.get("section_type", "other")
            content = section.get("content_text", "")

            if section_type in TAILORABLE_SECTIONS and content.strip():
                result = tailor_section(
                    section_type=section_type,
                    section_content=content,
                    job_title=job_title,
                    company_name=company_name,
                    required_skills=required_skills,
                    nice_to_have_skills=nice_to_have_skills,
                )
                tailored_sections.append({
                    "section_type":    section_type,
                    "section_label":   section.get("section_label", section_type.title()),
                    "position_index":  section.get("position_index", 0),
                    "original_text":   result["original_text"],
                    "tailored_text":   result["tailored_text"],
                    "was_tailored":    True,
                    "improvement_notes": result["improvement_notes"],
                })
            else:
                tailored_sections.append({
                    "section_type":    section_type,
                    "section_label":   section.get("section_label", section_type.title()),
                    "position_index":  section.get("position_index", 0),
                    "original_text":   content,
                    "tailored_text":   content,
                    "was_tailored":    False,
                    "improvement_notes": [],
                })

    # ── Build full tailored text ─────────────────────────────────────
    full_tailored = "\n\n".join(
        f"{s['section_label']}\n{s['tailored_text']}"
        for s in sorted(tailored_sections, key=lambda s: s["position_index"])
        if s["tailored_text"]
    )

    all_notes = [
        note
        for s in tailored_sections
        for note in s.get("improvement_notes", [])
    ]

    return {
        "tailored_sections":  tailored_sections,
        "tailored_full_text": full_tailored,
        "sections_tailored":  sum(1 for s in tailored_sections if s["was_tailored"]),
        "total_sections":     len(tailored_sections),
        "improvement_notes":  all_notes,
    }
