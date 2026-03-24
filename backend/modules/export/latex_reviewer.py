"""
Stage 2: LLM reviews the generated LaTeX and fixes issues.
Checks rule compliance, LaTeX syntax, content quality.
"""
import os
import re
import json
import logging
import requests
from .resume_rules import (
    UNIVERSAL_RULES, FORMATTING_RULES, STAGE_2_SYSTEM_PROMPT
)
from .latex_generator import call_ollama, call_nvidia, extract_latex

logger = logging.getLogger(__name__)

REVIEW_TIMEOUT = 180  # 3 minutes


REVIEW_CHECKLIST = """
REVIEW CHECKLIST — Check each item and fix if needed:

CONTENT CHECKS:
□ Does every bullet start with a strong action verb?
□ Does every bullet have at least one metric/number?
□ Are all special characters escaped? (& → \\&, % → \\%, $ → \\$)
□ Is contact info (email, phone, LinkedIn) ONLY in the header?
□ Are Technologies lines inside projects in itemize, not as section headers?
□ Is everything on ONE PAGE? (check \\linespread and spacing)

LATEX SYNTAX CHECKS:
□ Does \\documentclass appear at the start?
□ Does \\end{document} appear at the end?
□ Are all \\begin{} matched with \\end{}?
□ Are all braces { } balanced?
□ Is \\usepackage{enumitem} included?
□ Is \\usepackage{xcolor} included?
□ Is \\usepackage{hyperref} included?
□ Is \\usepackage{geometry} included?

FORMATTING CHECKS:
□ Is the name in \\Huge\\textbf and centered?
□ Do section headers use \\large\\textbf\\uppercase with \\hrule?
□ Are skills in tabular format (not bullet list)?
□ Are dates right-aligned using \\hfill?
□ Is line spacing set to 0.88?

QUALITY CHECKS:
□ Is everything truthful and based on the provided data?
□ Are job description keywords from the target role included?
□ Is the content specific enough to pass a recruiter's 6-second scan?
"""


def build_review_prompt(latex_code: str, original_data: str = "") -> str:
    """Build the Stage 2 review prompt."""
    return f"""
You are reviewing a generated LaTeX resume. Your job is to:
1. Check every item in the checklist below
2. Fix ALL issues you find
3. Return ONLY the corrected, complete LaTeX code

{UNIVERSAL_RULES}

{FORMATTING_RULES}

{REVIEW_CHECKLIST}

ORIGINAL RESUME DATA (for reference, to ensure nothing was lost):
{original_data[:2000] if original_data else "Not provided"}

LATEX CODE TO REVIEW:
{latex_code}

CRITICAL INSTRUCTIONS:
- Return ONLY the corrected LaTeX code
- Start with \\documentclass and end with \\end{{document}}
- No explanations, no markdown, no code blocks
- Fix every issue found in the checklist
- Do NOT change factual content — only improve formatting and fix errors
- If the code is already correct, return it unchanged

Return the corrected LaTeX code:
"""


def review_latex_stage2(
    latex_code: str,
    original_data: str = "",
    provider: str = "ollama"
) -> str:
    """
    Stage 2: Review and fix the generated LaTeX.

    Args:
        latex_code: LaTeX from Stage 1
        original_data: Original resume data for reference
        provider: 'ollama' or 'nvidia'

    Returns:
        str: Reviewed and corrected LaTeX code
    """
    prompt = build_review_prompt(latex_code, original_data)

    logger.info(f"Stage 2: Reviewing LaTeX with {provider}...")

    if provider == "nvidia":
        raw = call_nvidia(prompt, STAGE_2_SYSTEM_PROMPT)
    else:
        raw = call_ollama(prompt, STAGE_2_SYSTEM_PROMPT)

    reviewed_latex = extract_latex(raw)

    # Sanity check — if review produced garbage, return original
    if len(reviewed_latex) < 500 or '\\documentclass' not in reviewed_latex:
        logger.warning("Stage 2 review produced invalid output, using Stage 1 result")
        return latex_code

    logger.info(f"Stage 2 complete: {len(reviewed_latex)} chars in reviewed LaTeX")
    return reviewed_latex
