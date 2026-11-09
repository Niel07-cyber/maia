"""Chat endpoints: start a session, send a message, confirm or cancel an action."""

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from maia.agent.agent import AgentReply, Conversation, MaintenanceAgent
from maia.agent.budget import BudgetExceededError
from maia.agent.llm import ModelUnavailableError
from maia.agent.sessions import ConversationStore
from maia.api.deps import get_agent, get_conversation_store
from maia.api.limits import RateLimited

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["chat"])

AgentDep = Annotated[MaintenanceAgent, Depends(get_agent)]
StoreDep = Annotated[ConversationStore, Depends(get_conversation_store)]


class SessionCreated(BaseModel):
    session_id: str


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ConfirmationIn(BaseModel):
    approved: bool


class EventOut(BaseModel):
    name: str
    ok: bool
    confirmed: bool | None
    result: Any  # what the tool returned, so the UI can show readings and work orders


class PendingOut(BaseModel):
    tool: str
    description: str


class ChatReply(BaseModel):
    text: str
    events: list[EventOut]
    pending: list[PendingOut]

    @classmethod
    def from_agent(cls, reply: AgentReply) -> "ChatReply":
        return cls(
            text=reply.text,
            events=[
                EventOut(name=e.name, ok=e.ok, confirmed=e.confirmed, result=e.result)
                for e in reply.events
            ],
            pending=[PendingOut(tool=p.tool, description=p.description) for p in reply.pending],
        )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(store: StoreDep) -> SessionCreated:
    return SessionCreated(session_id=store.create().session_id)


@router.post("/{session_id}/messages", dependencies=[RateLimited])
def send_message(
    session_id: str, message: MessageIn, agent: AgentDep, store: StoreDep
) -> ChatReply:
    conversation = _get_conversation(store, session_id)
    with store.lock_for(session_id):
        return _call_agent(lambda: agent.send(conversation, message.text))


@router.post("/{session_id}/confirmation", dependencies=[RateLimited])
def confirm(
    session_id: str, confirmation: ConfirmationIn, agent: AgentDep, store: StoreDep
) -> ChatReply:
    conversation = _get_conversation(store, session_id)
    with store.lock_for(session_id):
        return _call_agent(lambda: agent.resolve(conversation, confirmation.approved))


def _get_conversation(store: ConversationStore, session_id: str) -> Conversation:
    conversation = store.get(session_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or expired session.")
    return conversation


def _call_agent(run: Callable[[], AgentReply]) -> ChatReply:
    try:
        return ChatReply.from_agent(run())
    except BudgetExceededError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ModelUnavailableError as exc:
        logger.warning("model unavailable: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The AI model is unavailable right now. Please try again in a moment.",
        ) from exc
