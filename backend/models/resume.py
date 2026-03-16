from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)                   # User-chosen name e.g. "Google SWE Resume"
    original_filename = Column(String, nullable=False)      # Original uploaded filename
    file_format = Column(String, nullable=False)            # "pdf" or "docx"
    file_path = Column(String, nullable=False)              # Relative path on disk
    raw_text = Column(Text, nullable=False)                 # Full plain text extracted from file
    structured_json = Column(Text, nullable=False)          # JSON blob of all parsed sections
    llm_extras_json = Column(Text, nullable=True)           # LLM-detected extra sections beyond standard 7
    char_count = Column(Integer, nullable=False, default=0)
    page_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="resumes")
    sections = relationship("ResumeSection", back_populates="resume", cascade="all, delete-orphan")
    tailoring_sessions = relationship("TailoringSession", back_populates="resume", cascade="all, delete-orphan")
