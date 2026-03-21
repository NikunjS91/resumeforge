"""
LaTeX template filler — takes structured resume data and fills the template.
Handles all LaTeX special character escaping.
"""
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path("templates/professional.tex")

# ─── LATEX ESCAPING ──────────────────────────────────────────────────────────

LATEX_ESCAPE_MAP = {
    '&':  r'\&',
    '%':  r'\%',
    '$':  r'\$',
    '#':  r'\#',
    '_':  r'\_',
    '{':  r'\{',
    '}':  r'\}',
    '~':  r'\textasciitilde{}',
    '^':  r'\textasciicircum{}',
    '\\': r'\textbackslash{}',
}

def escape(text: str) -> str:
    """Escape all LaTeX special characters in user content."""
    if not text:
        return ""
    # Process in order to avoid double-escaping
    result = ""
    for char in str(text):
        result += LATEX_ESCAPE_MAP.get(char, char)
    return result


def escape_url(url: str) -> str:
    """URLs don't need standard escaping but need % handled."""
    return url.replace('%', r'\%') if url else ""


# ─── SECTION PARSERS ─────────────────────────────────────────────────────────

def parse_contact(content: str) -> dict:
    """Parse contact section text into structured fields."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    contact = {
        'name': lines[0] if lines else 'Full Name',
        'location': '',
        'phone_raw': '',
        'phone_display': '',
        'email': '',
        'linkedin_url': 'https://linkedin.com',
        'github_url': 'https://github.com',
    }

    full_text = ' '.join(lines)

    # Extract email
    email_match = re.search(r'[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}', full_text)
    if email_match:
        contact['email'] = email_match.group()

    # Extract phone
    phone_match = re.search(r'\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}', full_text)
    if phone_match:
        contact['phone_display'] = phone_match.group()
        contact['phone_raw'] = re.sub(r'[^\d]', '', phone_match.group())

    # Extract LinkedIn
    linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', full_text)
    if linkedin_match:
        contact['linkedin_url'] = 'https://www.' + linkedin_match.group()

    # Extract GitHub
    github_match = re.search(r'github\.com/[\w-]+', full_text)
    if github_match:
        contact['github_url'] = 'https://' + github_match.group()

    # Location — look for "City, ST" pattern
    location_match = re.search(r'([A-Z][a-zA-Z\s]+,\s*[A-Z]{2})', full_text)
    if location_match:
        contact['location'] = location_match.group()

    return contact


def build_education_block(content: str) -> str:
    """Convert education section text to LaTeX."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    blocks = []
    current = []

    for line in lines:
        if any(kw in line.lower() for kw in ['university', 'college', 'institute', 'school']):
            if current:
                blocks.append('\n'.join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append('\n'.join(current))

    latex_blocks = []
    for block in blocks:
        block_lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not block_lines:
            continue
        latex = escape(block_lines[0])  # University name + location
        for bl in block_lines[1:]:
            latex += f'\\\\\n{escape(bl)}'
        latex_blocks.append(latex)

    return '\n\\vspace{2pt}\n'.join(latex_blocks)


def build_skills_rows(content: str) -> str:
    """Convert skills section text to LaTeX tabular rows."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    rows = []

    for line in lines:
        if ':' in line:
            parts = line.split(':', 1)
            label = escape(parts[0].strip())
            skills = escape(parts[1].strip())
            suffix = r'\\[1.5pt]' if line != lines[-1] else r'\\'
            rows.append(f'\\textbf{{{label}}} & {skills} {suffix}')
        elif line:
            rows.append(f'& {escape(line)} \\\\')

    return '\n'.join(rows)


def build_experience_block(content: str) -> str:
    """Convert experience section to LaTeX."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    latex_lines = []
    in_itemize = False

    for line in lines:
        if re.match(r'^[A-Z].*\d{4}', line) and not line.startswith('•'):
            # Looks like a job header
            if in_itemize:
                latex_lines.append('\\end{itemize}')
                in_itemize = False
            # Try to parse: "Role  Company  Location  Dates"
            latex_lines.append(f'\\textbf{{{escape(line)}}}')
        elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
            if not in_itemize:
                latex_lines.append('\\begin{itemize}')
                in_itemize = True
            bullet_text = escape(line.lstrip('•-* ').strip())
            latex_lines.append(f'    \\item {bullet_text}')
        else:
            if in_itemize:
                latex_lines.append('\\end{itemize}')
                in_itemize = False
            latex_lines.append(escape(line) + '\\\\')

    if in_itemize:
        latex_lines.append('\\end{itemize}')

    return '\n'.join(latex_lines)


def build_projects_block(content: str) -> str:
    """Convert projects section to LaTeX."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    latex_lines = []
    in_itemize = False
    first_project = True

    for line in lines:
        is_tech_line = any(line.lower().startswith(p) for p in
                           ['technologies:', 'tech stack:', 'tools:', 'stack:'])
        is_bullet = line.startswith('•') or line.startswith('-') or line.startswith('*')
        is_project_header = (not is_bullet and not is_tech_line
                             and len(line) > 5 and not line[0].isdigit()
                             and not line.startswith('http'))

        if is_project_header and (line.isupper() or 'github' in line.lower()
                                  or any(c.isupper() for c in line[:3])):
            if in_itemize:
                latex_lines.append('\\end{itemize}')
                in_itemize = False
            if not first_project:
                latex_lines.append('\\vspace{2pt}')
            first_project = False
            latex_lines.append(f'\\textbf{{{escape(line)}}}\\\\')
        elif is_tech_line:
            # Bold technologies line inside itemize
            if in_itemize:
                parts = line.split(':', 1)
                tech_text = escape(parts[1].strip()) if len(parts) > 1 else escape(line)
                latex_lines.append(f'    \\item \\textbf{{Technologies:}} {tech_text}')
            else:
                latex_lines.append(escape(line) + '\\\\')
        elif is_bullet:
            if not in_itemize:
                latex_lines.append('\\begin{itemize}')
                in_itemize = True
            bullet_text = escape(line.lstrip('•-* ').strip())
            latex_lines.append(f'    \\item {bullet_text}')
        else:
            if in_itemize:
                latex_lines.append('\\end{itemize}')
                in_itemize = False
            latex_lines.append(escape(line) + '\\\\')

    if in_itemize:
        latex_lines.append('\\end{itemize}')

    return '\n'.join(latex_lines)


def build_leadership_block(content: str) -> str:
    """Convert leadership section to LaTeX."""
    lines = [l.strip() for l in content.strip().split('\n') if l.strip()]
    # Filter out contact-pattern lines (phone, email, linkedin, github)
    contact_patterns = [
        r'[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}',   # email
        r'\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}',  # phone
        r'linkedin\.com',
        r'github\.com',
    ]
    filtered = []
    for line in lines:
        is_contact = any(re.search(p, line) for p in contact_patterns)
        if not is_contact:
            filtered.append(line)

    latex_lines = []
    first = True
    for line in filtered:
        if not first:
            latex_lines.append('\\vspace{2pt}')
        first = False
        latex_lines.append(f'\\textbf{{{escape(line)}}}\\\\')
    return '\n'.join(latex_lines)


# ─── MAIN FILLER ─────────────────────────────────────────────────────────────

def fill_template(sections: list, job_title: str = "", company_name: str = "") -> str:
    """
    Fill the LaTeX template with resume data.

    Args:
        sections: list of dicts with section_type, section_label, content_text, position_index
        job_title: used in PDF metadata
        company_name: used in PDF metadata

    Returns:
        str: complete .tex file content ready for pdflatex
    """
    template = TEMPLATE_PATH.read_text(encoding='utf-8')

    # Sort by position
    sorted_sections = sorted(sections, key=lambda s: s.get('position_index', 0))

    # Deduplicate — keep first of each type (allow multiple experience/projects)
    ALLOW_MULTIPLE = {'experience', 'projects'}
    seen = set()
    deduped = []
    for s in sorted_sections:
        st = s.get('section_type', 'other')
        if st in ALLOW_MULTIPLE:
            deduped.append(s)
        elif st not in seen:
            seen.add(st)
            deduped.append(s)
    sorted_sections = deduped

    # Extract each section
    def get_content(section_type: str) -> str:
        for s in sorted_sections:
            if s.get('section_type') == section_type:
                return s.get('content_text', '')
        return ''

    contact_content  = get_content('contact')
    education_content = get_content('education')
    skills_content   = get_content('skills')
    experience_content = get_content('experience')
    projects_content = get_content('projects')
    leadership_content = get_content('leadership') or get_content('unknown')

    # Parse contact
    contact = parse_contact(contact_content)
    author_name = contact['name']
    title = f"{author_name} - {job_title}" if job_title else author_name

    # Fill template
    filled = template
    filled = filled.replace('LATEX_PDF_TITLE',       escape(title))
    filled = filled.replace('LATEX_AUTHOR_NAME',     escape(author_name))
    filled = filled.replace('LATEX_FULL_NAME',       escape(contact['name']))
    filled = filled.replace('LATEX_LOCATION',        escape(contact['location']))
    filled = filled.replace('LATEX_PHONE_RAW',       contact['phone_raw'])
    filled = filled.replace('LATEX_PHONE_DISPLAY',   escape(contact['phone_display']))
    filled = filled.replace('LATEX_EMAIL',           contact['email'])
    filled = filled.replace('LATEX_LINKEDIN_URL',    escape_url(contact['linkedin_url']))
    filled = filled.replace('LATEX_GITHUB_URL',      escape_url(contact['github_url']))
    filled = filled.replace('LATEX_EDUCATION_BLOCK', build_education_block(education_content))
    filled = filled.replace('LATEX_SKILLS_ROWS',     build_skills_rows(skills_content))
    filled = filled.replace('LATEX_EXPERIENCE_BLOCK', build_experience_block(experience_content))
    filled = filled.replace('LATEX_PROJECTS_BLOCK',  build_projects_block(projects_content))
    filled = filled.replace('LATEX_LEADERSHIP_BLOCK', build_leadership_block(leadership_content))

    return filled
