import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models.tailoring_session import TailoringSession
from models.resume import Resume
from models.resume_section import ResumeSection
from models.job import Job
from models.user import User
from routers.auth import get_current_user
from modules.score.ats_scorer import score_resume

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/score", tags=["ATS Scorer"])


class ATSScoreRequest(BaseModel):
    resume_id: int
    job_id: int
    session_id: Optional[int] = None  # if provided, score the tailored version

    class Config:
        json_schema_extra = {
            "example": {
                "resume_id": 2,
                "job_id": 1,
                "session_id": None
            }
        }


@router.get("/status")
def score_status():
    return {"status": "not implemented yet", "module": "ats_scorer"}


@router.post("/ats")
def score_ats(
    request: ATSScoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate resume ───────────────────────────────────────────
    resume = db.query(Resume).filter(
        Resume.id == request.resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume {request.resume_id} not found."
        )

    # ── 2. Validate job ──────────────────────────────────────────────
    job = db.query(Job).filter(
        Job.id == request.job_id,
        Job.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {request.job_id} not found."
        )

    # ── 3. Load sections (original or tailored) ──────────────────────
    if request.session_id:
        # Score the tailored version from a tailoring session
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
                    "section_type": s.get("section_type"),
                    "section_label": s.get("section_label"),
                    "content_text": s.get("tailored_text", ""),
                    "position_index": s.get("position_index", 0),
                }
                for s in tailored_data.get("sections", [])
            ]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse tailored session data: {e}"
            )
        scoring_source = "tailored"
    else:
        # Score the original resume sections
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
                "section_type": s.section_type,
                "section_label": s.section_label,
                "content_text": s.content_text,
                "position_index": s.position_index,
            }
            for s in db_sections
        ]
        scoring_source = "original"

    # ── 4. Parse skills from job ─────────────────────────────────────
    try:
        required_skills = json.loads(job.required_skills_json or "[]")
    except Exception:
        required_skills = []
    try:
        nice_to_have_skills = json.loads(job.nicetohave_skills_json or "[]")
    except Exception:
        nice_to_have_skills = []

    if not required_skills:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job has no required skills. Analyze the job description first."
        )

    # ── 5. Run ATS scorer ────────────────────────────────────────────
    try:
        result = score_resume(
            resume_sections=sections_data,
            required_skills=required_skills,
            nice_to_have_skills=nice_to_have_skills,
            job_title=job.job_title or "",
            company_name=job.company_name or "",
        )
    except Exception as e:
        logger.error(f"ATS scoring failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring failed: {str(e)}"
        )

    # ── 6. Save to DB if session_id provided, else create new record ─
    if request.session_id and session:
        session.ats_score = result["ats_score"]
        session.matched_keywords_json = json.dumps(result["matched_keywords"])
        session.missing_keywords_json = json.dumps(result["missing_keywords"])
        session.score_breakdown_json  = json.dumps(result["score_breakdown"])
        db.commit()
        logger.info(f"Updated tailoring_session {session.id} with ATS score={result['ats_score']}")
    else:
        # Create a new lightweight tailoring session just for the score
        new_session = TailoringSession(
            user_id=current_user.id,
            resume_id=resume.id,
            job_id=job.id,
            tailored_text="",
            tailored_json="{}",
            ai_provider="none",
            ai_model="ats_scorer_v1",
            ats_score=result["ats_score"],
            matched_keywords_json=json.dumps(result["matched_keywords"]),
            missing_keywords_json=json.dumps(result["missing_keywords"]),
            score_breakdown_json=json.dumps(result["score_breakdown"]),
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        logger.info(f"Created score session {new_session.id}, ATS score={result['ats_score']}")

    # ── 7. Return response ───────────────────────────────────────────
    return {
        "resume_id":          resume.id,
        "resume_name":        resume.name,
        "job_id":             job.id,
        "job_title":          job.job_title,
        "company_name":       job.company_name,
        "scoring_source":     scoring_source,
        "session_id":         request.session_id,
        "ats_score":          result["ats_score"],
        "match_rate":         result["match_rate"],
        "required_count":     result["required_count"],
        "matched_count":      result["matched_count"],
        "matched_keywords":   result["matched_keywords"],
        "missing_keywords":   result["missing_keywords"],
        "nicetohave_matched": result["nicetohave_matched"],
        "nicetohave_missing": result["nicetohave_missing"],
        "score_breakdown":    result["score_breakdown"],
        "recommendation":     result["recommendation"],
    }
