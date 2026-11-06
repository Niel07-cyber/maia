"""Test doubles shared by several test files."""

from typing import Any

from maia.agent.llm import LLMResponse, ModelUnavailableError, ToolCall


class ScriptedLLM:
    """Replays prepared model responses in order and records what the agent sent."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.received: list[list[dict[str, Any]]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        self.received.append([dict(m) for m in messages])
        return self.responses.pop(0)


class UnavailableLLM:
    """A model whose provider is down."""

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        raise ModelUnavailableError("503 high demand")


def say(text: str) -> LLMResponse:
    return LLMResponse(content=text)


def call(name: str, *, call_id: str = "c1", **arguments: Any) -> LLMResponse:
    return LLMResponse(content=None, tool_calls=[ToolCall(call_id, name, arguments)])
