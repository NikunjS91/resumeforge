import json
import logging
import os
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
from modules.export.pdf_builder import build_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["PDF Exporter"])


@router.get("/status")
def export_status():
    return {"status": "not implemented yet", "module": "pdf_exporter"}


class ExportRequest(BaseModel):
    resume_id: Optional[int] = None    # export original resume
    session_id: Optional[int] = None   # export tailored session

    class Config:
        json_schema_extra = {
            "example": {
                "resume_id": None,
                "session_id": 5
            }
        }


@router.post("/pdf")
def export_pdf(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate — must provide exactly one of session_id or resume_id ──
    if not request.session_id and not request.resume_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either session_id (tailored export) or resume_id (original export)."
        )

    sections_data = []
    improvement_notes = []
    is_tailored = False
    job_title = ""
    company_name = ""
    resume_name = "resume"

    # ── 2. Load from tailoring session ──────────────────────────────────────
    if request.session_id:
        session = db.query(TailoringSession).filter(
            TailoringSession.id == request.session_id,
            TailoringSession.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tailoring session {request.session_id} not found."
            )

        # Parse tailored sections from JSON
        try:
            tailored_data = json.loads(session.tailored_json or "{}")
            sections_data = [
                {
                    "section_type":  s.get("section_type"),
                    "section_label": s.get("section_label"),
                    "content_text":  s.get("tailored_text", ""),
                    "position_index": s.get("position_index", 0),
                }
                for s in tailored_data.get("sections", [])
            ]
            improvement_notes = tailored_data.get("improvement_notes", [])
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse tailoring session: {e}"
            )

        is_tailored = True

        # Load job info for header subtitle
        job = db.query(Job).filter(Job.id == session.job_id).first()
        if job:
            job_title = job.job_title or ""
            company_name = job.company_name or ""

        # Load resume name
        resume = db.query(Resume).filter(Resume.id == session.resume_id).first()
        resume_name = resume.name if resume else "resume"
        output_filename = f"tailored_{resume_name}_{request.session_id}.pdf"

    # ── 3. Load from original resume ────────────────────────────────────────
    else:
        resume = db.query(Resume).filter(
            Resume.id == request.resume_id,
            Resume.user_id == current_user.id
        ).first()
        if not resume:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resume {request.resume_id} not found."
            )

        db_sections = db.query(ResumeSection).filter(
            ResumeSection.resume_id == resume.id
        ).order_by(ResumeSection.position_index).all()

        if not db_sections:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Resume has no sections. Upload and parse the resume first."
            )

        sections_data = [
            {
                "section_type":  s.section_type,
                "section_label": s.section_label,
                "content_text":  s.content_text,
                "position_index": s.position_index,
            }
            for s in db_sections
        ]
        resume_name = resume.name
        output_filename = f"original_{resume_name}_{request.resume_id}.pdf"

    # ── 4. Build PDF ─────────────────────────────────────────────────────────
    try:
        pdf_path = build_pdf(
            sections=sections_data,
            output_filename=output_filename,
            job_title=job_title,
            company_name=company_name,
            improvement_notes=improvement_notes,
            is_tailored=is_tailored,
        )
    except Exception as e:
        logger.error(f"PDF build failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(e)}"
        )

    # ── 5. Save pdf_path to tailoring_sessions ───────────────────────────────
    if request.session_id and session:
        session.pdf_path = pdf_path
        db.commit()
        logger.info(f"Saved pdf_path to tailoring_session {session.id}")

    # ── 6. Return PDF as downloadable file ───────────────────────────────────
    if not Path(pdf_path).exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF was not created successfully."
        )

    download_name = f"ResumeForge_{resume_name}.pdf"
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
    )
