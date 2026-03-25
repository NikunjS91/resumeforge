"""
Stage 1: LLM generates complete LaTeX resume from scratch.
Uses all available data: resume sections, job requirements, tailored content.
"""
import os
import re
import json
import logging
import requests
from pathlib import Path
from .resume_rules import (
    UNIVERSAL_RULES, EXPERIENCED_RULES, FRESHER_RULES,
    FORMATTING_RULES, SECTION_ORDER_EXPERIENCED, SECTION_ORDER_FRESHER,
    STAGE_1_SYSTEM_PROMPT, TEMPLATES, DEFAULT_TEMPLATE
)

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:14b"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"
GENERATION_TIMEOUT = 300  # 5 minutes


def detect_candidate_type(sections: list) -> str:
    """
    Detect if candidate is experienced or fresher based on sections.
    Returns 'experienced' or 'fresher'.
    """
    experience_section = next(
        (s for s in sections if s.get('section_type') == 'experience'), None
    )
    if experience_section:
        content = experience_section.get('content_text', '')
        # If experience content is substantial (> 200 chars), likely experienced
        if len(content) > 200:
            return 'experienced'
    return 'fresher'


def build_data_summary(
    sections: list,
    job_title: str = "",
    company_name: str = "",
    required_skills: list = None,
    nicetohave_skills: list = None,
    improvement_notes: list = None,
    is_tailored: bool = False
) -> str:
    """Build a structured summary of all resume data for the LLM."""
    required_skills = required_skills or []
    nicetohave_skills = nicetohave_skills or []
    improvement_notes = improvement_notes or []

    lines = []

    if is_tailored and job_title:
        lines.append(f"TARGET JOB: {job_title} at {company_name}")
        if required_skills:
            lines.append(f"REQUIRED SKILLS: {', '.join(required_skills)}")
        if nicetohave_skills:
            lines.append(f"NICE-TO-HAVE SKILLS: {', '.join(nicetohave_skills)}")
        if improvement_notes:
            lines.append(f"AI IMPROVEMENT NOTES:")
            for note in improvement_notes[:5]:
                lines.append(f"  - {note}")
        lines.append("")

    lines.append("RESUME SECTIONS:")
    for section in sorted(sections, key=lambda s: s.get('position_index', 0)):
        sec_type = section.get('section_type', 'other')
        sec_label = section.get('section_label', sec_type)
        content = section.get('content_text', '').strip()
        if content:
            lines.append(f"\n[{sec_label.upper()} — type: {sec_type}]")
            lines.append(content)

    return '\n'.join(lines)


def build_stage1_prompt(
    data_summary: str,
    candidate_type: str,
    job_title: str = "",
    company_name: str = "",
    template: str = "classic"
) -> str:
    """Build the Stage 1 prompt for LaTeX generation."""

    rules = UNIVERSAL_RULES + "\n"
    section_order = SECTION_ORDER_EXPERIENCED

    if candidate_type == 'experienced':
        rules += EXPERIENCED_RULES
        section_order = SECTION_ORDER_EXPERIENCED
    else:
        rules += FRESHER_RULES
        section_order = SECTION_ORDER_FRESHER

    rules += "\n" + FORMATTING_RULES

    # Add template-specific style rules
    template_config = TEMPLATES.get(template, TEMPLATES[DEFAULT_TEMPLATE])
    rules += f"\n{template_config['style_rules']}"

    target_note = ""
    if job_title:
        target_note = f"\nTHIS RESUME IS BEING TAILORED FOR: {job_title} at {company_name}\nPrioritize and emphasize skills and experiences that match this role.\n"

    prompt = f"""
{rules}

{target_note}

SECTION ORDER TO USE: {' → '.join(section_order)}

Here is ALL the candidate's data:

{data_summary}

TASK: Generate a COMPLETE, COMPILABLE LaTeX resume using the data above.

CRITICAL REQUIREMENTS:
1. Generate ONLY the LaTeX code — no explanations, no markdown, no code blocks
2. Start with \\documentclass and end with \\end{{document}}
3. Use the EXACT formatting rules specified above
4. Include ALL relevant content from the data — do not skip sections
5. Fit everything on ONE PAGE by adjusting spacing if needed
6. Escape all special characters: & → \\&, % → \\%, $ → \\$, # → \\#, _ → \\_
7. Technologies lines in projects go INSIDE the itemize as \\item \\textbf{{Technologies:}} ...
8. Use the professional color scheme: name color #1a1a2e, section color #16213e
9. Make it ATS-friendly — no tables for content, no complex columns in body
10. Every bullet must have an action verb and a metric

Generate the complete LaTeX code now:
"""
    return prompt.strip()


def call_ollama(prompt: str, system: str) -> str:
    """Call Ollama for LaTeX generation."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_predict": 4096,
        }
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=GENERATION_TIMEOUT)
    response.raise_for_status()
    result = response.json().get('response', '')
    # Strip think tags
    result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL)
    return result.strip()


def call_nvidia(prompt: str, system: str) -> str:
    """Call NVIDIA NIM for LaTeX generation."""
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
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "top_p": 0.9,
        "max_tokens": 4096,
        "stream": True
    }
    response = requests.post(NVIDIA_URL, headers=headers, json=payload,
                             stream=True, timeout=GENERATION_TIMEOUT)
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


def extract_latex(raw_output: str) -> str:
    """Extract clean LaTeX from LLM output, removing any markdown wrappers."""
    # Remove markdown code blocks
    raw_output = re.sub(r'```latex\s*', '', raw_output)
    raw_output = re.sub(r'```\s*', '', raw_output)

    # Find the actual LaTeX content
    start = raw_output.find('\\documentclass')
    end = raw_output.rfind('\\end{document}')

    if start != -1 and end != -1:
        return raw_output[start:end + len('\\end{document}')].strip()

    # If no clean boundaries, return cleaned version
    return raw_output.strip()


def generate_latex_stage1(
    sections: list,
    job_title: str = "",
    company_name: str = "",
    required_skills: list = None,
    nicetohave_skills: list = None,
    improvement_notes: list = None,
    is_tailored: bool = False,
    provider: str = "ollama",
    template: str = "classic"
) -> str:
    """
    Stage 1: Generate complete LaTeX resume using LLM.

    Returns:
        str: Complete LaTeX code ready for review
    """
    candidate_type = detect_candidate_type(sections)
    logger.info(f"Detected candidate type: {candidate_type}")

    data_summary = build_data_summary(
        sections=sections,
        job_title=job_title,
        company_name=company_name,
        required_skills=required_skills,
        nicetohave_skills=nicetohave_skills,
        improvement_notes=improvement_notes,
        is_tailored=is_tailored
    )

    prompt = build_stage1_prompt(
        data_summary=data_summary,
        candidate_type=candidate_type,
        job_title=job_title,
        company_name=company_name,
        template=template
    )

    logger.info(f"Stage 1: Generating LaTeX with {provider}...")

    if provider == "nvidia":
        raw = call_nvidia(prompt, STAGE_1_SYSTEM_PROMPT)
    else:
        raw = call_ollama(prompt, STAGE_1_SYSTEM_PROMPT)

    latex = extract_latex(raw)
    logger.info(f"Stage 1 complete: {len(latex)} chars generated")
    return latex
