"""The same agent built with LangGraph, to compare an orchestration framework with the
explicit loop in agent.py (see docs/adr/0002).

Same model client, prompt, tools and safety rules: only the orchestration differs. The
conversation is a graph of nodes; the confirmation gate is a LangGraph interrupt, and the
conversation state lives in a checkpointer, keyed by the session id.

    START -> model -> tools -> model -> ... -> END
                        \\-> confirm (interrupt: wait for the technician) -> model
"""

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from maia.agent.agent import (
    MAX_STEPS,
    AgentReply,
    Conversation,
    PendingAction,
    ToolEvent,
    TransactionFactory,
    describe_call,
    needs_confirmation,
    run_tool,
    tool_message,
)
from maia.agent.llm import ChatModel, ToolCall
from maia.agent.prompts import SYSTEM_PROMPT
from maia.agent.registry import TOOLS
from maia.manual.embeddings import Embedder

GIVE_UP = "I could not finish this request. Please rephrase or break it into steps."
CONFIRM = "Please confirm the following action(s)."


class State(TypedDict, total=False):
    # Lists with operator.add are appended to; the other keys are replaced on each update.
    messages: Annotated[list[dict[str, Any]], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
    calls: list[dict[str, Any]]  # tool calls from the last model response
    pending: list[dict[str, Any]]  # tool calls waiting for the technician
    steps: int  # model calls in this turn
    reply: str


def _call(data: dict[str, Any]) -> ToolCall:
    return ToolCall(id=data["id"], name=data["name"], arguments=data["arguments"])


def _session_id(config: RunnableConfig) -> str:
    session_id: str = config["configurable"]["thread_id"]
    return session_id


def _event(event: ToolEvent) -> dict[str, Any]:
    return {
        "name": event.name,
        "arguments": event.arguments,
        "ok": event.ok,
        "result": event.result,
        "confirmed": event.confirmed,
    }


class LangGraphAgent:
    def __init__(self, llm: ChatModel, embedder: Embedder, transaction: TransactionFactory) -> None:
        self.llm = llm
        self.embedder = embedder
        self.transaction = transaction
        self.tool_schemas = [tool.schema() for tool in TOOLS.values()]
        self.graph = self._build().compile(checkpointer=InMemorySaver())

    # ---------- the same interface as MaintenanceAgent ----------

    def send(self, conversation: Conversation, text: str) -> AgentReply:
        config = self._config(conversation)
        before = self._event_count(config)
        if self._waiting(config):
            # The technician replied instead of confirming: decline, then read the message.
            self.graph.invoke(
                Command(
                    resume={
                        "approved": False,
                        "reason": "The technician replied instead.",
                        "message": text,
                    }
                ),
                config,
            )
        else:
            self.graph.invoke(
                {"messages": [{"role": "user", "content": text}], "steps": 0, "pending": []},
                config,
            )
        return self._reply(config, before)

    def resolve(self, conversation: Conversation, approved: bool) -> AgentReply:
        config = self._config(conversation)
        if not self._waiting(config):
            return AgentReply(text="There is nothing waiting for confirmation.")
        before = self._event_count(config)
        self.graph.invoke(
            Command(resume={"approved": approved, "reason": "The technician declined."}), config
        )
        return self._reply(config, before)

    # ---------- the graph ----------

    def _build(self) -> StateGraph[State]:
        graph = StateGraph(State)
        graph.add_node("model", self._model)
        graph.add_node("tools", self._tools)
        graph.add_node("confirm", self._confirm)
        graph.add_node("give_up", lambda state: {"reply": GIVE_UP})
        graph.add_edge(START, "model")
        graph.add_conditional_edges("model", lambda state: "tools" if state["calls"] else END)
        graph.add_conditional_edges("tools", self._after_tools)
        graph.add_edge("confirm", "model")
        graph.add_edge("give_up", END)
        return graph

    def _model(self, state: State) -> State:
        response = self.llm.complete(
            [{"role": "system", "content": SYSTEM_PROMPT}, *state["messages"]], self.tool_schemas
        )
        return {
            "messages": [
                response.raw_message or {"role": "assistant", "content": response.content}
            ],
            "calls": [
                {"id": c.id, "name": c.name, "arguments": c.arguments} for c in response.tool_calls
            ],
            "steps": state.get("steps", 0) + 1,
            "reply": response.content or "",
        }

    def _tools(self, state: State, config: RunnableConfig) -> State:
        """Run the tools that change nothing; hold the others for confirmation."""
        messages, events, pending = [], [], []
        for data in state["calls"]:
            call = _call(data)
            if needs_confirmation(call):
                pending.append(data)
                continue
            event = run_tool(call, self.embedder, self.transaction, _session_id(config))
            messages.append(tool_message(call, event.result))
            events.append(_event(event))
        return {"messages": messages, "events": events, "pending": pending}

    def _after_tools(self, state: State) -> Literal["confirm", "model", "give_up"]:
        if state["pending"]:
            return "confirm"
        return "give_up" if state["steps"] >= MAX_STEPS else "model"

    def _confirm(self, state: State, config: RunnableConfig) -> State:
        # interrupt() pauses the graph here and saves its state. When the technician answers,
        # this node runs again from the top and interrupt() returns their decision. Nothing
        # with side effects may happen before it.
        decision: dict[str, Any] = interrupt({"pending": state["pending"]})
        messages, events = [], []
        for data in state["pending"]:
            call = _call(data)
            if decision["approved"]:
                event = run_tool(
                    call, self.embedder, self.transaction, _session_id(config), confirmed=True
                )
            else:
                result = {"error": f"Not done. {decision['reason']}"}
                event = ToolEvent(call.name, call.arguments, False, result, confirmed=False)
            messages.append(tool_message(call, event.result))
            events.append(_event(event))
        if decision.get("message"):
            messages.append({"role": "user", "content": decision["message"]})
        return {"messages": messages, "events": events, "pending": [], "steps": 0}

    # ---------- helpers ----------

    @staticmethod
    def _config(conversation: Conversation) -> RunnableConfig:
        # The session id doubles as LangGraph's thread id: one saved state per conversation.
        return {"configurable": {"thread_id": conversation.session_id}}

    def _waiting(self, config: RunnableConfig) -> bool:
        return bool(self.graph.get_state(config).next)

    def _event_count(self, config: RunnableConfig) -> int:
        return len(self.graph.get_state(config).values.get("events", []))

    def _reply(self, config: RunnableConfig, before: int) -> AgentReply:
        snapshot = self.graph.get_state(config)
        values = snapshot.values
        events = [ToolEvent(**data) for data in values.get("events", [])[before:]]
        pending: list[PendingAction] = []
        if snapshot.next:
            pending = [describe_call(_call(data)) for data in values.get("pending", [])]
        text = values.get("reply", "") or (CONFIRM if pending else "")
        return AgentReply(text=text, events=events, pending=pending)
