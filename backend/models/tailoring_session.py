from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class TailoringSession(Base):
    __tablename__ = "tailoring_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Foreign keys to three parent tables
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    # AI output
    tailored_text = Column(Text, nullable=False)            # Full AI-generated tailored resume text
    tailored_json = Column(Text, nullable=False)            # Structured JSON of tailored sections

    # ATS scoring
    ats_score = Column(Integer, nullable=False, default=0)  # 0-100
    matched_keywords_json = Column(Text, nullable=False, default="[]")   # Keywords found
    missing_keywords_json = Column(Text, nullable=False, default="[]")   # Keywords still missing
    # e.g. { "skills_match": 88, "experience_relevance": 72, "keyword_density": 80 }
    score_breakdown_json = Column(Text, nullable=False, default="{}")

    # AI provider tracking
    # Values: "ollama" | "claude" | "openai" | "gemini"
    ai_provider = Column(String, nullable=False)
    # Exact model used e.g. "mistral:7b", "gpt-4o", "claude-sonnet-4-6"
    ai_model = Column(String, nullable=False)

    # PDF export — NULL until user clicks Export PDF
    pdf_path = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="tailoring_sessions")
    resume = relationship("Resume", back_populates="tailoring_sessions")
    job = relationship("Job", back_populates="tailoring_sessions")
