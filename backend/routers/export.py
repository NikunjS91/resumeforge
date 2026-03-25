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
            improvement_notes = json.loads(session.improvement_notes_json or '[]')
        except Exception:
            pass

    # ── 5. Stage 1 — Generate LaTeX ──────────────────────────────────────────────
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

    # ── 6. Stage 2 — Review and Fix ──────────────────────────────────────────────
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

    # ── 7. Compile to PDF ────────────────────────────────────────────────────────
    try:
        pdf_path = compile_latex(latex_final, output_stem)
    except RuntimeError as e:
        # If compilation fails, try Stage 1 output directly
        logger.warning(f"Compilation of Stage 2 output failed, trying Stage 1: {e}")
        try:
            pdf_path = compile_latex(latex_stage1, output_stem + "_s1")
        except RuntimeError as e2:
            raise HTTPException(status_code=500, detail=f"PDF compilation failed: {e2}")

    # ── 8. Save pdf_path to DB ────────────────────────────────────────────────
    if session:
        session.pdf_path = pdf_path
        db.commit()

    # ── 9. Return PDF ─────────────────────────────────────────────────────────
    download_name = f"ResumeForge_{resume_name}.pdf"
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
    )
