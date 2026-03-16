from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class JobCreate(BaseModel):
    jd_raw_text: str


class JobResponse(BaseModel):
    id: int
    user_id: int
    auto_name: str
    company_name: Optional[str]
    job_title: Optional[str]
    location: Optional[str]
    is_remote: Optional[bool]
    seniority_level: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class JobAnalyzeOut(BaseModel):
    job_id:              int
    auto_name:           str
    company_name:        Optional[str]
    job_title:           Optional[str]
    location:            Optional[str]
    is_remote:           bool
    seniority_level:     Optional[str]
    salary_range:        Optional[str]
    required_skills:     List[str]
    nice_to_have_skills: List[str]
    required_count:      int
    nicetohave_count:    int

    class Config:
        from_attributes = True
