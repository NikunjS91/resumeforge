"""
Validates resume source data before passing to LLM.
Detects placeholder URLs, suspicious GPA, missing sections, thin content.
Injects warnings into the LLM prompt so it knows to be careful.
"""
import re
import logging

logger = logging.getLogger(__name__)


def validate_sections(sections: list) -> dict:
    """
    Check source data quality before LLM generation.
    Returns warnings that get injected into the prompt.
    """
    warnings = []
    all_text = ' '.join(s.get('content_text', '') for s in sections)

    # Check 1 — Placeholder URLs
    if 'LinkedIn URL' in all_text or 'GitHub URL' in all_text:
        warnings.append(
            "WARNING: Contact section contains placeholder text ('LinkedIn URL' or 'GitHub URL'). "
            "Do NOT use these as real URLs. Extract only real URLs that begin with https://."
        )

    # Check 2 — GPA accuracy AND metrics preservation
    gpa_matches = re.findall(r'GPA[:\s]+(\d+\.\d+)', all_text)
    for gpa in gpa_matches:
        if float(gpa) < 3.0:
            warnings.append(f"WARNING: GPA value {gpa} seems low — verify it is correct.")
        warnings.append(f"NOTE: GPA found in source is {gpa} — use EXACTLY this value, do not round.")

    # Check for real metrics that MUST be preserved
    real_metrics = re.findall(r'(\d+(?:\.\d+)?%)', all_text)
    if real_metrics:
        metrics_list = list(set(real_metrics))[:10]  # Dedupe, limit to 10
        warnings.append(
            f"CRITICAL METRICS TO PRESERVE: Source contains these exact percentages: {', '.join(metrics_list)}. "
            f"You MUST include these metrics in the output. Do NOT remove them to save space."
        )

    # Check 3 — Skills content
    skills_sections = [s for s in sections if s.get('section_type') == 'skills']
    total_skill_chars = sum(len(s.get('content_text', '')) for s in skills_sections)
    if total_skill_chars < 300:
        warnings.append(
            "WARNING: Skills section is thin (< 300 chars). "
            "Include ALL skill categories found — do not reduce further."
        )

    # Check 4 — Missing contact fields
    contact = next((s for s in sections if s.get('section_type') == 'contact'), None)
    if contact:
        content = contact.get('content_text', '')
        if not re.search(r'[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}', content):
            warnings.append("WARNING: No email found in contact section.")
        if not re.search(r'https?://|linkedin\.com|github\.com', content):
            warnings.append(
                "WARNING: No real LinkedIn or GitHub URL found in contact. "
                "Do not invent URLs — leave them blank or use the exact text from source."
            )

    # Check 5 — Project count with explicit names
    projects = [s for s in sections if s.get('section_type') == 'projects']
    if len(projects) == 0:
        warnings.append(
            "WARNING: No projects section found. "
            "Look for project data in other sections labeled 'Academic Projects' or similar."
        )
    else:
        # Count known projects explicitly mentioned in source
        project_text = ' '.join(s.get('content_text', '') for s in projects)

        # List of actual projects we know exist
        actual_projects = []
        if 'TrueSight' in project_text or 'Deepfake' in project_text:
            actual_projects.append('TrueSight')
        if 'Sentiment' in project_text:
            actual_projects.append('Sentiment Analysis')
        if 'Job Application' in project_text or 'Tracker' in project_text:
            actual_projects.append('Job Application Tracker')
        if 'Churn' in project_text:
            actual_projects.append('Churn Prediction')

        if len(actual_projects) >= 2:
            project_list = ', '.join(actual_projects)
            warnings.append(
                f"CRITICAL: Source contains EXACTLY {len(actual_projects)} projects: {project_list}. "
                f"Include ALL {len(actual_projects)} of these projects EXACTLY as named. "
                f"DO NOT invent fake projects. DO NOT add 'Project 1', 'Project 2', etc."
            )

    return {
        'warnings': warnings,
        'has_issues': len(warnings) > 0,
        'warning_text': '\n'.join(warnings) if warnings else ''
    }
