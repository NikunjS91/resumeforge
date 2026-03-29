import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models.job import Job
from models.user import User
from routers.auth import get_current_user
from modules.analyze.jd_analyzer import analyze_jd

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyze", tags=["Job Analyzer"])


class JDAnalyzeRequest(BaseModel):
    jd_text: str

    class Config:
        json_schema_extra = {
            "example": {
                "jd_text": "We are looking for a Senior Cloud Engineer at Acme Corp..."
            }
        }


@router.get("/status")
def analyze_status():
    return {"status": "operational", "module": "job_analyzer"}


@router.post("/job")
def analyze_job(
    request: JDAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate input ───────────────────────────────────────────
    if not request.jd_text or len(request.jd_text.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job description is too short. Provide the full JD text (min 50 chars)."
        )

    # ── 2. Run JD analysis pipeline ─────────────────────────────────
    try:
        analysis = analyze_jd(request.jd_text)
    except Exception as e:
        logger.error(f"JD analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )

    # ── 3. Auto-generate job name ────────────────────────────────────
    company   = analysis.get("company_name") or "Unknown Company"
    title     = analysis.get("job_title") or "Unknown Role"
    date_str  = datetime.utcnow().strftime("%b %Y")
    auto_name = f"{company} — {title} ({date_str})"

    # ── 4. Save to DB ────────────────────────────────────────────────
    job_record = Job(
        user_id           = current_user.id,
        auto_name         = auto_name,
        jd_raw_text       = analysis["jd_raw_text"],
        company_name      = analysis.get("company_name"),
        job_title         = analysis.get("job_title"),
        location          = analysis.get("location"),
        is_remote         = analysis.get("is_remote", False),
        seniority_level   = analysis.get("seniority_level"),
        required_skills_json   = json.dumps(analysis.get("required_skills", [])),
        nicetohave_skills_json = json.dumps(analysis.get("nice_to_have_skills", [])),
        salary_range      = analysis.get("salary_range"),
    )
    db.add(job_record)
    db.commit()
    db.refresh(job_record)
    logger.info(f"Saved job_id={job_record.id} for user_id={current_user.id}")

    # ── 5. Return response ───────────────────────────────────────────
    return {
        "job_id":              job_record.id,
        "auto_name":           auto_name,
        "company_name":        job_record.company_name,
        "job_title":           job_record.job_title,
        "location":            job_record.location,
        "is_remote":           job_record.is_remote,
        "seniority_level":     job_record.seniority_level,
        "salary_range":        job_record.salary_range,
        "required_skills":     analysis.get("required_skills", []),
        "nice_to_have_skills": analysis.get("nice_to_have_skills", []),
        "required_count":      len(analysis.get("required_skills", [])),
        "nicetohave_count":    len(analysis.get("nice_to_have_skills", [])),
    }
