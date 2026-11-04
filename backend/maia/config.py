"""Application settings, read from environment variables or the repo-level .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    openai_api_key: str = ""
    gemini_api_key: str = ""

    llm_model: str = "openai/gpt-4o-mini"
    llm_model_alt: str = "gemini/gemini-2.5-flash"
    embedding_model: str = "text-embedding-3-small"

    database_url: str = "postgresql+psycopg://maia:maia@db:5432/maia"
    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    """Return the settings, built once and reused (cached)."""
    return Settings()
