"""
Resume rules injected into every LLM prompt.
Based on industry best practices for ATS-optimized resumes.
"""

UNIVERSAL_RULES = """
UNIVERSAL RESUME RULES (NON-NEGOTIABLE):
1. ONE PAGE ONLY — fit everything on exactly one page
2. Reverse chronological order — most recent experience/education first
3. Every bullet point MUST start with a strong action verb (Led, Built, Architected, Deployed, Reduced, Increased, Designed, Implemented, Optimized, Managed, Spearheaded, Delivered)
4. Quantify every bullet — include at least one number, percentage, or metric per bullet
5. No personal pronouns (never use I, me, my, we, our)
6. No "References available upon request"
7. No photos, graphics, or decorative elements — ATS-safe only
8. Mirror job description keywords EXACTLY — use their exact phrasing
9. Never invent, exaggerate, or fabricate metrics or experiences — 100% truthful
10. Contact info (name, email, phone, LinkedIn) ONLY in the header — never in body
"""

EXPERIENCED_RULES = """
RULES FOR EXPERIENCED CANDIDATES (1+ years work experience):
1. Professional Experience section comes BEFORE Education
2. No "Objective" statement — omit it entirely
3. Education section goes at the BOTTOM with minimal detail (degree, school, year, GPA only)
4. Focus on IMPACT and ROI — not duties or responsibilities
5. Use the formula: Action Verb + What You Did + Measurable Result
   - BAD: "Managed infrastructure"
   - GOOD: "Architected AWS infrastructure serving 10K+ users, reducing operational costs by 35%"
6. Skills grouped by category: Cloud & AWS, DevOps & CI/CD, Backend, Databases, etc.
7. Current/most recent role: 5-6 bullets. Older roles: 3-4 bullets.
"""

FRESHER_RULES = """
RULES FOR FRESHERS (0-1 years experience, students):
1. Education section comes FIRST with full detail
2. Include GPA if 3.5 or higher
3. Include relevant coursework (4-6 courses max)
4. Projects section is equally important as experience — treat each project like a job
5. For each project: what you built, technologies used, measurable outcome
6. Leadership/Activities section demonstrates teamwork and initiative
7. Skills section emphasizes tools, languages, and certifications mastered
"""

FORMATTING_RULES = """
LATEX FORMATTING RULES:
1. Document class: article, 10pt, letterpaper
2. Margins: top=0.4in, bottom=0.4in, left=0.5in, right=0.5in

CRITICAL: You MUST fit everything on ONE PAGE.
If content is too long:
- Reduce bullets per section (max 4 per role, max 3 per project)
- Use tighter vspace: \\vspace{1pt} between sections
- Reduce section spacing: spaceBefore=0, spaceAfter=0
- Skills table: reduce row spacing to [0.5pt]
- Use \\small font size (9pt) for body if needed
- Remove oldest/least relevant bullets first
NEVER add a second page — truncate content if necessary

3. Name: \\Huge\\textbf, centered, color #1a1a2e
4. Section headers: \\large\\textbf\\uppercase with \\hrule below, color #16213e
5. Body text: 10pt regular, linespread 0.88
6. Bullets: leftmargin=0.15in, nosep, itemsep=0pt (ultra compact)
7. Skills: tabular format with @{}p{1.45in}p{5.25in}@{} column widths
8. Dates: always right-aligned using \\hfill on same line as company/role
9. Technologies line in projects: \\textbf{Technologies:} inside itemize, NOT a new section
10. Special characters MUST be escaped: & → \\&, % → \\%, $ → \\$, # → \\#, _ → \\_, { → \\{, } → \\}

CRITICAL PDFLATEX COMPATIBILITY:
- DO NOT use \\usepackage{fontspec} — it requires XeLaTeX/LuaLaTeX
- DO NOT use \\setmainfont or \\setsansfont
- Use only pdflatex-compatible packages: geometry, xcolor, enumitem, hyperref
- For colors use \\definecolor{namecolor}{HTML}{1a1a2e} format
- Do NOT use # for colors directly in \\textcolor — define them first
"""

SECTION_ORDER_EXPERIENCED = [
    "contact",      # Header with name and contact info
    "experience",   # Professional Experience (most important)
    "skills",       # Technical Skills (tabular)
    "projects",     # Projects
    "education",    # Education (bottom)
    "leadership",   # Leadership & Activities (if present)
]

SECTION_ORDER_FRESHER = [
    "contact",      # Header with name and contact info
    "education",    # Education (most important for freshers)
    "skills",       # Technical Skills
    "projects",     # Projects (treated like experience)
    "experience",   # Any internships/part-time
    "leadership",   # Leadership & Activities
]

STAGE_1_SYSTEM_PROMPT = """You are an expert resume writer and LaTeX specialist. 
Your job is to generate a complete, professional, ATS-optimized LaTeX resume.
You have deep knowledge of what recruiters look for and how ATS systems work.
You produce clean, compilable LaTeX code that renders to a beautiful 1-page resume.

CRITICAL CONSTRAINT: The output MUST compile to exactly ONE PAGE.
Aggressively cut content to fit. Fewer bullets is better than overflow."""

STAGE_2_SYSTEM_PROMPT = """You are a senior resume reviewer and LaTeX expert.
Your job is to review a generated LaTeX resume and fix any issues.
You check for rule compliance, LaTeX syntax errors, content quality, and formatting.
You return the corrected, improved LaTeX code ready for compilation."""


# ─── Template Definitions ─────────────────────────────────────────────────────

TEMPLATES = {
    "classic": {
        "name": "Classic",
        "description": "Dark navy header, tabular skills. Best for Tech/Engineering.",
        "file": "templates/professional.tex",
        "style_rules": """
STYLE: Classic Professional
- Use dark navy color (#1a1a2e) for name and section headers
- Section headers: \\large\\textbf\\uppercase with \\hrule below
- Skills in tabular format with bold category labels
- Name in \\Huge\\textbf centered
- Use \\definecolor for all colors
"""
    },
    "minimal": {
        "name": "Minimal",
        "description": "Clean, no colors, maximum ATS safety. Best for Finance/Corporate.",
        "file": "templates/minimal.tex",
        "style_rules": """
STYLE: Minimal Clean
- NO colors — black text only throughout
- Section headers: plain \\large\\textbf with thin hrule
- Name in \\LARGE\\textbf centered
- Clean bullet points, maximum whitespace
- ATS-safe: no decorative elements
"""
    },
    "modern": {
        "name": "Modern",
        "description": "Blue accent bar, colored bullets. Best for Startups/Creative roles.",
        "file": "templates/modern.tex",
        "style_rules": """
STYLE: Modern with Accent
- Use blue accent color (#2563eb) for section decorators and bullets
- Section headers: left accent rule + bold text
- Name in \\Huge\\textbf, subtitle in gray
- Colored bullet points (\\color{accentcolor}\\textbullet)
- Experience section comes FIRST (before education)
"""
    }
}

DEFAULT_TEMPLATE = "classic"
