"""Application settings, read from environment variables or the repo-level .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    openai_api_key: str = ""
    gemini_api_key: str = ""

    llm_model: str = "openai/gpt-5.4-mini"
    llm_model_alt: str = "openai/gpt-5.4-nano"
    # How long GPT-5 style models think before answering: minimal, low, medium or high.
    # Lower is faster; empty means the provider's default.
    llm_reasoning_effort: str | None = "low"
    embedding_model: str = "openai/text-embedding-3-small"

    # Speech-to-text for push-to-talk.
    transcription_model: str = "openai/gpt-4o-mini-transcribe"

    # Public demo protection. 0 turns a limit off (the default, for local development).
    rate_limit_per_minute: int = 0  # requests per visitor that call a model
    rate_limit_per_day: int = 0
    daily_budget_usd: float = 0.0  # chat model spending per UTC day, for the whole demo

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
