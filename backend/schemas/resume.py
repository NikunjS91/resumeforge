from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ResumeCreate(BaseModel):
    name: str


class ResumeResponse(BaseModel):
    id: int
    user_id: int
    name: str
    original_filename: str
    file_format: str
    char_count: int
    page_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class SectionOut(BaseModel):
    section_type:   str
    section_label:  str
    content_text:   str
    position_index: int
    detected_by:    str


class ResumeUploadOut(BaseModel):
    resume_id:     int
    name:          str
    file_format:   str
    char_count:    int
    page_count:    int
    section_count: int
    sections:      List[SectionOut]

    class Config:
        from_attributes = True
