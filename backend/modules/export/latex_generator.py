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
from .data_validator import validate_sections
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

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

_TEMPLATE_FILES = {
    "classic": "professional.tex",
    "minimal": "minimal.tex",
    "modern":  "modern.tex",
}


def _load_template(template_name: str) -> str:
    """Load a template file. Returns empty string if not found."""
    fname = _TEMPLATE_FILES.get(template_name, "professional.tex")
    path = TEMPLATES_DIR / fname
    if path.exists():
        return path.read_text()
    logger.warning(f"Template file not found: {path}")
    return ""


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

    # ── Run validation first ──────────────────────────────────────────────────
    validation = validate_sections(sections)
    if validation['has_issues']:
        lines.append("=== DATA QUALITY WARNINGS — READ BEFORE GENERATING ===")
        lines.append(validation['warning_text'])
        lines.append("=== END WARNINGS ===")
        lines.append("")

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


def build_template_fill_prompt(
    template_content: str,
    data_summary: str,
    candidate_type: str,
    job_title: str = "",
    company_name: str = "",
) -> str:
    """
    Build a prompt that asks the LLM to fill in LATEX_* placeholders in the template.
    The LLM never touches the document structure — only replaces placeholder tokens.
    """
    target = f"Target role: {job_title} at {company_name}" if job_title else ""

    return f"""Fill in the LaTeX resume template below. Replace every LATEX_* placeholder with the correct value from the source data.

CRITICAL ACCURACY RULES:
R1. GPA: copy EXACTLY — if source says 3.84, write 3.84. Never round or change.
R2. URLs: copy EXACTLY — if source has https://linkedin.com/in/nikunj-shetye, use that full URL.
    If source has placeholder text like "LinkedIn URL", copy that text as the URL value.
R3. METRICS: copy ALL numbers EXACTLY — 35%, 40%, 45%, 60%, 99.9%, 76%, etc.
R4. Never invent numbers, project names, company names, or URLs.
R5. Include ALL skills categories, ALL projects, ALL experience from source.

PLACEHOLDER GUIDE:
- LATEX_FULL_NAME → candidate's full name only (no pronouns)
- LATEX_LOCATION → city and state (e.g., New York, NY)
- LATEX_PHONE_RAW → digits only (e.g., 5513627616)
- LATEX_PHONE_DISPLAY → formatted phone (e.g., (551)-362-7616)
- LATEX_EMAIL → email address
- LATEX_LINKEDIN_URL → full LinkedIn URL copied from source
- LATEX_GITHUB_URL → full GitHub URL copied from source
- LATEX_PDF_TITLE → "Resume - Full Name"
- LATEX_AUTHOR_NAME → Full Name
- LATEX_EXPERIENCE_BLOCK → use \\resumesubheading{{Company}}{{Dates}}{{Title}}{{Location}} then \\begin{{itemize}}...\\end{{itemize}}; max 4 bullets for current role, 2-3 for older
- LATEX_SKILLS_ROWS → one row per category: \\textbf{{Category}} & item1, item2, item3 \\\\
- LATEX_PROJECTS_BLOCK → \\textbf{{Project Name}} \\hfill {{(tech stack)}} then \\begin{{itemize}}...\\end{{itemize}}; max 3 bullets per project; include ALL projects
- LATEX_EDUCATION_BLOCK → \\resumesubheading{{School}}{{Dates}}{{Degree, GPA: X.XX/4.0}}{{Location}}
- LATEX_LEADERSHIP_BLOCK → activities/clubs in same format as experience, or a single \\vspace{{0pt}} if no leadership data

FORMAT RULES:
- Escape special chars: & → \\&, % → \\%, $ → \\$, # → \\#, _ → \\_
- Bullets start with action verbs (Led, Built, Deployed, Reduced, Increased, etc.)
- Do NOT use \\begin{{itemize}} for the contact header — it is already structured in the template

{target}

════════════════════════════
SOURCE DATA (copy values exactly — do not invent):
════════════════════════════
{data_summary}

════════════════════════════
TEMPLATE (replace LATEX_* tokens only — do NOT change any LaTeX commands or document structure):
════════════════════════════
{template_content}

Return ONLY the complete filled LaTeX. Start with \\documentclass, end with \\end{{document}}. No markdown, no explanations.
"""


def build_stage1_prompt(
    data_summary: str,
    candidate_type: str,
    job_title: str = "",
    company_name: str = "",
    template: str = "classic"
) -> str:

    candidate_rules = EXPERIENCED_RULES if candidate_type == 'experienced' else FRESHER_RULES
    template_config = TEMPLATES.get(template, TEMPLATES[DEFAULT_TEMPLATE])

    target = f"Target: {job_title} at {company_name}" if job_title else ""

    return f"""You are generating a LaTeX resume. Read all 3 blocks carefully.

════════════════════════════════════════════════════
BLOCK 1 — CRITICAL RULES (read before touching data)
════════════════════════════════════════════════════

ACCURACY RULES (violations = complete failure):
R1. COPY GPA EXACTLY — if source says 3.84, write 3.84. Never round. Never change.
R2. COPY URLs EXACTLY — if source has https://linkedin.com/in/nikunj-shetye, use that.
    If source has placeholder text like "LinkedIn URL", copy "LinkedIn URL" as-is.
R3. COPY METRICS EXACTLY — preserve ALL numbers from source data:
    - "reducing operational costs by 35%" → keep "35%"
    - "improving system uptime to 99.9%" → keep "99.9%"
    - "reducing deployment time by 40%" → keep "40%"
    - "improving page load times by 60%" → keep "60%"
    - "reducing API response time by 45%" → keep "45%"
    These are REAL metrics from the source — INCLUDE them!
R4. NO INVENTED NUMBERS — only omit numbers if they DON'T exist in source.
    If source has a metric, you MUST include it.
R5. NO INVENTED PROJECTS — only include projects explicitly named in the source data.

COMPLETENESS RULES:
R6. INCLUDE ALL SECTIONS — Education, Skills, Experience, Projects, Leadership.
    Do NOT drop any section even if space is tight.
R7. INCLUDE ALL SKILLS CATEGORIES — every category from source must appear.
    Shorten entries within a category before removing a whole category.
R8. INCLUDE ALL PROJECTS — every project from source must appear.
    Reduce to 3 bullets per project before removing a project entirely.

FORMATTING RULES:
R9. TARGET ONE PAGE — use these compression techniques:
    - Margins: 0.4in all sides
    - Line spacing: \\linespread{{0.85}} or \\renewcommand{{\\baselinestretch}}{{0.85}}
    - Section spacing: \\vspace{{2pt}} between sections
    - Bullet spacing: [noitemsep,topsep=0pt,parsep=0pt,partopsep=0pt]
    - Experience: MAX 4 bullets for current role
    - Projects: MAX 2 bullets each (keep all 3 projects with 2 bullets each)
    - Education: Combine to 2 lines per school
    PRIORITY: Include ALL projects/sections > strict 1-page limit.
R10. Escape all special chars: & → \\&  % → \\%  $ → \\$  # → \\#  _ → \\_
R11. PDFLATEX ONLY — DO NOT use \\usepackage{{fontspec}} or \\setmainfont (requires XeLaTeX).
    Use only: geometry, xcolor, enumitem, hyperref packages.

════════════════════════════════════════════════════
BLOCK 2 — SOURCE DATA (copy this exactly, do not invent)
════════════════════════════════════════════════════

{target}

{data_summary}

════════════════════════════════════════════════════
BLOCK 3 — STYLE AND FORMAT INSTRUCTIONS
════════════════════════════════════════════════════

Candidate type: {candidate_type}
{candidate_rules}

Template style:
{template_config['style_rules']}

════════════════════════════════════════════════════
FINAL REMINDER — CHECK BEFORE OUTPUTTING:
════════════════════════════════════════════════════
Before writing your output, verify:
✓ GPA matches source EXACTLY
✓ LinkedIn/GitHub are copied from source (real URL or placeholder, not invented)
✓ No metric was invented (all numbers came from source data)
✓ All sections present (Education, Skills, Experience, Projects, Leadership)
✓ All skills categories present
✓ ALL PROJECTS present (count them: Job Application Tracker, TrueSight, Sentiment Analysis, etc)
✓ Compressed to fit close to 1 page (but did NOT remove projects to achieve this)

Now generate ONLY the complete LaTeX code.
Start with \\documentclass — end with \\end{{document}}.
No markdown, no explanations, no code blocks.
"""


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

    # ── Template-fill approach (primary): LLM fills LATEX_* placeholders only ──
    template_content = _load_template(template)
    if template_content:
        logger.info(f"Stage 1: Template-fill approach with {provider} (template: {template})")
        prompt = build_template_fill_prompt(
            template_content=template_content,
            data_summary=data_summary,
            candidate_type=candidate_type,
            job_title=job_title,
            company_name=company_name,
        )
    else:
        # ── Fallback: scratch generation if template not found ──────────────────
        logger.warning(f"Template '{template}' not found — falling back to scratch generation")
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

    # Validate the template placeholders were filled (not left as LATEX_*)
    unfilled = [p for p in ["LATEX_FULL_NAME", "LATEX_EMAIL", "LATEX_EDUCATION_BLOCK"]
                if p in latex]
    if unfilled:
        logger.warning(f"Stage 1: {len(unfilled)} unfilled placeholder(s): {unfilled}")

    logger.info(f"Stage 1 complete: {len(latex)} chars generated")
    return latex
