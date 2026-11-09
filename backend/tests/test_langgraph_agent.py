"""The LangGraph agent must behave like the explicit loop: same tools, same confirmation
gate, same limits. These mirror the most important tests in test_agent.py."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from fakes import ScriptedLLM, UnavailableLLM, call, say
from sqlalchemy import select
from sqlalchemy.orm import Session

from maia.agent.agent import MAX_STEPS, Conversation
from maia.agent.langgraph_agent import GIVE_UP, LangGraphAgent
from maia.agent.llm import LLMResponse, ModelUnavailableError
from maia.db.models import StepLog, WorkOrder
from maia.manual.embeddings import Embedder

Transaction = Callable[[], AbstractContextManager[Session]]

WORK_ORDER: dict[str, Any] = {
    "vehicle_id": "RV200-014",
    "asset_id": "RV200-014-B2",
    "procedure_code": "PROC-BRK-01",
    "priority": "high",
    "description": "Replace brake pads",
    "parts": [{"part_number": "BP-2207", "quantity": 2}],
}

STEP: dict[str, Any] = {"vehicle_id": "RV200-014", "procedure_code": "PROC-BRK-01", "step": 1}


def agent(
    responses: list[LLMResponse], embedder: Embedder, transaction: Transaction
) -> LangGraphAgent:
    return LangGraphAgent(ScriptedLLM(responses), embedder, transaction)


def test_answers_without_tools(embedder: Embedder, transaction: Transaction) -> None:
    reply = agent([say("Hello.")], embedder, transaction).send(Conversation(), "Hi")

    assert reply.text == "Hello."
    assert reply.events == [] and reply.pending == []


def test_runs_tools_that_change_nothing_right_away(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    conversation = Conversation()
    maia = agent([call("log_step", **STEP), say("Step 1 logged.")], embedder, transaction)

    reply = maia.send(conversation, "Lockout done.")

    assert reply.text == "Step 1 logged."
    assert [(e.name, e.ok) for e in reply.events] == [("log_step", True)]
    logged = depot.scalars(select(StepLog).where(StepLog.session_id == conversation.session_id))
    assert [entry.step for entry in logged] == [1]


def test_a_write_waits_for_confirmation_then_runs(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    conversation = Conversation()
    maia = agent(
        [call("create_work_order", **WORK_ORDER), say("Work order opened.")], embedder, transaction
    )

    asked = maia.send(conversation, "Open a work order")

    assert [p.tool for p in asked.pending] == ["create_work_order"]
    assert "2 x BP-2207" in asked.pending[0].description
    assert depot.scalars(select(WorkOrder)).all() == []  # nothing written yet

    done = maia.resolve(conversation, approved=True)

    assert done.text == "Work order opened."
    assert [(e.name, e.ok, e.confirmed) for e in done.events] == [("create_work_order", True, True)]
    assert len(depot.scalars(select(WorkOrder)).all()) == 1


def test_a_declined_write_is_not_done(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    conversation = Conversation()
    maia = agent(
        [call("create_work_order", **WORK_ORDER), say("Cancelled.")], embedder, transaction
    )
    maia.send(conversation, "Open a work order")

    reply = maia.resolve(conversation, approved=False)

    assert reply.events[0].confirmed is False
    assert depot.scalars(select(WorkOrder)).all() == []


def test_replying_instead_of_confirming_declines_and_reads_the_message(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    conversation = Conversation()
    llm = ScriptedLLM([call("create_work_order", **WORK_ORDER), say("OK, no work order.")])
    maia = LangGraphAgent(llm, embedder, transaction)
    maia.send(conversation, "Open a work order")

    reply = maia.send(conversation, "Actually, wait.")

    assert reply.text == "OK, no work order."
    assert reply.events[0].confirmed is False
    assert depot.scalars(select(WorkOrder)).all() == []


def test_nothing_to_confirm(embedder: Embedder, transaction: Transaction) -> None:
    reply = agent([], embedder, transaction).resolve(Conversation(), approved=True)

    assert reply.text == "There is nothing waiting for confirmation."


def test_gives_up_after_too_many_steps(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    looping = [call("check_stock", part_number="BP-2207") for _ in range(MAX_STEPS + 2)]

    reply = agent(looping, embedder, transaction).send(Conversation(), "Stock?")

    assert reply.text == GIVE_UP
    assert len(reply.events) == MAX_STEPS


def test_a_model_outage_is_raised_like_the_explicit_agent(
    embedder: Embedder, transaction: Transaction
) -> None:
    maia = LangGraphAgent(UnavailableLLM(), embedder, transaction)

    with pytest.raises(ModelUnavailableError):
        maia.send(Conversation(), "Hi")
