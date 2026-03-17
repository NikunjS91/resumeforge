from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()
