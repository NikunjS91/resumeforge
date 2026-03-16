from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_config"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # "ollama" | "claude" | "openai" | "gemini"
    provider_name = Column(String, unique=True, nullable=False)

    # Toggle on/off without touching code
    is_enabled = Column(Boolean, default=True, nullable=False)

    # Default model for this provider e.g. "mistral:7b", "claude-sonnet-4-6", "gpt-4o"
    default_model = Column(String, nullable=False)

    # Per-module model overrides
    # e.g. { "analyzer": "mistral:7b", "tailor": "llama3.2", "scorer": "deepseek-r1" }
    module_overrides_json = Column(Text, nullable=True, default="{}")

    # Fallback order: 1 = try first, 2 = try second, etc.
    priority_order = Column(Integer, nullable=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
