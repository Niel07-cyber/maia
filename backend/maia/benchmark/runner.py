"""Play a scenario's scripted technician against an agent and record what happened."""

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from maia.agent.agent import AgentReply, Conversation, ToolEvent
from maia.agent.llm import ChatModel, LLMResponse, ModelUnavailableError
from maia.benchmark.scenario import Scenario

MAX_TURNS = 12  # technician turns per scenario, so an agent that keeps asking cannot loop


class Agent(Protocol):
    """Any agent the benchmark can drive: ours, or another implementation to compare."""

    def send(self, conversation: Conversation, text: str) -> AgentReply: ...

    def resolve(self, conversation: Conversation, approved: bool) -> AgentReply: ...


class MeteredModel:
    """Wraps a chat model to count its calls, tokens and cost."""

    def __init__(self, inner: ChatModel) -> None:
        self.inner = inner
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost_usd = 0.0
        self.cost_known = True

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResponse:
        response = self.inner.complete(messages, tools)
        self.calls += 1
        if response.usage is None:
            self.cost_known = False
            return response
        self.prompt_tokens += response.usage.prompt_tokens
        self.completion_tokens += response.usage.completion_tokens
        if response.usage.cost_usd is None:
            self.cost_known = False
        else:
            self.cost_usd += response.usage.cost_usd
        return response


@dataclass
class Turn:
    technician: str  # what the technician said, or [approve] / [decline]
    reply: str
    events: list[ToolEvent]
    pending: list[str]
    seconds: float


@dataclass
class Transcript:
    scenario_id: str
    session_id: str
    turns: list[Turn] = field(default_factory=list)
    error: str | None = None

    @property
    def events(self) -> list[ToolEvent]:
        return [event for turn in self.turns for event in turn.events]

    @property
    def replies(self) -> list[str]:
        return [turn.reply for turn in self.turns]

    @property
    def seconds(self) -> float:
        return sum(turn.seconds for turn in self.turns)


def run_scenario(agent: Agent, scenario: Scenario) -> Transcript:
    """Say the scripted messages in order. Whenever the agent asks for confirmation, answer
    as the script says before saying anything else."""
    conversation = Conversation()
    transcript = Transcript(scenario.id, conversation.session_id)
    messages = list(scenario.technician.messages)
    approve = scenario.technician.confirm == "approve"
    waiting_for_confirmation = False

    for _ in range(MAX_TURNS):
        if waiting_for_confirmation:
            said = "[approve]" if approve else "[decline]"
        elif messages:
            said = messages.pop(0)
        else:
            break
        start = time.perf_counter()
        try:
            if waiting_for_confirmation:
                reply = agent.resolve(conversation, approve)
            else:
                reply = agent.send(conversation, said)
        except ModelUnavailableError as exc:
            transcript.error = str(exc)
            break
        transcript.turns.append(
            Turn(
                technician=said,
                reply=reply.text,
                events=reply.events,
                pending=[action.description for action in reply.pending],
                seconds=time.perf_counter() - start,
            )
        )
        waiting_for_confirmation = bool(reply.pending)
    return transcript
