"""
Resume history endpoint — returns all tailoring sessions for the current user.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models.tailoring_session import TailoringSession
from models.resume import Resume
from models.job import Job
from models.user import User
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["History"])


@router.get("/")
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
    offset: int = 0
):
    """
    Returns all tailoring sessions for the current user, most recent first.
    Each session includes resume name, job title, ATS score, model used, date.
    """
    sessions = (
        db.query(TailoringSession)
        .filter(TailoringSession.user_id == current_user.id)
        .order_by(TailoringSession.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for session in sessions:
        # Get resume name
        resume = db.query(Resume).filter(Resume.id == session.resume_id).first()
        resume_name = resume.name if resume else f"Resume #{session.resume_id}"

        # Get job info
        job = db.query(Job).filter(Job.id == session.job_id).first()
        job_title = job.job_title if job else "Unknown Role"
        company_name = job.company_name if job else "Unknown Company"

        # Parse tailored_json to get sections_tailored and improvement_notes
        sections_tailored = 0
        notes_count = 0
        try:
            tailored_data = json.loads(session.tailored_json or "{}")
            sections = tailored_data.get("sections", [])
            sections_tailored = sum(1 for s in sections if s.get("was_tailored", False))
            notes = tailored_data.get("improvement_notes", [])
            notes_count = len(notes)
        except Exception:
            pass

        results.append({
            "session_id":    session.id,
            "resume_id":     session.resume_id,
            "resume_name":   resume_name,
            "job_id":        session.job_id,
            "job_title":     job_title,
            "company_name":  company_name,
            "ai_model":      session.ai_model or "unknown",
            "ats_score":     session.ats_score,
            "sections_tailored": sections_tailored,
            "notes_count":   notes_count,
            "has_pdf":       bool(session.pdf_path),
            "pdf_path":      session.pdf_path,
            "created_at":    str(session.created_at) if hasattr(session, 'created_at') else None,
        })

    return {
        "total": len(results),
        "sessions": results
    }


@router.get("/{session_id}/pdf")
def download_session_pdf(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-download a previously generated PDF for a session."""
    session = db.query(TailoringSession).filter(
        TailoringSession.id == session_id,
        TailoringSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.pdf_path or not Path(session.pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail="PDF not found for this session. Please re-export from the pipeline."
        )

    resume = db.query(Resume).filter(Resume.id == session.resume_id).first()
    resume_name = resume.name if resume else "resume"

    return FileResponse(
        path=session.pdf_path,
        media_type="application/pdf",
        filename=f"ResumeForge_{resume_name}_session{session_id}.pdf",
        headers={"Content-Disposition": f'attachment; filename="ResumeForge_{resume_name}.pdf"'}
    )
