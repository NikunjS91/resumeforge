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


def _count_bullets(content: str) -> int:
    """Count bullet points in a section content string (excluding Technologies lines)."""
    return sum(1 for line in content.splitlines()
               if line.strip().startswith(('•', '-', '*', '\\item', '·'))
               and 'technologies' not in line.lower())


def _strip_bullet(line: str) -> str:
    """Remove leading bullet character and whitespace from a line."""
    import re as _re
    return _re.sub(r'^[•\-\*·\s]+', '', line).strip()


def _normalize_project_content(content: str) -> list:
    """
    Normalize project content where bullets may span multiple lines.
    Handles formats like:
      "•\\nLine 1\\nwrapped continuation\\n•\\nLine 2"
      "Technologies: ..." (no leading bullet — kept as bullet-like)
    Returns a list of clean lines where each bullet is a single string.
    """
    raw = content.splitlines()
    result = []
    in_bullet = False  # True when the last appended line was a bullet

    i = 0
    while i < len(raw):
        line = raw[i]
        stripped = line.strip()

        if not stripped:
            in_bullet = False
            i += 1
            continue

        # Lone bullet char on its own line — merge with next text line
        if stripped in ('•', '-', '*', '·'):
            if i + 1 < len(raw):
                next_stripped = raw[i + 1].strip()
                if next_stripped and next_stripped not in ('•', '-', '*', '·'):
                    result.append('• ' + next_stripped)
                    # Technologies is always the last item — don't treat as continuable bullet
                    in_bullet = not next_stripped.lower().startswith('technologies:')
                    i += 2
                    continue
            # Lone bullet with nothing after — skip
            i += 1
            continue

        # Technologies: line — treat as a special bullet-like line
        if stripped.lower().startswith('technologies:'):
            result.append(line)
            in_bullet = False
            i += 1
            continue

        # Normal bullet line (starts with bullet char after text)
        if stripped.startswith(('•', '-', '*', '·')):
            result.append(line)
            # Technologies is always the last bullet — no continuation expected after it
            in_bullet = 'technologies' not in stripped.lower()
            i += 1
            continue

        # Non-bullet text line
        if in_bullet and result:
            # Continuation of the previous wrapped bullet — join onto last line
            result[-1] = result[-1].rstrip() + ' ' + stripped
            i += 1
            continue

        # Project heading
        result.append(line)
        in_bullet = False
        i += 1

    return result


def _parse_projects(content: str) -> list:
    """
    Parse individual projects from the projects section content.
    Returns list of dicts: {name, github_suffix, bullets, has_technologies, tech_line, raw_block}
    Handles bullet-on-separate-line format and Technologies: lines without leading bullet.
    """
    projects = []
    lines = _normalize_project_content(content)
    current_name = ""
    current_github = ""
    current_lines = []

    def _save_project():
        if not current_name:
            return
        block = '\n'.join(current_lines)
        # Technologies: find any line containing "technologies:" (with or without leading bullet)
        tech_line = next(
            (_strip_bullet(l) for l in current_lines if 'technologies' in l.lower()),
            ""
        )
        bullet_count = sum(
            1 for l in current_lines
            if l.strip() and 'technologies' not in l.lower()
        )
        projects.append({
            'name': current_name,
            'github_suffix': current_github,
            'bullets': bullet_count,
            'has_technologies': bool(tech_line),
            'tech_line': tech_line,
            'raw_block': block
        })

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Treat as bullet if: starts with bullet char OR is a Technologies line
        is_bullet = (
            stripped.startswith(('•', '-', '*', '·')) or
            stripped.lower().startswith('technologies:')
        )
        if not is_bullet:
            # Save previous project before starting new one
            _save_project()
            # Parse "Project Name GitHub" or "Project Name" from heading
            if ' GitHub' in stripped:
                current_name = stripped[:stripped.rfind(' GitHub')].strip()
                current_github = 'GitHub'
            else:
                current_name = stripped
                current_github = ''
            current_lines = []
        else:
            current_lines.append(line)

    # Save last project
    _save_project()

    return projects


def build_data_summary(
    sections: list,
    job_title: str = "",
    company_name: str = "",
    required_skills: list = None,
    nicetohave_skills: list = None,
    improvement_notes: list = None,
    is_tailored: bool = False,
    candidate_type: str = "experienced"
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
        if not content:
            continue

        # ── BUG-011: suppress coursework for experienced candidates ───────────
        if sec_type == 'coursework' and candidate_type == 'experienced':
            continue  # LLM cannot output what it never sees

        # ── BUG-011: also strip "Relevant Coursework:" line from education ──
        if sec_type == 'education' and candidate_type == 'experienced':
            cleaned_lines = [
                l for l in content.splitlines()
                if 'relevant coursework' not in l.lower()
                and not l.strip().lower().startswith('coursework')
            ]
            content = '\n'.join(cleaned_lines).strip()

        # ── BUG-008: annotate experience bullet count ─────────────────────────
        if sec_type == 'experience':
            bullet_count = _count_bullets(content)
            lines.append(
                f"\n[{sec_label.upper()} — type: {sec_type}]"
                f"\n[COMPLETENESS: source has {bullet_count} bullets — "
                f"output ALL {bullet_count}, NONE dropped, NONE merged]"
            )
            lines.append(content)
            continue

        # ── BUG-009/012/018/019: annotate projects with order, names, bullets ──
        if sec_type == 'projects':
            projects = _parse_projects(content)
            lines.append(f"\n[{sec_label.upper()} — type: {sec_type}]")
            lines.append(
                "[ORDER: output projects in EXACTLY this sequence — "
                "PROJECT 1 first, PROJECT 2 second, PROJECT 3 third. "
                "Do NOT reorder for job relevance or any other reason.]"
            )
            for idx, proj in enumerate(projects, 1):
                # Pre-format the LaTeX heading so LLM just copies it
                gh = r" \hfill \href{https://github.com/NikunjS91}{GitHub}" if proj['github_suffix'] else ""
                latex_heading = f"\\textbf{{{proj['name']}}}{gh}"
                lines.append(
                    f"\n[PROJECT {idx} of {len(projects)}]"
                    f"\n[EXACT HEADING TO USE: {latex_heading}]"
                    f"\n[BULLETS: source has {proj['bullets']} — output ALL {proj['bullets']}]"
                )
                if proj['has_technologies']:
                    lines.append(
                        f"[TECHNOLOGIES LINE — include as last bullet: "
                        f"\\item \\textbf{{Technologies:}} {proj['tech_line'].replace('Technologies:', '').strip()}]"
                    )
                lines.append(proj['name'])
                lines.append(proj['raw_block'])
            continue

        # ── BUG-013: annotate leadership with explicit LATEX_LEADERSHIP_BLOCK mapping ──
        if sec_type == 'leadership':
            lines.append(
                f"\n[{sec_label.upper()} — type: {sec_type}]"
                f"\n[CRITICAL: This section MUST fill LATEX_LEADERSHIP_BLOCK. "
                f"It is MANDATORY. An empty LATEX_LEADERSHIP_BLOCK is a critical error.]"
            )
            lines.append(content)
            continue

        # ── Default: append section as-is ────────────────────────────────────
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
    coursework_rule = (
        "EXPERIENCED CANDIDATE: LATEX_COURSEWORK_BLOCK MUST be an empty string. "
        "Delete the token entirely — do NOT output any coursework section."
        if candidate_type == "experienced"
        else "FRESHER CANDIDATE: include coursework in LATEX_COURSEWORK_BLOCK if present in source."
    )

    return f"""Fill in the LaTeX resume template below. Replace every LATEX_* placeholder with the correct value from the source data.

════════════════════════════════════════════
ACCURACY RULES (violations = failure):
════════════════════════════════════════════
R1. GPA: copy EXACTLY — if source says 3.84, write 3.84. If source says 3.5, write 3.5. Never change.
R2. URLs: copy EXACTLY from source. If source has "LinkedIn URL" as placeholder text, use that text as the href value.
R3. METRICS: copy ALL percentages and numbers EXACTLY — 35%, 40%, 76%, 85%, 20%, etc.
R4. Never invent numbers, dates, company names, project names, or URLs.

════════════════════════════════════════════
COMPLETENESS RULES (missing content = failure):
════════════════════════════════════════════
C1. SKILLS: count the skill categories in source data — include EVERY SINGLE ONE as its own row.
    Do NOT merge categories. Do NOT drop categories. If source has 10 categories, output 10 rows.
    CRITICAL: Only include skill categories that are EXPLICITLY listed in the skills section of the source.
    NEVER infer or add skill categories from the experience or projects sections (e.g. do NOT add
    "Frontend: React" just because React appears in a job bullet — it must be in the skills section).
C2. PROJECTS: include ALL projects from source. Include ALL bullets from source (up to 6 per project).
    Keep specific metrics ("76% accuracy", "85% accuracy", "20% attrition reduction") — these are real.
    For each project, if a Technologies line exists in the source (e.g. "Technologies: React, Node.js..."),
    include it as the LAST bullet: \\item \\textbf{{Technologies:}} React, Node.js, ...
    If the source has a GitHub link for a project, add it right-aligned in the heading:
    \\textbf{{Project Name}} \\hfill \\href{{https://github.com/...}}{{GitHub}}
C3. EXPERIENCE: include ALL bullets for each role — do NOT cap or drop any bullets.
    If source has 6 bullets, output all 6. Only reduce if the page strictly cannot fit.
C4. VOLUNTEER WORK: if source has volunteer work or a volunteer section, include it in LATEX_LEADERSHIP_BLOCK.
C5. LEADERSHIP: if source has a leadership/clubs section, include it in LATEX_LEADERSHIP_BLOCK alongside volunteer work.
    CRITICAL: NEVER drop the Leadership & Activities section if it exists in the source. It is MANDATORY.
C6. LATEX_LEADERSHIP_BLOCK MAPPING: The source section annotated with type "leadership" ALWAYS maps to
    LATEX_LEADERSHIP_BLOCK. If you output an empty LATEX_LEADERSHIP_BLOCK when the source has a leadership
    section, that is a critical failure. Go back and fill it.
C7. PROJECT ORDER: Projects are annotated [PROJECT 1], [PROJECT 2], [PROJECT 3] in the source.
    Output them in EXACTLY that order. Do NOT reorder by JD relevance or any other reason.
C8. PROJECT NAMES: Use the EXACT name shown in "EXACT NAME:" annotation — every word, dash, and subtitle.
    Do NOT shorten, abbreviate, or drop any part. "AI-Powered Job Application Tracker - Cloud Deployed"
    must appear in full — never as "Job Application Tracker".

════════════════════════════════════════════
PLACEHOLDER GUIDE:
════════════════════════════════════════════
- LATEX_FULL_NAME → candidate's full name only (no pronouns, no (He/Him))
- LATEX_LOCATION → city and state only (e.g., New York, NY)
- LATEX_PHONE_RAW → digits only, no formatting (e.g., 5513627616)
- LATEX_PHONE_DISPLAY → formatted phone (e.g., (551)-362-7616)
- LATEX_EMAIL → email address
- LATEX_LINKEDIN_URL → exact LinkedIn URL or placeholder text from source
- LATEX_GITHUB_URL → exact GitHub URL or placeholder text from source
- LATEX_PDF_TITLE → "Resume - Full Name"
- LATEX_AUTHOR_NAME → Full Name

- LATEX_EXPERIENCE_BLOCK →
    For each role: \\resumesubheading{{Job Title}}{{Dates}}{{Company Name}}{{Location}}
    The Job Title MUST be arg #1 (rendered bold). Company Name is arg #3 (rendered italic).
    followed by \\begin{{itemize}} with ALL bullets from source — include every bullet, do not cap \\end{{itemize}}
    Include volunteer/internship roles here ONLY if they are work experience (not in volunteer section).

- LATEX_SKILLS_ROWS →
    ONE ROW PER CATEGORY. Format: \\textbf{{Category Name}} & skill1, skill2, skill3, skill4 \\\\
    Count categories in source and generate EXACTLY that many rows.
    Example if source has Programming Languages, Data Science Libraries, Cloud Platforms, DevOps:
    \\textbf{{Programming Languages}} & Python, R, SQL \\\\
    \\textbf{{Data Science Libraries}} & NumPy, Pandas, Scikit-learn, TensorFlow \\\\
    \\textbf{{Cloud Platforms}} & AWS (EC2, S3, Lambda), Google Cloud \\\\
    \\textbf{{DevOps Tools}} & Docker, Kubernetes, Terraform \\\\

- LATEX_PROJECTS_BLOCK →
    For each project: \\textbf{{Project Name}} \\hfill {{(Technologies Used)}}
    followed by \\begin{{itemize}} with ALL bullets from source \\end{{itemize}}
    Include ALL projects. Keep ALL metrics (accuracy %, attrition reduction %, etc.)

- LATEX_EDUCATION_BLOCK →
    For each school: \\resumesubheading{{School Full Name}}{{Graduation Date}}{{Degree — GPA: X.XX/scale}}{{City, Country}}
    Include BOTH schools if source has two.

- LATEX_COURSEWORK_BLOCK →
    IF source has a "Relevant Coursework" or "Coursework" section:
      \\resumesection{{Relevant Coursework}}
      followed by course names as a compact comma-separated paragraph or pipe-separated list.
    IF source has NO coursework section: leave this placeholder as an EMPTY STRING (delete the token entirely).

- LATEX_LEADERSHIP_BLOCK →
    IF source has leadership clubs OR volunteer work:
      \\resumesection{{Leadership \\& Activities}}
      followed by ALL volunteer entries AND all leadership club entries using \\resumesubheading + \\begin{{itemize}}
      Include BOTH volunteer work section AND leadership section from source here.
    IF source has NEITHER: leave this placeholder as an EMPTY STRING (delete the token entirely).

════════════════════════════════════════════
FORMAT RULES:
════════════════════════════════════════════
- Escape: & → \\&, % → \\%, $ → \\$, # → \\#, _ → \\_
- Bullet points start with action verbs (Led, Built, Deployed, Reduced, Increased, Developed, etc.)
- Do NOT use \\begin{{itemize}} for the contact header — it is already structured in the template
- Do NOT add section headers outside the designated blocks
- NEVER add a Contact or Personal Information section in the resume body. Contact info belongs
  ONLY in the header \\begin{{center}} block already in the template.
- CANDIDATE TYPE: {candidate_type.upper()} — {coursework_rule}

{target}

════════════════════════════
SOURCE DATA (copy values exactly — do not invent or omit):
════════════════════════════
{data_summary}

════════════════════════════
TEMPLATE (replace LATEX_* tokens only — do NOT change any LaTeX commands or document structure):
════════════════════════════
{template_content}

════════════════════════════
FINAL CHECKS (verify before outputting):
════════════════════════════
✓ LATEX_LEADERSHIP_BLOCK is NOT empty — source has a leadership section, it MUST appear
✓ LATEX_COURSEWORK_BLOCK is an empty string — experienced candidate, no coursework section
✓ Projects appear in ORDER: [PROJECT 1] first, [PROJECT 2] second, [PROJECT 3] third
✓ Each project uses its EXACT NAME from the "EXACT NAME:" annotation — not shortened
✓ Each project annotated with Technologies has it as the last \\item \\textbf{{Technologies:}}
✓ Experience has ALL bullets matching the [COMPLETENESS: N bullets] annotation count
✓ GPA is copied exactly from source

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
✓ All sections present (Experience, Skills, Projects, Education, Leadership)
✓ Skills table has ONLY categories from the source skills section — no inferred categories from experience/projects
✓ Experience subheading order: Job Title (bold, arg1) then Company (italic, arg3) — NOT company first
✓ ALL experience bullets present — do not cap; if source has 6, output 6
✓ ALL projects have Technologies bullet as last item (if present in source)
✓ ALL projects have GitHub link in heading (if present in source)
✓ ALL skills categories present
✓ ALL PROJECTS present (count them in the source and match that count)
✓ LEADERSHIP section is present if source has it — NEVER drop Leadership & Activities
✓ Compressed to fit close to 1 page (but did NOT remove projects or sections to achieve this)
✓ SECTION ORDER (experienced): Experience → Skills → Projects → Education → Leadership
  CHECK: Does Experience come BEFORE Education? If not, fix it now.
✓ NO Contact/Personal Info section in the body — contact info is in the header only
✓ NO Coursework section (experienced candidates do not list coursework)

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
    """Call NVIDIA NIM for LaTeX generation (non-streaming)."""
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
    }
    # Non-streaming: avoids SSE JSON parsing issues with LaTeX backslashes
    response = requests.post(NVIDIA_URL, headers=headers, json=payload,
                             timeout=GENERATION_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


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


def _build_projects_latex(content: str) -> str:
    """
    Pre-build the LaTeX for the Projects section in Python.
    Preserves exact names, all bullets, Technologies lines, and correct order.
    """
    projects = _parse_projects(content)
    if not projects:
        return ""

    latex_lines = []
    for proj in projects:
        # Build heading with optional GitHub link
        name_esc = proj['name'].replace('&', r'\&').replace('%', r'\%')
        if proj['github_suffix']:
            heading = (
                f"\\textbf{{{name_esc}}} "
                r"\hfill \href{https://github.com/NikunjS91}{GitHub}"
            )
        else:
            heading = f"\\textbf{{{name_esc}}}"
        latex_lines.append(heading)

        # Build bullets (skip Technologies line — we add it last, formatted)
        raw_bullets = [
            l.strip() for l in proj['raw_block'].splitlines()
            if l.strip().startswith(('•', '-', '*', '·'))
            and 'technologies' not in l.lower()
        ]
        latex_lines.append(r"\begin{itemize}")
        for bullet in raw_bullets:
            # Strip the bullet character
            text = _strip_bullet(bullet).replace('&', r'\&').replace('%', r'\%').replace('#', r'\#')
            latex_lines.append(f"\\item {text}")

        # Add Technologies line as last bullet if it exists
        if proj['has_technologies'] and proj['tech_line']:
            tech_content = proj['tech_line'].replace('Technologies:', '').strip()
            tech_content = tech_content.replace('&', r'\&').replace('%', r'\%')
            latex_lines.append(f"\\item \\textbf{{Technologies:}} {tech_content}")

        latex_lines.append(r"\end{itemize}")

    return '\n'.join(latex_lines)


def _replace_latex_section(latex: str, section_name: str, new_content: str) -> str:
    """
    Replace the body of a named \\resumesection in the generated LaTeX with new_content.
    Matches from \\resumesection{Name} to the next \\resumesection or \\end{document}.
    """
    import re as _re
    pattern = (
        r'(\\resumesection\{' + _re.escape(section_name) + r'[^}]*\})'
        r'(.*?)'
        r'(?=(\\resumesection|\\end\{document\}))'
    )
    # Use a lambda to avoid regex escape issues with LaTeX backslashes in new_content
    result = _re.sub(pattern, lambda m: m.group(1) + '\n' + new_content + '\n', latex, flags=_re.DOTALL)
    if result == latex:
        logger.warning(f"_replace_latex_section: section '{section_name}' not found in output")
    return result


def _remove_coursework_section(latex: str) -> str:
    """Remove a standalone \\resumesection{Relevant Coursework} block from LaTeX."""
    import re as _re
    pattern = (
        r'\\resumesection\{Relevant Coursework[^}]*\}'
        r'.*?'
        r'(?=(\\resumesection|\\end\{document\}))'
    )
    return _re.sub(pattern, '', latex, flags=_re.DOTALL)


def post_process_latex(latex: str, sections: list, candidate_type: str) -> str:
    """
    After LLM generation: replace Projects and Leadership sections with
    Python-built versions (guaranteed correct names, all bullets, Technologies lines).
    Also removes Coursework section for experienced candidates.
    """
    # Fix Projects (BUG-009, BUG-012, BUG-018, BUG-019)
    projects_section = next(
        (s for s in sections if s.get('section_type') == 'projects'), None
    )
    if projects_section:
        projects_content = projects_section.get(
            'tailored_text', projects_section.get('content_text', '')
        ).strip()
        if projects_content:
            projects_latex = _build_projects_latex(projects_content)
            latex = _replace_latex_section(latex, 'Projects', projects_latex)
            logger.info("Post-processed: replaced Projects section with Python-built version")

    # Fix Leadership (BUG-013)
    leadership_section = next(
        (s for s in sections if s.get('section_type') == 'leadership'), None
    )
    if leadership_section:
        leadership_content = leadership_section.get(
            'tailored_text', leadership_section.get('content_text', '')
        ).strip()
        if leadership_content:
            # Only replace if leadership section exists in LLM output; if missing, append it
            import re as _re
            if _re.search(r'\\resumesection\{Leadership', latex):
                leadership_latex = _build_leadership_latex(leadership_content)
                latex = _replace_latex_section(latex, r'Leadership \& Activities', leadership_latex)
            else:
                # Append before \end{document}
                leadership_latex = _build_leadership_latex(leadership_content)
                latex = latex.replace(
                    r'\end{document}',
                    leadership_latex + '\n' + r'\end{document}'
                )
            logger.info("Post-processed: replaced/appended Leadership section")

    # Fix Coursework for experienced candidates (BUG-011)
    if candidate_type == 'experienced':
        latex = _remove_coursework_section(latex)
        logger.info("Post-processed: removed Coursework section (experienced candidate)")

    return latex


def _build_leadership_latex(content: str) -> str:
    """
    Pre-build the LaTeX for the Leadership & Activities section in Python.
    This bypasses the LLM entirely for this block — guaranteeing it is never dropped.
    Parses entries that look like: "Role, Title  Dates\nDescription text"
    """
    import re as _re
    lines = [l for l in content.splitlines() if l.strip()]
    if not lines:
        return ""

    latex_lines = [r"\resumesection{Leadership \& Activities}"]
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Detect a heading line: contains a year or date range
        has_date = bool(_re.search(r'\b(20\d\d|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec|Present)\b', line))
        if has_date:
            # Try to split "Title  Date" — last occurrence of a date pattern
            date_match = _re.search(
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4}|'
                r'\d{4})\s*[–\-]\s*'
                r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4}|Present|\d{4})',
                line
            )
            if date_match:
                role = line[:date_match.start()].strip()
                dates = date_match.group(0).strip()
            else:
                role = line
                dates = ""
            # Next line(s) until blank or another heading = description
            desc_lines = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                next_has_date = bool(_re.search(
                    r'\b(20\d\d|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Present)\b',
                    next_line
                ))
                if next_has_date and i < len(lines) - 1:
                    break
                desc_lines.append(next_line)
                i += 1
            # Escape ampersands in role/desc for LaTeX
            role_esc = role.replace('&', r'\&')
            dates_esc = dates.replace('–', '--')
            latex_lines.append(f"\\resumesubheading{{{role_esc}}}{{{dates_esc}}}{{}}{{}}")
            if desc_lines:
                latex_lines.append(r"\begin{itemize}")
                for d in desc_lines:
                    if d:
                        d_esc = d.replace('&', r'\&').replace('%', r'\%')
                        latex_lines.append(f"\\item {d_esc}")
                latex_lines.append(r"\end{itemize}")
        else:
            i += 1

    return '\n'.join(latex_lines)


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
        is_tailored=is_tailored,
        candidate_type=candidate_type
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

    # NOTE: post_process_latex is intentionally NOT called here.
    # It runs in export.py AFTER Stage 2 review, so Stage 2 cannot undo it.

    # Validate the template placeholders were filled (not left as LATEX_*)
    unfilled = [p for p in ["LATEX_FULL_NAME", "LATEX_EMAIL", "LATEX_EDUCATION_BLOCK"]
                if p in latex]
    if unfilled:
        logger.warning(f"Stage 1: {len(unfilled)} unfilled placeholder(s): {unfilled}")

    logger.info(f"Stage 1 complete: {len(latex)} chars generated")
    return latex
