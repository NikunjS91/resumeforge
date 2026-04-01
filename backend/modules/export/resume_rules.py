"""
Resume rules injected into every LLM prompt.
Based on industry best practices for ATS-optimized resumes.
"""

UNIVERSAL_RULES = """
UNIVERSAL RESUME RULES (NON-NEGOTIABLE):

CONTENT INTEGRITY (MOST CRITICAL):
1. ZERO HALLUCINATION — Never invent, fabricate, or estimate any metric, number, percentage,
   or achievement. If a number does not appear verbatim in the source data, DO NOT include it.
   - WRONG: "Reduced deployment time by 40%" (if source says nothing about deployment time)
   - RIGHT: "Reduced deployment time" (describe without fabricating a number)
   - WRONG: "Achieved 25% increase in sales" (invented)
   - RIGHT: "Reduced manual work by 40%" (if source says exactly this)
2. PRESERVE EXACT NUMBERS — When source data contains a metric, copy it EXACTLY:
   - If source says "40%", write "40%" — not "approximately 40%" or "~35%"
   - If source says "GPA: 3.84", write "3.84" — never round to 3.5 or 3.8
   - If source says "10K+ users", write "10K+ users" — not "thousands of users"
3. PRESERVE ALL CONTACT DATA — Copy name, email, phone, LinkedIn, GitHub EXACTLY from source:
   - If source has a real LinkedIn URL, use it
   - If source has placeholder text like "LinkedIn URL", flag it but still copy it
   - Never replace real URLs with placeholders

STRUCTURE RULES:
4. ONE PAGE ONLY — Fit everything on exactly one page using spacing, not content removal
5. Reverse chronological order — most recent experience/education first
6. Every bullet MUST start with a strong action verb (Led, Built, Deployed, Architected,
   Reduced, Increased, Designed, Implemented, Optimized, Managed, Delivered)
7. No personal pronouns (never use I, me, my, we, our)

HEADER vs BODY:
8. NEVER generate a CONTACT or PERSONAL INFORMATION section in the resume body.
   Contact info (name, email, phone, LinkedIn, GitHub) goes ONLY in the LaTeX header
   \begin{center} block. If source data has a "Contact" section, extract the values
   for the header — do NOT render it as a body section with a section heading.

CONTENT PRESERVATION:
9. Include ALL sections from source — never drop entire sections
10. Include ALL skills categories — reduce bullets per category if needed but keep all categories.
    CRITICAL: Only include skill categories explicitly listed in the source skills section.
    NEVER add skill categories inferred from experience/project bullets.
11. Include ALL projects — reduce bullets per project if needed but keep all projects
12. If content does not fit on one page, reduce SPACING and BULLETS per item — not whole sections
13. Mirror job description keywords EXACTLY where present in source data
14. Leadership & Activities section is MANDATORY if it exists in the source — never remove it
"""

EXPERIENCED_RULES = """
RULES FOR EXPERIENCED CANDIDATES (1+ years work experience):
1. MANDATORY SECTION ORDER: Header → Experience → Skills → Projects → Education → Leadership
   Education MUST come AFTER Experience. No exceptions.
2. No "Objective" statement — omit it entirely
3. Education section goes at the BOTTOM — include degree, school, GPA (EXACT value), graduation date
4. Focus on IMPACT and ROI — use the formula: Action Verb + What + Measurable Result (if in source)
5. Current/most recent role: 4-5 bullets max. Older roles: 2-3 bullets max.
6. Skills: keep ALL categories from source — reduce rows per category before dropping categories
7. Projects: keep ALL projects from source — reduce to 3 bullets each if space is tight
8. Do NOT include a Relevant Coursework section. If the source has one, discard it entirely —
   experienced candidates do not list coursework on their resume.

ONE-PAGE FITTING STRATEGY (use in this order, stop when it fits):
   Step 1: Reduce line spacing (use \\vspace{1pt} between sections)
   Step 2: Reduce bullets per role (current role: 4 max, older: 2 max)
   Step 3: Reduce bullets per project (3 max each)
   Step 4: Shorten individual bullet text (keep all key facts, remove filler words)
   NEVER: Drop entire sections or entire projects to fit the page
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
7. Skills: tabular format with @{}p{1.7in}p{5.0in}@{} column widths
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
    "leadership",   # Leadership & Activities (MANDATORY if present in source — never drop)
]

SECTION_ORDER_FRESHER = [
    "contact",      # Header with name and contact info
    "education",    # Education (most important for freshers)
    "skills",       # Technical Skills
    "projects",     # Projects (treated like experience)
    "experience",   # Any internships/part-time
    "leadership",   # Leadership & Activities
]

STAGE_1_SYSTEM_PROMPT = """You are a precise LaTeX resume generator with one absolute rule:
ACCURACY FIRST. You never invent, fabricate, or modify any data from the source.

Your job in order of priority:
1. Copy all numbers, URLs, and metrics EXACTLY as they appear in source data
2. Include ALL sections, skills categories, and projects from source data
3. Format professionally in LaTeX
4. Fit on exactly 1 page by adjusting spacing and bullet count — never by removing sections

If you are ever unsure whether a metric is real or invented: OMIT the metric.
Write the action without a number rather than risk fabrication.
"""

STAGE_2_SYSTEM_PROMPT = """You are a senior resume reviewer and LaTeX debugger.

Your PRIMARY job is catching fabricated data. Check every number and metric in the
LaTeX against the original source data provided. If ANY metric appears that was NOT
in the source data, DELETE it — replace with the action without the number.

Your SECONDARY job is completeness. Verify all sections, all skills categories,
and all projects from the source are present. If any are missing, add them back.

Your TERTIARY job is formatting. Fix LaTeX syntax errors, ensure 1-page fit,
fix special character escaping.

Return the corrected complete LaTeX. Nothing else.
"""


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
- Add \\vspace{6pt} BEFORE each section header for clear separation
- Add \\vspace{3pt} AFTER each section header
- Use \\vspace{2pt} between job/project entries
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
- Add \\vspace{6pt} BEFORE each section header for clear separation
- Add \\vspace{3pt} AFTER each section header
- Use \\vspace{2pt} between job entries
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
- Add \\vspace{6pt} BEFORE each section header for clear separation
- Add \\vspace{3pt} AFTER each section header
- Use \\vspace{2pt} between job/project entries
"""
    }
}

DEFAULT_TEMPLATE = "classic"
