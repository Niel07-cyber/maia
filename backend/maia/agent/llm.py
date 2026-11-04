"""The chat model behind the agent. ChatModel is a protocol, so tests can script the
model's replies while the app calls a real one through LiteLLM."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from maia.config import get_settings


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    # The assistant message exactly as the provider returned it. It is sent back on the next
    # turn unchanged, so provider-specific details (such as Gemini's) are preserved.
    raw_message: dict[str, Any] = field(default_factory=dict)


class ChatModel(Protocol):
    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> LLMResponse: ...


class LiteLLMChat:
    """A hosted chat model through LiteLLM (default: the model set in LLM_MODEL)."""

    def __init__(self, model: str | None = None, temperature: float | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.llm_model
        self.api_key = settings.api_key_for(self.model)
        self.temperature = temperature

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        import litellm  # slow to import; only needed for real calls

        logging.getLogger("LiteLLM").setLevel(logging.WARNING)
        options = {} if self.temperature is None else {"temperature": self.temperature}
        response = litellm.completion(
            model=self.model,
            messages=messages,
            tools=tools,
            api_key=self.api_key,
            num_retries=3,
            **options,
        )
        message = response.choices[0].message
        tool_calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=json.loads(call.function.arguments or "{}"),
            )
            for call in (message.tool_calls or [])
        ]
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            raw_message=message.model_dump(exclude_none=True),
        )
