from maia.config import Settings


def test_api_key_matches_the_model_provider() -> None:
    settings = Settings(openai_api_key="openai-key", gemini_api_key="gemini-key")

    assert settings.api_key_for("gemini/gemini-embedding-001") == "gemini-key"
    assert settings.api_key_for("openai/gpt-4o-mini") == "openai-key"
