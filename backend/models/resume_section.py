from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class ResumeSection(Base):
    __tablename__ = "resume_sections"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)

    # Section identity
    # Valid values: contact | summary | experience | education | skills | projects | certifications | llm_detected
    section_type = Column(String, nullable=False)
    section_label = Column(String, nullable=False)          # Heading as it appeared in the file e.g. "WORK EXPERIENCE"

    # Content storage — dual format
    content_text = Column(Text, nullable=False)             # Plain text of this section
    content_json = Column(Text, nullable=False)             # Structured JSON e.g. list of jobs with bullets

    # Formatting metadata extracted from PDF/DOCX
    # JSON array: [{ "text": "...", "bold": true, "italic": false, "font": "Calibri", "size": 12, "x": 72, "y": 140 }]
    formatting_json = Column(Text, nullable=False, default="[]")

    # Position in original document (1 = first section, 2 = second, etc.)
    position_index = Column(Integer, nullable=False, default=0)

    # Edit tracking — user can optionally review and edit parsed content
    is_edited = Column(Boolean, default=False, nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    resume = relationship("Resume", back_populates="sections")
