from pydantic import BaseModel
from datetime import datetime
from typing import Optional


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
