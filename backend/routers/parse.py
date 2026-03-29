import uuid
import json
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.resume import Resume
from models.resume_section import ResumeSection
from models.user import User
from routers.auth import get_current_user
from modules.parse.extractor import extract
from modules.parse.section_detector import detect_sections

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/parse", tags=["Resume Parser"])

UPLOAD_BASE = Path(__file__).parent.parent / "data" / "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


# Keep exactly as Day 1 left it
@router.get("/status")
def parse_status():
    return {"status": "operational", "module": "resume_parser"}


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ── 1. Validate file extension ──────────────────────────
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Only PDF and DOCX allowed."
        )

    # ── 2. Read content & validate size ─────────────────────
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 5MB."
        )

    # ── 3. Save file to disk ────────────────────────────────
    user_dir = UPLOAD_BASE / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    saved_filename = f"{uuid.uuid4()}{ext}"
    file_path = user_dir / saved_filename
    file_path.write_bytes(content)
    logger.info(f"Saved upload: {file_path}")

    # ── 4. Extract text ─────────────────────────────────────
    file_format = ext.lstrip(".")
    extraction  = extract(str(file_path), file_format)
    raw_text    = extraction["raw_text"]
    page_count  = extraction["page_count"]

    # ── 5. Detect sections ──────────────────────────────────
    sections = detect_sections(raw_text)

    # ── 6. Save Resume to DB ────────────────────────────────
    name = Path(file.filename).stem
    structured = {
        "section_count": len(sections),
        "sections": [s["section_type"] for s in sections],
    }
    resume_record = Resume(
        user_id           = current_user.id,
        name              = name,
        original_filename = file.filename,
        file_format       = file_format,
        file_path         = str(file_path),
        raw_text          = raw_text,
        structured_json   = json.dumps(structured),
        char_count        = len(raw_text),
        page_count        = page_count,
    )
    db.add(resume_record)
    db.flush()  # get resume_record.id before commit

    # ── 7. Save Sections to DB ──────────────────────────────
    for sec in sections:
        db.add(ResumeSection(
            resume_id       = resume_record.id,
            section_type    = sec["section_type"],
            section_label   = sec["section_label"],
            content_text    = sec["content_text"],
            content_json    = json.dumps({"text": sec["content_text"]}),
            position_index  = sec["position_index"],
            formatting_json = json.dumps({"detected_by": sec["detected_by"]}),
            is_edited       = False,
        ))

    db.commit()
    db.refresh(resume_record)

    # ── 8. Return response ─────────────────────────────────
    return {
        "resume_id":     resume_record.id,
        "name":          resume_record.name,
        "file_format":   resume_record.file_format,
        "char_count":    resume_record.char_count,
        "page_count":    resume_record.page_count,
        "section_count": len(sections),
        "sections": [
            {
                "section_type":   s["section_type"],
                "section_label":  s["section_label"],
                "content_text":   s["content_text"],
                "position_index": s["position_index"],
                "detected_by":    s["detected_by"],
            }
            for s in sections
        ]
    }


@router.post("/reparse/{resume_id}")
def reparse_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-parse a previously uploaded resume using the current section_detector.
    Useful when the parser is improved and existing DB sections are stale.
    """
    resume = db.query(Resume).filter(
        Resume.id == resume_id,
        Resume.user_id == current_user.id
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found.")

    file_path = Path(resume.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=422, detail="Resume file not found on disk.")

    # Re-extract and re-detect sections
    extraction = extract(str(file_path), resume.file_format)
    raw_text   = extraction["raw_text"]
    sections   = detect_sections(raw_text)

    # Delete old sections and insert fresh ones
    db.query(ResumeSection).filter(ResumeSection.resume_id == resume_id).delete()
    for sec in sections:
        db.add(ResumeSection(
            resume_id       = resume_id,
            section_type    = sec["section_type"],
            section_label   = sec["section_label"],
            content_text    = sec["content_text"],
            content_json    = json.dumps({"text": sec["content_text"]}),
            position_index  = sec["position_index"],
            formatting_json = json.dumps({"detected_by": sec["detected_by"]}),
            is_edited       = False,
        ))

    # Update raw_text in case extractor improved too
    resume.raw_text = raw_text
    db.commit()

    logger.info(f"Re-parsed resume {resume_id}: {len(sections)} sections")
    return {
        "resume_id":     resume_id,
        "section_count": len(sections),
        "sections": [
            {
                "section_type":  s["section_type"],
                "section_label": s["section_label"],
                "position_index": s["position_index"],
            }
            for s in sections
        ]
    }
