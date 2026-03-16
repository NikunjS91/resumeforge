from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Any


class TailoringSessionResponse(BaseModel):
    id: int
    user_id: int
    resume_id: int
    job_id: int
    ats_score: int
    ai_provider: str
    ai_model: str
    pdf_path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TailoredSectionOut(BaseModel):
    section_type:      str
    section_label:     str
    position_index:    int
    was_tailored:      bool
    tailored_text:     str
    improvement_notes: List[str]


class TailorOut(BaseModel):
    session_id:        int
    resume_id:         int
    job_id:            int
    resume_name:       str
    job_title:         Optional[str]
    company_name:      Optional[str]
    ai_model:          str
    sections_tailored: int
    total_sections:    int
    improvement_notes: List[str]
    tailored_sections: List[TailoredSectionOut]

    class Config:
        from_attributes = True
