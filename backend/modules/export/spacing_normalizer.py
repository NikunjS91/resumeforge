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

    # 0 — Keep 11pt font; only downsize if LLM explicitly chose larger
    latex = re.sub(r'\\documentclass\[1[2-9]pt\]', r'\\documentclass[11pt]', latex)

    # 1 — Tighten linespread to 0.88 (readable but compact — per resume_rules.py)
    latex = re.sub(r'\\linespread\{[0-9.]+\}', r'\\linespread{0.88}', latex)
    latex = re.sub(r'\\renewcommand\{\\baselinestretch\}\{[0-9.]+\}',
                   r'\\renewcommand{\\baselinestretch}{0.88}', latex)

    # 2 — Cap large vspace values at 4pt; preserve small ones for section breathing room
    def _cap_vspace(m):
        val = m.group(1).strip()
        # Keep negative vspace and already-small values unchanged
        if val.startswith('-'):
            return m.group(0)
        try:
            num = float(re.sub(r'[a-z]+', '', val))
            unit = re.sub(r'[0-9.\-]', '', val) or 'pt'
            # Convert to pt for comparison (rough: 1em≈10pt, 1ex≈5pt, 1mm≈2.8pt)
            conv = {'pt': 1, 'em': 10, 'ex': 5, 'mm': 2.8, 'cm': 28, 'in': 72}
            pt_val = num * conv.get(unit, 1)
            if pt_val > 4:
                return r'\vspace{3pt}'
        except (ValueError, AttributeError):
            pass
        return m.group(0)

    latex = re.sub(r'\\vspace\{([^}]+)\}', _cap_vspace, latex)

    # 3 — Tighten geometry margins (balanced: 0.35in top/bottom per resume_rules.py spirit)
    latex = re.sub(
        r'\\usepackage\[[^\]]*geometry[^\]]*\]\{geometry\}',
        r'\\usepackage[top=0.35in,bottom=0.35in,left=0.4in,right=0.4in]{geometry}',
        latex
    )
    latex = re.sub(
        r'\\usepackage\[margin=[^\]]+\]\{geometry\}',
        r'\\usepackage[top=0.35in,bottom=0.35in,left=0.4in,right=0.4in]{geometry}',
        latex
    )
    latex = re.sub(r'bottom=0\.[4-9]in', 'bottom=0.35in', latex)
    latex = re.sub(r'top=0\.[4-9]in', 'top=0.35in', latex)

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

    # 6 — (removed \small — it compounds font compression and hurts readability)

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

    # 9 — Cap spacing after hrule at 1pt (keep a tiny gap for readability)
    latex = re.sub(r'\\hrule\s*\\vspace\{[^}]+\}', r'\\hrule\\vspace{1pt}', latex)

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
