"""
Normalizes LaTeX spacing to force 1-page output.
Applied AFTER Stage 2 review, BEFORE pdflatex compilation.
Does NOT remove any content — only adjusts spacing values.
"""
import re
import logging

logger = logging.getLogger(__name__)


def normalize_spacing(latex: str) -> str:
    """
    Reduce all spacing values to force 1-page output.
    Only modifies spacing — never removes content.
    """
    original_lines = latex.count('\n')

    # 0 — Force smaller font size (10pt instead of 11pt)
    latex = re.sub(r'\\documentclass\[11pt\]', r'\\documentclass[10pt]', latex)

    # 1 — Tighten linespread to 0.78 (more aggressive)
    latex = re.sub(r'\\linespread\{[0-9.]+\}', r'\\linespread{0.78}', latex)
    latex = re.sub(r'\\renewcommand\{\\baselinestretch\}\{[0-9.]+\}',
                   r'\\renewcommand{\\baselinestretch}{0.78}', latex)

    # 2 — Reduce all vspace to 0pt (most aggressive)
    latex = re.sub(r'\\vspace\{[^}]+\}', r'\\vspace{0pt}', latex)

    # 3 — Tighten geometry margins (more aggressive: 0.25in top/bottom)
    latex = re.sub(
        r'\\usepackage\[[^\]]*geometry[^\]]*\]\{geometry\}',
        r'\\usepackage[top=0.25in,bottom=0.25in,left=0.4in,right=0.4in]{geometry}',
        latex
    )
    latex = re.sub(
        r'\\usepackage\[margin=[^\]]+\]\{geometry\}',
        r'\\usepackage[top=0.25in,bottom=0.25in,left=0.4in,right=0.4in]{geometry}',
        latex
    )
    latex = re.sub(r'bottom=0\.[3-9]in', 'bottom=0.25in', latex)
    latex = re.sub(r'top=0\.[3-9]in', 'top=0.25in', latex)

    # 4 — Reduce spaceBefore/spaceAfter in ParagraphStyle (if present)
    latex = re.sub(r'spaceAfter=\d+', 'spaceAfter=0', latex)
    latex = re.sub(r'spaceBefore=\d+', 'spaceBefore=0', latex)

    # 5 — Tighten itemize spacing via inline options
    latex = re.sub(
        r'\\setlist\[itemize\]\{([^}]*)\}',
        lambda m: re.sub(r'topsep=\d+pt', 'topsep=0pt',
                   re.sub(r'itemsep=\d+pt', 'itemsep=0pt',
                   re.sub(r'parsep=\d+pt', 'parsep=0pt', m.group(0)))),
        latex
    )

    # 6 — Add \small after \begin{document} to shrink body text
    if r'\begin{document}' in latex and r'\small' not in latex:
        latex = latex.replace(r'\begin{document}', r'\begin{document}' + '\n\\small')

    # 7 — Reduce parskip globally (add after geometry if not present)
    if r'\setlength{\parskip}' not in latex:
        latex = re.sub(
            r'(\\usepackage\[[^\]]*\]\{geometry\})',
            r'\1\n\\setlength{\\parskip}{0pt}',
            latex
        )

    # 8 — Reduce tabcolsep for tighter tables
    if r'\setlength{\tabcolsep}' not in latex:
        latex = re.sub(
            r'(\\begin\{document\})',
            r'\\setlength{\\tabcolsep}{4pt}\n\1',
            latex
        )

    # 9 — Remove any large spacing after hrule
    latex = re.sub(r'\\hrule\s*\\vspace\{[^}]+\}', r'\\hrule', latex)

    logger.info(f"Spacing normalized: {original_lines} lines → {latex.count(chr(10))} lines")
    return latex


def count_expected_pages(latex: str) -> str:
    """
    Rough estimate of page count based on content length.
    Just for logging — not used for decisions.
    """
    # Count bullets and lines as a rough proxy
    bullet_count = latex.count('\\item ')
    section_count = latex.count('\\resumesection')
    return f"~{bullet_count} bullets, {section_count} sections"
