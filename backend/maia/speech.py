"""Speech-to-text for push-to-talk: a technician wearing gloves can speak instead of type."""

import logging
from typing import Protocol

from maia.agent.llm import ModelUnavailableError
from maia.config import get_settings

# Words a general speech model is likely to mishear. Giving them as a prompt helps it spell
# part numbers and procedure codes the way the manual does.
VOCABULARY = (
    "RV-200 railcar maintenance. RV200-014, RV200-027, bogie B2, pantograph, lockout/tagout, "
    "SAF-01, PROC-BRK-01, PROC-PAN-03, BP-2207, CS-1130, DS-450, millimetres, volts."
)


class Transcriber(Protocol):
    def transcribe(self, audio: bytes, filename: str) -> str: ...


class LiteLLMTranscriber:
    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.transcription_model
        self.api_key = settings.api_key_for(self.model)

    def transcribe(self, audio: bytes, filename: str) -> str:
        import litellm  # slow to import; only needed for real calls
        import openai

        logging.getLogger("LiteLLM").setLevel(logging.WARNING)
        try:
            response = litellm.transcription(
                model=self.model,
                file=(filename, audio),
                language="en",
                prompt=VOCABULARY,
                api_key=self.api_key,
                max_retries=2,
            )
        except openai.APIError as exc:
            raise ModelUnavailableError(str(exc)) from exc
        return (response.text or "").strip()
