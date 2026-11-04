"""Application settings, read from environment variables or the repo-level .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    openai_api_key: str = ""
    gemini_api_key: str = ""

    llm_model: str = "gemini/gemini-2.5-flash"
    llm_model_alt: str = "gemini/gemini-2.5-flash-lite"
    embedding_model: str = "gemini/gemini-embedding-001"

    database_url: str = "postgresql+psycopg://maia:maia@db:5432/maia"
    frontend_origin: str = "http://localhost:5173"

    def api_key_for(self, model: str) -> str:
        """Pick the API key that matches a LiteLLM model name ("gemini/..." or "openai/...")."""
        if model.startswith("gemini/"):
            return self.gemini_api_key
        return self.openai_api_key


@lru_cache
def get_settings() -> Settings:
    """Return the settings, built once and reused (cached)."""
    return Settings()
