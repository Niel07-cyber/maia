import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from fakes import ScriptedLLM, call, say
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from maia.agent.agent import MAX_STEPS, Conversation, MaintenanceAgent
from maia.agent.llm import LLMResponse
from maia.agent.registry import TOOLS
from maia.db.models import Part, PartReservation, WorkOrder
from maia.manual.embeddings import Embedder

Transaction = Callable[[], AbstractContextManager[Session]]


WORK_ORDER_ARGS: dict[str, Any] = {
    "vehicle_id": "RV200-014",
    "asset_id": "RV200-014-B2",
    "procedure_code": "PROC-BRK-01",
    "priority": "high",
    "description": "Replace brake pads",
    "parts": [{"part_number": "BP-2207", "quantity": 2}],
}


def make_agent(
    responses: list[LLMResponse], embedder: Embedder, transaction: Transaction
) -> tuple[MaintenanceAgent, ScriptedLLM]:
    llm = ScriptedLLM(responses)
    return MaintenanceAgent(llm, embedder, transaction), llm


def last_tool_result(llm: ScriptedLLM) -> Any:
    tool_messages = [m for m in llm.received[-1] if m["role"] == "tool"]
    return json.loads(tool_messages[-1]["content"])


def work_orders(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(WorkOrder)) or 0


def test_plain_answer_needs_no_tools(embedder: Embedder, transaction: Transaction) -> None:
    agent, _ = make_agent([say("Hello, which vehicle?")], embedder, transaction)

    reply = agent.send(Conversation(), "Hi")

    assert reply.text == "Hello, which vehicle?"
    assert reply.events == []


def test_read_tool_runs_and_its_result_reaches_the_model(
    embedder: Embedder, transaction: Transaction
) -> None:
    agent, llm = make_agent(
        [call("check_stock", part_number="BP-2207"), say("6 brake pads available.")],
        embedder,
        transaction,
    )

    reply = agent.send(Conversation(), "How many brake pads are there?")

    assert reply.text == "6 brake pads available."
    assert [(e.name, e.ok) for e in reply.events] == [("check_stock", True)]
    assert last_tool_result(llm)["quantity_available"] == 6


def test_write_tool_waits_for_confirmation(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    agent, _ = make_agent([call("create_work_order", **WORK_ORDER_ARGS)], embedder, transaction)

    reply = agent.send(Conversation(), "Open a work order")

    assert len(reply.pending) == 1
    assert "reserve 2 x BP-2207" in reply.pending[0].description
    assert work_orders(depot) == 0


def test_approved_action_runs_atomically(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    agent, llm = make_agent(
        [call("create_work_order", **WORK_ORDER_ARGS), say("Work order opened.")],
        embedder,
        transaction,
    )
    conversation = Conversation()
    agent.send(conversation, "Open a work order")

    reply = agent.resolve(conversation, approved=True)

    assert reply.text == "Work order opened."
    assert reply.events[0].confirmed is True
    assert work_orders(depot) == 1
    assert depot.get_one(Part, "BP-2207").quantity_reserved == 2
    assert last_tool_result(llm)["reservations"][0]["quantity_available_after"] == 4


def test_declined_action_is_not_run_and_the_model_is_told(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    agent, llm = make_agent(
        [call("create_work_order", **WORK_ORDER_ARGS), say("Understood, nothing opened.")],
        embedder,
        transaction,
    )
    conversation = Conversation()
    agent.send(conversation, "Open a work order")

    reply = agent.resolve(conversation, approved=False)

    assert work_orders(depot) == 0
    assert reply.events[0].confirmed is False
    assert "declined" in last_tool_result(llm)["error"]


def test_replying_instead_of_confirming_declines_the_action(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    agent, _ = make_agent(
        [call("create_work_order", **WORK_ORDER_ARGS), say("OK, what next?")],
        embedder,
        transaction,
    )
    conversation = Conversation()
    agent.send(conversation, "Open a work order")

    agent.send(conversation, "Actually, wait")

    assert conversation.pending == []
    assert work_orders(depot) == 0


def test_failed_reservation_rolls_back_the_whole_work_order(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    too_many: dict[str, Any] = {
        **WORK_ORDER_ARGS,
        "parts": [{"part_number": "BP-2207", "quantity": 7}],
    }
    agent, llm = make_agent(
        [call("create_work_order", **too_many), say("Not enough pads.")], embedder, transaction
    )
    conversation = Conversation()
    agent.send(conversation, "Open a work order")

    agent.resolve(conversation, approved=True)

    assert work_orders(depot) == 0
    assert depot.scalar(select(func.count()).select_from(PartReservation)) == 0
    assert "6 available, 7 requested" in last_tool_result(llm)["error"]


def test_invalid_arguments_are_reported_to_the_model(
    embedder: Embedder, transaction: Transaction
) -> None:
    agent, llm = make_agent(
        [call("log_step", vehicle_id="RV200-014", procedure_code="PROC-BRK-01"), say("Sorry.")],
        embedder,
        transaction,
    )

    reply = agent.send(Conversation(), "Step done")

    assert reply.events[0].ok is False
    assert "Invalid arguments" in last_tool_result(llm)["error"]


def test_unknown_tool_is_reported_to_the_model(
    embedder: Embedder, transaction: Transaction
) -> None:
    agent, llm = make_agent([call("delete_everything"), say("Sorry.")], embedder, transaction)

    agent.send(Conversation(), "Hi")

    assert "no tool called" in last_tool_result(llm)["error"]


def test_step_limit_stops_a_looping_model(embedder: Embedder, transaction: Transaction) -> None:
    looping = [
        call("check_stock", call_id=f"c{i}", part_number="BP-2207") for i in range(MAX_STEPS)
    ]
    agent, _ = make_agent(looping, embedder, transaction)

    reply = agent.send(Conversation(), "Hi")

    assert "could not finish" in reply.text
    assert len(reply.events) == MAX_STEPS


@pytest.mark.parametrize("name", list(TOOLS))
def test_tool_schemas_use_only_simple_json_schema(name: str) -> None:
    schema = json.dumps(TOOLS[name].schema())

    assert "$ref" not in schema
    assert "anyOf" not in schema
