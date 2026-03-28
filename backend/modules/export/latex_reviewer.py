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
REVIEW CHECKLIST — Fix every issue found:

ANTI-HALLUCINATION CHECKS (HIGHEST PRIORITY):
□ Are ALL numbers and percentages present verbatim in the original source data?
  - If ANY metric was not in the source data, REMOVE it immediately
  - Replace with action-only bullet: "Led migration to AWS" not "Led migration, reducing costs by 35%"
□ Is the GPA EXACTLY as it appears in the source? (e.g., 3.84 not 3.5 or 3.8)
□ Are LinkedIn and GitHub URLs copied exactly from source? (real URLs, not placeholders)
□ Are all company names, job titles, and dates copied exactly from source?

CONTENT COMPLETENESS CHECKS:
□ Are ALL skills categories from the source present? (none dropped)
□ Are ALL projects from the source present? (none dropped)
□ Are ALL sections present? (Education, Skills, Experience, Projects, Leadership if in source)
□ Is the experience section present with the correct company name and role title?

LATEX SYNTAX CHECKS:
□ Does \\documentclass appear at the start?
□ Does \\end{document} appear at the end?
□ Are all \\begin{} matched with \\end{}?
□ Are all special characters escaped? (& → \\&, % → \\%, $ → \\$, # → \\#, _ → \\_)
□ Are all braces { } balanced?

FORMATTING CHECKS:
□ Does the resume fit on ONE PAGE?
□ Is the name in \\Huge or \\LARGE\\textbf centered?
□ Are section headers using \\large\\textbf with \\hrule?
□ Are skills in tabular format (not bullet list)?
□ Are dates right-aligned using \\hfill?

IF ANYTHING IS WRONG: Fix it and return the corrected LaTeX.
IF HALLUCINATED METRICS FOUND: Remove them — do not keep or replace with other invented numbers.
"""


def build_review_prompt(latex_code: str, original_data: str = "") -> str:
    """Build the Stage 2 review prompt with source data for fact-checking."""

    source_section = ""
    if original_data:
        source_section = f"""
════════════════════════════════════════════
ORIGINAL SOURCE DATA (fact-check against this)
════════════════════════════════════════════
{original_data[:3000]}
════════════════════════════════════════════
"""

    return f"""Review the LaTeX resume below. Fix every issue.

{source_section}

WHAT TO CHECK AND FIX:

PRIORITY 1 — FABRICATED DATA (most critical):
- Compare every number/percentage in the LaTeX against the source data above
- If a metric appears in LaTeX but NOT in source data: DELETE it from the bullet
- Example: If LaTeX has "25% increase in sales" but source never mentions this → remove it
- Example: If source has "40% reduction" but LaTeX changed it to "35%" → fix to 40%
- GPA: must match source exactly (e.g., 3.84 not 3.5)
- URLs: must be copied from source (real URLs or placeholder text — not invented)

PRIORITY 2 — MISSING CONTENT:
- All sections present? (Education, Skills, Experience, Projects, Leadership)
- All skills categories from source present?
- All projects from source present?
- If anything is missing: add it back, reducing spacing to fit 1 page

PRIORITY 3 — LATEX SYNTAX:
- All special chars escaped: & → \\& % → \\% $ → \\$ # → \\# _ → \\_
- All \\begin{{}} matched with \\end{{}}
- \\documentclass at start, \\end{{document}} at end

PRIORITY 4 — ONE PAGE (critical):
- Must fit on exactly 1 page
- Check total bullet count: if more than 18 bullets total, reduce
  Current/main role: max 4 bullets
  Older roles: max 2 bullets
  Each project: max 3 bullets
  Leadership entries: max 2 bullets each
- After reducing bullets, check \\vspace values — all should be \\vspace{{1pt}}
- Check \\linespread — should be 0.82 or less
- If still too long: shorten individual bullet text (remove filler words)
- NEVER remove whole sections or whole projects

LATEX CODE TO REVIEW:
{latex_code}

Return ONLY the corrected complete LaTeX code.
Start with \\documentclass — end with \\end{{document}}.
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
