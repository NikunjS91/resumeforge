import os
import json
import logging
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models.tailoring_session import TailoringSession
from models.resume import Resume
from models.resume_section import ResumeSection
from models.job import Job
from models.user import User
from routers.auth import get_current_user
from modules.export.latex_generator import generate_latex_stage1, build_data_summary
from modules.export.latex_reviewer import review_latex_stage2
from modules.export.latex_compiler import compile_latex
from modules.export.latex_surgeon import surgical_tailor
from modules.export.spacing_normalizer import normalize_spacing

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["PDF Exporter"])


@router.get("/status")
def export_status():
    return {"status": "operational", "module": "latex_pdf_exporter"}


class ExportRequest(BaseModel):
    resume_id: Optional[int] = None
    session_id: Optional[int] = None
    template: Optional[str] = "classic"

    class Config:
        json_schema_extra = {
            "example": {
                "resume_id": None,
                "session_id": 5,
                "template": "classic"  # classic | minimal | modern
            }
        }


@router.post("/pdf")
def export_pdf(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate ──────────────────────────────────────────────────────────
    if not request.session_id and not request.resume_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either session_id (tailored) or resume_id (original)."
        )

    sections_data  = []
    job_title      = ""
    company_name   = ""
    resume_name    = "resume"
    output_stem    = ""
    session        = None

    # ── 2. Load from tailoring session ───────────────────────────────────────
    if request.session_id:
        session = db.query(TailoringSession).filter(
            TailoringSession.id == request.session_id,
            TailoringSession.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(status_code=404,
                detail=f"Tailoring session {request.session_id} not found.")

        try:
            tailored_data = json.loads(session.tailored_json or "{}")
            sections_data = [
                {
                    "section_type":   s.get("section_type"),
                    "section_label":  s.get("section_label", ""),
                    "content_text":   s.get("tailored_text", s.get("content_text", "")),
                    "position_index": s.get("position_index", 0),
                }
                for s in tailored_data.get("sections", [])
                if s.get("tailored_text", s.get("content_text", "")).strip()
            ]
        except Exception as e:
            raise HTTPException(status_code=500,
                detail=f"Failed to parse tailoring session: {e}")

        job = db.query(Job).filter(Job.id == session.job_id).first()
        if job:
            job_title    = job.job_title or ""
            company_name = job.company_name or ""

        resume = db.query(Resume).filter(Resume.id == session.resume_id).first()
        resume_name = resume.name if resume else "resume"
        output_stem = f"tailored_{resume_name}_{request.session_id}"

    # ── 3. Load from original resume ─────────────────────────────────────────
    else:
        resume = db.query(Resume).filter(
            Resume.id == request.resume_id,
            Resume.user_id == current_user.id
        ).first()
        if not resume:
            raise HTTPException(status_code=404,
                detail=f"Resume {request.resume_id} not found.")

        db_sections = db.query(ResumeSection).filter(
            ResumeSection.resume_id == resume.id
        ).order_by(ResumeSection.position_index).all()

        if not db_sections:
            raise HTTPException(status_code=422,
                detail="Resume has no sections. Upload and parse the resume first.")

        sections_data = [
            {
                "section_type":   s.section_type,
                "section_label":  s.section_label,
                "content_text":   s.content_text,
                "position_index": s.position_index,
            }
            for s in db_sections
        ]
        resume_name = resume.name
        output_stem = f"original_{resume_name}_{request.resume_id}"

    # ── 4. Load job data for skills ─────────────────────────────────────────────
    required_skills = []
    nicetohave_skills = []
    improvement_notes = []
    is_tailored = bool(request.session_id)

    if request.session_id and session:
        job = db.query(Job).filter(Job.id == session.job_id).first()
        if job:
            try:
                required_skills = json.loads(job.required_skills_json or '[]')
                nicetohave_skills = json.loads(job.nicetohave_skills_json or '[]')
            except Exception:
                pass
        try:
            # improvement_notes are stored inside tailored_json, not a separate field
            tailored_data = json.loads(session.tailored_json or "{}")
            improvement_notes = tailored_data.get("improvement_notes", [])
            if not isinstance(improvement_notes, list):
                improvement_notes = []
        except Exception:
            pass

    # ── 5. Check for master LaTeX ───────────────────────────────────────────────
    resume_for_master = db.query(Resume).filter(
        Resume.id == (session.resume_id if request.session_id else request.resume_id)
    ).first()

    has_master = bool(resume_for_master and resume_for_master.master_latex)
    logger.info(f"Master LaTeX available: {has_master}")

    if has_master:
        # ── SURGICAL PATH: minimal changes to master LaTeX ────────────────────────
        logger.info("Using surgical tailoring on master LaTeX")
        try:
            latex_final = surgical_tailor(
                master_latex=resume_for_master.master_latex,
                job_title=job_title,
                company_name=company_name,
                required_skills=required_skills,
                nicetohave_skills=nicetohave_skills,
                provider="nvidia" if os.getenv('NVIDIA_API_KEY') else "ollama"
            )
            logger.info("Surgical tailoring complete")
        except Exception as e:
            logger.warning(f"Surgical tailor failed, using master as-is: {e}")
            latex_final = resume_for_master.master_latex

    else:
        # ── GENERATION PATH: original 2-stage LLM generation ─────────────────────
        logger.info("No master LaTeX — using full generation pipeline")
        try:
            latex_stage1 = generate_latex_stage1(
                sections=sections_data,
                job_title=job_title,
                company_name=company_name,
                required_skills=required_skills,
                nicetohave_skills=nicetohave_skills,
                improvement_notes=improvement_notes,
                is_tailored=is_tailored,
                provider="nvidia" if os.getenv('NVIDIA_API_KEY') else "ollama",
                template=request.template or "classic"
            )
            logger.info(f"Stage 1 LaTeX generated: {len(latex_stage1)} chars")
        except Exception as e:
            logger.error(f"Stage 1 generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"LaTeX generation failed: {e}")

        try:
            original_data = build_data_summary(sections_data)
            latex_final = review_latex_stage2(
                latex_code=latex_stage1,
                original_data=original_data,
                provider="nvidia" if os.getenv('NVIDIA_API_KEY') else "ollama"
            )
            logger.info(f"Stage 2 reviewed LaTeX: {len(latex_final)} chars")
        except Exception as e:
            logger.warning(f"Stage 2 review failed, using Stage 1 output: {e}")
            latex_final = latex_stage1

    # ── 6. Normalize spacing and compile to PDF ──────────────────────────────────
    try:
        pdf_path = compile_latex(latex_final, output_stem)
    except RuntimeError as e:
        # If compilation fails and we have stage1, try that
        if not has_master and 'latex_stage1' in locals():
            logger.warning(f"Compilation failed, trying Stage 1: {e}")
            try:
                pdf_path = compile_latex(latex_stage1, output_stem + "_s1")
            except RuntimeError as e2:
                raise HTTPException(status_code=500, detail=f"PDF compilation failed: {e2}")
        else:
            raise HTTPException(status_code=500, detail=f"PDF compilation failed: {e}")

    # ── 7. Save pdf_path to DB ────────────────────────────────────────────────
    if session:
        session.pdf_path = pdf_path
        db.commit()

    # ── 8. Return PDF ─────────────────────────────────────────────────────────
    download_name = f"ResumeForge_{resume_name}.pdf"
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
    )


# ══════════════════════════════════════════════════════════════════════════════
# Master LaTeX endpoints for surgical tailoring
# ══════════════════════════════════════════════════════════════════════════════

class MasterLatexRequest(BaseModel):
    resume_id: int
    latex_content: str   # the full .tex file content


@router.post("/master-latex")
def upload_master_latex(
    request: MasterLatexRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Store a perfect LaTeX file as the master resume for a given resume_id.
    This becomes the source of truth for all future PDF exports.
    """
    resume = db.query(Resume).filter(
        Resume.id == request.resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Validate it's real LaTeX
    if '\\documentclass' not in request.latex_content:
        raise HTTPException(
            status_code=422,
            detail="Content does not appear to be valid LaTeX (missing \\documentclass)"
        )

    resume.master_latex = request.latex_content
    db.commit()

    return {
        "resume_id": resume.id,
        "message": "Master LaTeX stored successfully",
        "latex_length": len(request.latex_content)
    }


@router.get("/master-latex/{resume_id}")
def get_master_latex(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a master LaTeX exists for a resume."""
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    return {
        "resume_id": resume_id,
        "has_master_latex": bool(resume.master_latex),
        "latex_length": len(resume.master_latex) if resume.master_latex else 0
    }

