"""
Runs pdflatex to compile a .tex file into a PDF.
"""
import subprocess
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("data/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Find pdflatex binary
PDFLATEX_PATHS = [
    '/Library/TeX/texbin/pdflatex',
    '/usr/local/bin/pdflatex',
    '/usr/bin/pdflatex',
]

def find_pdflatex() -> str | None:
    """Find pdflatex binary on the system."""
    for path in PDFLATEX_PATHS:
        if Path(path).exists():
            return path
    # Try which
    result = shutil.which('pdflatex')
    return result


def compile_latex(tex_content: str, output_stem: str) -> str:
    """
    Write .tex file and compile to PDF.

    Args:
        tex_content: complete .tex file content
        output_stem: filename stem e.g. "resume_session_5" (no extension)

    Returns:
        str: full path to compiled PDF

    Raises:
        RuntimeError: if pdflatex not found or compilation fails
    """
    pdflatex = find_pdflatex()
    if not pdflatex:
        raise RuntimeError(
            "pdflatex not found. Install with: brew install basictex\n"
            "Then add to PATH: export PATH=$PATH:/Library/TeX/texbin"
        )

    tex_path = EXPORT_DIR / f"{output_stem}.tex"
    pdf_path = EXPORT_DIR / f"{output_stem}.pdf"

    # Write .tex file
    tex_path.write_text(tex_content, encoding='utf-8')
    logger.info(f"Wrote .tex file: {tex_path}")

    # Compile with pdflatex (run twice for correct page refs)
    for run in range(2):
        result = subprocess.run(
            [pdflatex,
             '-interaction=nonstopmode',
             '-output-directory', str(EXPORT_DIR),
             str(tex_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 and run == 1:
            logger.error(f"pdflatex error:\n{result.stdout[-2000:]}")
            raise RuntimeError(f"pdflatex compilation failed. Check .tex syntax.")

    if not pdf_path.exists():
        raise RuntimeError("PDF was not created after compilation.")

    # Clean up auxiliary files
    for ext in ['.aux', '.log', '.out']:
        aux = EXPORT_DIR / f"{output_stem}{ext}"
        if aux.exists():
            aux.unlink()

    logger.info(f"Compiled PDF: {pdf_path} ({pdf_path.stat().st_size} bytes)")
    return str(pdf_path)
