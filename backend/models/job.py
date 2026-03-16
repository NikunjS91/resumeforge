from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Auto-generated name: "Google — SWE Intern — Mar 2026"
    auto_name = Column(String, nullable=False)

    # Full pasted job description text
    jd_raw_text = Column(Text, nullable=False)

    # LLM-extracted metadata
    company_name = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    location = Column(String, nullable=True)
    is_remote = Column(Boolean, nullable=True)

    # Intern | Junior | Mid | Senior | Lead
    seniority_level = Column(String, nullable=True)

    # JSON arrays: ["Python", "FastAPI", "AWS", "Docker"]
    required_skills_json = Column(Text, nullable=True, default="[]")
    nicetohave_skills_json = Column(Text, nullable=True, default="[]")

    # e.g. "$80,000 — $100,000" if mentioned in JD
    salary_range = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="jobs")
    tailoring_sessions = relationship("TailoringSession", back_populates="job", cascade="all, delete-orphan")
