"""
Surgical LaTeX tailoring.
Takes a master .tex file and makes minimal targeted changes for a specific job.
Does NOT rewrite content — only keyword substitution and bullet strengthening.
"""
import os
import re
import json
import logging
import requests

logger = logging.getLogger(__name__)

NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:14b"


SURGEON_SYSTEM_PROMPT = """You are a LaTeX resume surgeon.
Your job is to make MINIMAL, SURGICAL changes to an existing LaTeX resume.
You NEVER rewrite sections from scratch.
You NEVER change the structure, formatting, or commands.
You ONLY make these specific types of changes:
1. Add job-required keywords to the skills section (inline with existing skills)
2. Strengthen 2-3 experience/project bullets to mention required technologies
3. Reorder skills categories to put most relevant first
Everything else stays EXACTLY the same — same GPA, same URLs, same structure, same metrics.
"""


SURGEON_PROMPT_TEMPLATE = """
You are making SURGICAL changes to this LaTeX resume to target a specific job.

════════════════════════════════════════════
TARGET JOB
════════════════════════════════════════════
Job Title: {job_title}
Company: {company_name}
Required Skills: {required_skills}
Nice-to-Have Skills: {nicetohave_skills}

════════════════════════════════════════════
WHAT TO CHANGE (minimal list):
════════════════════════════════════════════
1. SKILLS SECTION: Add any required skills that are missing from the skills table.
   Add them to the most appropriate existing category row.
   Do NOT create new category rows.
   Example: If "CloudFormation" is required and not in AWS row → add it there.

2. EXPERIENCE BULLETS: In 2-3 bullets, naturally weave in 1-2 required keywords
   if they are genuinely related to what is described.
   ONLY if it is truthful and natural. Do NOT force keywords where they don't belong.
   Example: If bullet says "AWS infrastructure" and "EC2" is required → add "EC2" naturally.

3. SKILLS ORDER: Move the most relevant skills category to appear first in the table.

════════════════════════════════════════════
WHAT NOT TO CHANGE:
════════════════════════════════════════════
- GPA values (copy them exactly)
- Contact information, URLs
- All metrics and percentages
- Section structure and LaTeX commands
- Project descriptions (unless a keyword can be added very naturally)
- Education content
- Leadership content
- Overall document structure

════════════════════════════════════════════
MASTER LATEX RESUME (make changes to this):
════════════════════════════════════════════
{master_latex}

════════════════════════════════════════════
OUTPUT INSTRUCTIONS:
════════════════════════════════════════════
Return ONLY the modified LaTeX.
Start with \\documentclass — end with \\end{{document}}.
Make as few changes as possible while targeting the role.
If a required skill is already present, do NOT add it again.
"""


def call_nvidia_surgeon(prompt: str) -> str:
    api_key = os.getenv('NVIDIA_API_KEY', '')
    if not api_key:
        raise ValueError("NVIDIA_API_KEY not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": NVIDIA_MODEL,
        "messages": [
            {"role": "system", "content": SURGEON_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,   # very low — we want minimal changes
        "top_p": 0.9,
        "max_tokens": 4096,
        "stream": True
    }
    response = requests.post(NVIDIA_URL, headers=headers, json=payload,
                             stream=True, timeout=120)
    response.raise_for_status()

    result = ""
    for line in response.iter_lines():
        if line and line.startswith(b'data: '):
            data = line[6:]
            if data == b'[DONE]':
                break
            try:
                chunk = json.loads(data)
                delta = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                if delta:
                    result += delta
            except Exception:
                pass
    return result.strip()


def call_ollama_surgeon(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SURGEON_SYSTEM_PROMPT,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.1, "num_predict": 4096}
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=300)
    response.raise_for_status()
    result = response.json().get('response', '')
    result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
    return result.strip()


def extract_latex(raw: str) -> str:
    """Extract clean LaTeX from LLM output."""
    raw = re.sub(r'```latex\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    start = raw.find('\\documentclass')
    end = raw.rfind('\\end{document}')
    if start != -1 and end != -1:
        return raw[start:end + len('\\end{document}')].strip()
    return raw.strip()


def surgical_tailor(
    master_latex: str,
    job_title: str = "",
    company_name: str = "",
    required_skills: list = None,
    nicetohave_skills: list = None,
    provider: str = "nvidia"
) -> str:
    """
    Make surgical changes to master LaTeX to target a specific job.

    Args:
        master_latex: The perfect master .tex content
        job_title: Target job title
        company_name: Target company
        required_skills: List of required skills from JD
        nicetohave_skills: List of nice-to-have skills
        provider: 'nvidia' or 'ollama'

    Returns:
        str: Modified LaTeX with minimal surgical changes
    """
    required_skills = required_skills or []
    nicetohave_skills = nicetohave_skills or []

    prompt = SURGEON_PROMPT_TEMPLATE.format(
        job_title=job_title,
        company_name=company_name,
        required_skills=', '.join(required_skills),
        nicetohave_skills=', '.join(nicetohave_skills),
        master_latex=master_latex
    )

    logger.info(f"Surgical tailoring with {provider} for {job_title} at {company_name}")

    if provider == "nvidia":
        raw = call_nvidia_surgeon(prompt)
    else:
        raw = call_ollama_surgeon(prompt)

    result = extract_latex(raw)

    # Safety check — if result is dramatically shorter, something went wrong
    if len(result) < len(master_latex) * 0.7:
        logger.warning("Surgical result too short — falling back to master LaTeX")
        return master_latex

    logger.info(f"Surgical tailor complete: {len(master_latex)} → {len(result)} chars")
    return result
