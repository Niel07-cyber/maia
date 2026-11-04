"""Turn text into embedding vectors. The Embedder protocol lets tests use a fake, offline
embedder while the app uses a real model."""

from typing import Protocol

from maia.config import get_settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...


class LiteLLMEmbedder:
    """Embeddings from a hosted model through LiteLLM (default: OpenAI text-embedding-3-small)."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.embedding_model
        self.api_key = api_key or settings.openai_api_key

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Imported here, not at the top: importing litellm is slow (it fetches a model price
        # list), and only real embedding calls need it.
        import litellm

        response = litellm.embedding(model=self.model, input=texts, api_key=self.api_key)
        return [list(item["embedding"]) for item in response.data]
