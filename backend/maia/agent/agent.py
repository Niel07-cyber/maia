"""The agent loop: send the conversation to the LLM, run the tools it asks for, and repeat
until it answers. Tools that change records wait for the technician's confirmation."""

import json
import logging
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from maia.agent.llm import ChatModel, ToolCall
from maia.agent.prompts import SYSTEM_PROMPT
from maia.agent.registry import TOOLS, ToolContext, to_json
from maia.manual.embeddings import Embedder
from maia.tools.errors import ToolError

logger = logging.getLogger(__name__)

MAX_STEPS = 8  # model calls per user turn, so a confused model cannot loop forever

# Opens a transaction for one tool call: committed on success, rolled back on error.
TransactionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass
class Conversation:
    """Everything the agent remembers about one technician session."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    messages: list[dict[str, Any]] = field(default_factory=list)
    pending: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ToolEvent:
    """One tool call, for the UI and the benchmark."""

    name: str
    arguments: dict[str, Any]
    ok: bool
    result: Any
    confirmed: bool | None = None  # None: no confirmation needed


@dataclass(frozen=True)
class PendingAction:
    call_id: str
    tool: str
    description: str


@dataclass(frozen=True)
class AgentReply:
    text: str
    events: list[ToolEvent] = field(default_factory=list)
    pending: list[PendingAction] = field(default_factory=list)


class MaintenanceAgent:
    def __init__(self, llm: ChatModel, embedder: Embedder, transaction: TransactionFactory) -> None:
        self.llm = llm
        self.embedder = embedder
        self.transaction = transaction
        self.tool_schemas = [tool.schema() for tool in TOOLS.values()]

    def send(self, conversation: Conversation, text: str) -> AgentReply:
        """Handle a message from the technician."""
        events: list[ToolEvent] = []
        if conversation.pending:
            # The technician replied instead of confirming: treat the actions as declined.
            events += self._decline_pending(conversation, "The technician replied instead.")
        conversation.messages.append({"role": "user", "content": text})
        return self._run(conversation, events)

    def resolve(self, conversation: Conversation, approved: bool) -> AgentReply:
        """Run or cancel the actions waiting for confirmation, then let the agent continue."""
        if not conversation.pending:
            return AgentReply(text="There is nothing waiting for confirmation.")
        if approved:
            events = [
                self._execute(conversation, call, confirmed=True) for call in conversation.pending
            ]
            conversation.pending = []
        else:
            events = self._decline_pending(conversation, "The technician declined.")
        return self._run(conversation, events)

    # ---------- internals ----------

    def _run(self, conversation: Conversation, events: list[ToolEvent]) -> AgentReply:
        for _ in range(MAX_STEPS):
            response = self.llm.complete(
                [{"role": "system", "content": SYSTEM_PROMPT}, *conversation.messages],
                self.tool_schemas,
            )
            conversation.messages.append(
                response.raw_message or {"role": "assistant", "content": response.content}
            )
            if not response.tool_calls:
                return AgentReply(text=response.content or "", events=events)

            needs_confirmation = []
            for call in response.tool_calls:
                tool = TOOLS.get(call.name)
                if tool is not None and tool.requires_confirmation:
                    needs_confirmation.append(call)
                else:
                    events.append(self._execute(conversation, call))

            if needs_confirmation:
                conversation.pending = needs_confirmation
                return AgentReply(
                    text=response.content or "Please confirm the following action(s).",
                    events=events,
                    pending=[self._describe(call) for call in needs_confirmation],
                )
        return AgentReply(
            text="I could not finish this request. Please rephrase or break it into steps.",
            events=events,
        )

    def _execute(
        self, conversation: Conversation, call: ToolCall, confirmed: bool | None = None
    ) -> ToolEvent:
        """Validate the arguments, run the tool in its own transaction, and give the result
        (or the reason it failed) back to the LLM."""
        tool = TOOLS.get(call.name)
        ok = False
        try:
            if tool is None:
                raise ToolError(f"There is no tool called '{call.name}'.")
            args = tool.args_model.model_validate(call.arguments)
            with self.transaction() as session:
                ctx = ToolContext(session, self.embedder, conversation.session_id)
                result: Any = to_json(tool.run(ctx, args))
            ok = True
        except ValidationError as exc:
            result = {"error": f"Invalid arguments: {exc.errors(include_url=False)}"}
        except ToolError as exc:
            result = {"error": str(exc)}

        logger.info("tool %s ok=%s", call.name, ok)
        self._add_tool_message(conversation, call, result)
        return ToolEvent(call.name, call.arguments, ok, result, confirmed)

    def _decline_pending(self, conversation: Conversation, reason: str) -> list[ToolEvent]:
        events = []
        for call in conversation.pending:
            result = {"error": f"Not done. {reason}"}
            self._add_tool_message(conversation, call, result)
            events.append(ToolEvent(call.name, call.arguments, False, result, confirmed=False))
        conversation.pending = []
        return events

    @staticmethod
    def _describe(call: ToolCall) -> PendingAction:
        tool = TOOLS[call.name]
        try:
            args = tool.args_model.model_validate(call.arguments)
            description = tool.describe(args) if tool.describe else call.name
        except ValidationError:
            description = f"{call.name} {json.dumps(call.arguments)}"
        return PendingAction(call.id, call.name, description)

    @staticmethod
    def _add_tool_message(conversation: Conversation, call: ToolCall, result: Any) -> None:
        conversation.messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "name": call.name,
                "content": json.dumps(result),
            }
        )
