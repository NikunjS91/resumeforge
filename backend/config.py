from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ResumeForge"
    app_version: str = "1.0.0"
    debug: bool = True

    database_url: str = "sqlite:///./data/resumeforge.db"

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    upload_dir: str = "./data/resumes"
    max_file_size_mb: int = 10

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
