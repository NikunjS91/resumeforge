import os
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    HRFlowable, Table, TableStyle
)
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

EXPORT_DIR = Path("data/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Professional color palette
COLOR_HEADER_BG  = colors.HexColor("#1a1a2e")   # dark navy
COLOR_HEADER_FG  = colors.white
COLOR_ACCENT     = colors.HexColor("#4a90d9")    # professional blue
COLOR_DIVIDER    = colors.HexColor("#cccccc")
COLOR_NOTES_BG   = colors.HexColor("#f0f7ff")   # light blue tint
COLOR_BODY       = colors.HexColor("#333333")
COLOR_LABEL      = colors.HexColor("#1a1a2e")

# Section icons (unicode)
SECTION_ICONS = {
    "contact":    "●",
    "education":  "🎓",
    "skills":     "⚙",
    "experience": "💼",
    "projects":   "🚀",
    "leadership": "★",
    "summary":    "▶",
    "unknown":    "●",
}

# ─── STYLES ──────────────────────────────────────────────────────────────────

def build_styles():
    base = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "NameStyle",
        parent=base["Normal"],
        fontSize=22,
        textColor=COLOR_HEADER_FG,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    contact_style = ParagraphStyle(
        "ContactStyle",
        parent=base["Normal"],
        fontSize=9,
        textColor=COLOR_HEADER_FG,
        fontName="Helvetica",
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    section_label_style = ParagraphStyle(
        "SectionLabel",
        parent=base["Normal"],
        fontSize=11,
        textColor=COLOR_LABEL,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=base["Normal"],
        fontSize=9.5,
        textColor=COLOR_BODY,
        fontName="Helvetica",
        spaceBefore=1,
        spaceAfter=1,
        leading=13,
    )
    bullet_style = ParagraphStyle(
        "BulletStyle",
        parent=base["Normal"],
        fontSize=9.5,
        textColor=COLOR_BODY,
        fontName="Helvetica",
        leftIndent=12,
        spaceBefore=1,
        spaceAfter=1,
        leading=13,
    )
    notes_header_style = ParagraphStyle(
        "NotesHeader",
        parent=base["Normal"],
        fontSize=10,
        textColor=COLOR_ACCENT,
        fontName="Helvetica-Bold",
        spaceBefore=8,
        spaceAfter=3,
    )
    notes_item_style = ParagraphStyle(
        "NotesItem",
        parent=base["Normal"],
        fontSize=9,
        textColor=COLOR_BODY,
        fontName="Helvetica-Oblique",
        leftIndent=10,
        spaceBefore=1,
        spaceAfter=1,
    )

    return {
        "name": name_style,
        "contact": contact_style,
        "section_label": section_label_style,
        "body": body_style,
        "bullet": bullet_style,
        "notes_header": notes_header_style,
        "notes_item": notes_item_style,
    }


# ─── CONTACT PARSER ──────────────────────────────────────────────────────────

def parse_contact(content_text: str) -> dict:
    """Parse contact section into name and details."""
    lines = [l.strip() for l in content_text.strip().split("\n") if l.strip()]
    name = lines[0] if lines else "Resume"
    details = " · ".join(lines[1:]) if len(lines) > 1 else ""
    return {"name": name, "details": details}


# ─── HEADER BUILDER ──────────────────────────────────────────────────────────

def build_header(story: list, styles: dict, contact: dict, job_title: str = "", company_name: str = ""):
    """Build the professional header bar with name and contact info."""
    header_data = [
        [Paragraph(contact["name"], styles["name"])],
    ]
    if contact["details"]:
        header_data.append([Paragraph(contact["details"], styles["contact"])])
    if job_title and company_name:
        target_text = f"Tailored for: {job_title} at {company_name}"
        header_data.append([Paragraph(target_text, styles["contact"])])

    header_table = Table(header_data, colWidths=[7.5 * inch])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), COLOR_HEADER_BG),
        ("TOPPADDING",  (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 14),
        ("LEFTPADDING",  (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))


# ─── SECTION BUILDER ─────────────────────────────────────────────────────────

def build_section(story: list, styles: dict, section_type: str, section_label: str, content_text: str):
    """Build a single resume section with divider and icon."""
    icon = SECTION_ICONS.get(section_type, "●")
    label_text = f"{icon}  {section_label.upper()}"

    story.append(Paragraph(label_text, styles["section_label"]))
    story.append(HRFlowable(
        width="100%", thickness=0.8,
        color=COLOR_ACCENT, spaceAfter=4
    ))

    # Parse content into lines
    lines = content_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            story.append(Spacer(1, 3))
            continue

        # Escape XML special chars for ReportLab
        line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if line.startswith("•") or line.startswith("-") or line.startswith("●"):
            story.append(Paragraph(f"  {line}", styles["bullet"]))
        else:
            story.append(Paragraph(line, styles["body"]))

    story.append(Spacer(1, 6))


# ─── NOTES SUMMARY BUILDER ───────────────────────────────────────────────────

def build_notes_summary(story: list, styles: dict, improvement_notes: list):
    """Build the improvement notes summary section at the bottom."""
    if not improvement_notes:
        return

    # Deduplicate notes
    seen = set()
    unique_notes = []
    for note in improvement_notes:
        if note.lower() not in seen:
            seen.add(note.lower())
            unique_notes.append(note)

    story.append(HRFlowable(width="100%", thickness=1.2, color=COLOR_ACCENT, spaceBefore=10, spaceAfter=6))
    story.append(Paragraph("✨  AI IMPROVEMENT SUMMARY", styles["notes_header"]))

    for note in unique_notes[:8]:  # cap at 8 unique notes
        note_escaped = note.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(f"  • {note_escaped}", styles["notes_item"]))

    story.append(Spacer(1, 8))


# ─── MAIN PDF BUILDER ────────────────────────────────────────────────────────

def build_pdf(
    sections: list,
    output_filename: str,
    job_title: str = "",
    company_name: str = "",
    improvement_notes: list = None,
    is_tailored: bool = False,
) -> str:
    """
    Build a professional PDF resume.

    Args:
        sections: list of dicts with section_type, section_label, content_text, position_index
        output_filename: filename (not full path) e.g. "resume_session_5.pdf"
        job_title: job title for header subtitle
        company_name: company name for header subtitle
        improvement_notes: list of improvement note strings (shown only for tailored)
        is_tailored: whether this is a tailored session export

    Returns:
        str: full path to the generated PDF
    """
    output_path = EXPORT_DIR / output_filename
    styles = build_styles()
    story = []

    # Sort sections by position_index
    sorted_sections = sorted(sections, key=lambda s: s.get("position_index", 0))

    # Deduplicate — keep only the FIRST occurrence of each section_type
    # Exception: allow multiple 'experience' and 'projects' entries
    ALLOW_MULTIPLE = {"experience", "projects"}
    seen_types = set()
    deduped_sections = []
    for s in sorted_sections:
        sec_type = s.get("section_type", "other")
        if sec_type in ALLOW_MULTIPLE:
            deduped_sections.append(s)
        elif sec_type not in seen_types:
            seen_types.add(sec_type)
            deduped_sections.append(s)
        # else: skip duplicate

    sorted_sections = deduped_sections

    # Extract contact section
    contact_section = next(
        (s for s in sorted_sections if s.get("section_type") == "contact"),
        None
    )
    contact = parse_contact(contact_section.get("content_text", "")) if contact_section else {"name": "Resume", "details": ""}

    # Build document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.6 * inch,
    )

    # 1 — Header
    build_header(story, styles, contact, job_title if is_tailored else "", company_name if is_tailored else "")

    # 2 — Sections (skip contact, already in header)
    SKIP_TYPES = {"contact"}
    for section in sorted_sections:
        sec_type = section.get("section_type", "other")
        if sec_type in SKIP_TYPES:
            continue
        content = section.get("content_text", "").strip()
        if not content:
            continue
        build_section(
            story, styles,
            sec_type,
            section.get("section_label", sec_type.title()),
            content
        )

    # 3 — Improvement notes (tailored only)
    if is_tailored and improvement_notes:
        build_notes_summary(story, styles, improvement_notes)

    # Build PDF
    doc.build(story)
    logger.info(f"PDF built: {output_path} ({output_path.stat().st_size} bytes)")
    return str(output_path)
