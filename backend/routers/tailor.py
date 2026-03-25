import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models.tailoring_session import TailoringSession
from models.resume import Resume
from models.resume_section import ResumeSection
from models.job import Job
from models.user import User
from routers.auth import get_current_user
from modules.tailor.resume_tailor import tailor_resume, DEFAULT_MODEL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tailor", tags=["Resume Tailor"])


class TailorRequest(BaseModel):
    resume_id: int
    job_id:    int
    provider:  Optional[str] = "ollama"  # "ollama" or "nvidia"

    class Config:
        json_schema_extra = {
            "example": {
                "resume_id": 2,
                "job_id":    1,
                "provider":  "ollama"
            }
        }


@router.get("/status")
def tailor_status():
    return {"status": "not implemented yet", "module": "resume_tailor"}


@router.post("/resume")
def tailor_resume_endpoint(
    request: TailorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate resume belongs to user ──────────────────────────
    resume = db.query(Resume).filter(
        Resume.id == request.resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume {request.resume_id} not found or does not belong to you."
        )

    # ── 2. Validate job belongs to user ─────────────────────────────
    job = db.query(Job).filter(
        Job.id == request.job_id,
        Job.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {request.job_id} not found or does not belong to you."
        )

    # ── 3. Load resume sections ──────────────────────────────────────
    sections = db.query(ResumeSection).filter(
        ResumeSection.resume_id == resume.id
    ).order_by(ResumeSection.position_index).all()

    if not sections:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Resume has no sections. Please upload and parse the resume first."
        )

    # ── 4. Parse skills from job ─────────────────────────────────────
    try:
        required_skills = json.loads(job.required_skills_json or "[]")
    except Exception:
        required_skills = []
    try:
        nice_to_have_skills = json.loads(job.nicetohave_skills_json or "[]")
    except Exception:
        nice_to_have_skills = []

    # ── 5. Build sections list for tailor module ─────────────────────
    sections_data = [
        {
            "section_type": s.section_type,
            "section_label": s.section_label,
            "content_text": s.content_text,
            "position_index": s.position_index,
        }
        for s in sections
    ]

    # ── 6. Run tailoring pipeline ────────────────────────────────────
    logger.info(
        f"Starting tailor: resume_id={resume.id}, job_id={job.id}, "
        f"user_id={current_user.id}, sections={len(sections_data)}"
    )
    try:
        result = tailor_resume(
            resume_sections=sections_data,
            job_title=job.job_title or "the role",
            company_name=job.company_name or "the company",
            required_skills=required_skills,
            nice_to_have_skills=nice_to_have_skills,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Tailoring failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tailoring failed: {str(e)}"
        )

    # ── 7. Save to tailoring_sessions table ──────────────────────────
    ai_model = DEFAULT_MODEL
    session_record = TailoringSession(
        user_id=current_user.id,
        resume_id=resume.id,
        job_id=job.id,
        tailored_text=result["tailored_full_text"],
        tailored_json=json.dumps({
            "sections": result["tailored_sections"],
            "improvement_notes": result["improvement_notes"],
        }),
        ai_provider=request.provider,
        ai_model=ai_model,
    )

    db.add(session_record)
    db.commit()
    db.refresh(session_record)
    logger.info(f"Saved tailoring_session_id={session_record.id}")

    # ── 8. Return response ───────────────────────────────────────────
    return {
        "session_id": session_record.id,
        "resume_id": resume.id,
        "job_id": job.id,
        "resume_name": resume.name,
        "job_title": job.job_title,
        "company_name": job.company_name,
        "ai_model": ai_model,
        "sections_tailored": result["sections_tailored"],
        "total_sections": result["total_sections"],
        "improvement_notes": result["improvement_notes"],
        "tailored_sections": [
            {
                "section_type": s["section_type"],
                "section_label": s["section_label"],
                "position_index": s["position_index"],
                "was_tailored": s["was_tailored"],
                "tailored_text": s["tailored_text"],
                "improvement_notes": s["improvement_notes"],
            }
            for s in result["tailored_sections"]
        ],
    }
