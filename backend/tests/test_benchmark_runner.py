from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from fakes import ScriptedLLM, UnavailableLLM, call, say
from sqlalchemy.orm import Session

from maia.agent.agent import MaintenanceAgent
from maia.agent.llm import LLMResponse, Usage
from maia.benchmark.runner import MAX_TURNS, MeteredModel, run_scenario
from maia.benchmark.scenario import Scenario
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


def scenario(messages: list[str], confirm: str = "approve") -> Scenario:
    return Scenario.model_validate(
        {
            "id": "test",
            "title": "Test",
            "description": "Test scenario",
            "technician": {"messages": messages, "confirm": confirm},
            "expect": {},
        }
    )


def with_usage(response: LLMResponse, cost: float | None = 0.001) -> LLMResponse:
    return LLMResponse(response.content, response.tool_calls, usage=Usage(100, 20, cost))


def test_technician_says_each_message_and_approves_confirmations(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    llm = MeteredModel(
        ScriptedLLM(
            [
                with_usage(say("Which vehicle?")),
                with_usage(call("create_work_order", **WORK_ORDER)),
                with_usage(say("Work order opened.")),
            ]
        )
    )
    agent = MaintenanceAgent(llm, embedder, transaction)

    transcript = run_scenario(agent, scenario(["Hi", "Open a work order"]))

    assert [turn.technician for turn in transcript.turns] == [
        "Hi",
        "Open a work order",
        "[approve]",
    ]
    assert transcript.turns[1].pending  # the work order waited for confirmation
    [event] = transcript.events
    assert (event.name, event.ok, event.confirmed) == ("create_work_order", True, True)
    assert transcript.replies[-1] == "Work order opened."
    assert transcript.error is None
    assert (llm.calls, llm.prompt_tokens, llm.completion_tokens) == (3, 300, 60)
    assert round(llm.cost_usd, 6) == 0.003 and llm.cost_known


def test_technician_can_decline(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    llm = ScriptedLLM([call("create_work_order", **WORK_ORDER), say("Cancelled.")])
    agent = MaintenanceAgent(llm, embedder, transaction)

    transcript = run_scenario(agent, scenario(["Open a work order"], confirm="decline"))

    assert transcript.turns[-1].technician == "[decline]"
    assert transcript.events[0].confirmed is False


def test_a_model_outage_is_recorded_not_raised(
    embedder: Embedder, transaction: Transaction
) -> None:
    agent = MaintenanceAgent(UnavailableLLM(), embedder, transaction)

    transcript = run_scenario(agent, scenario(["Hi"]))

    assert transcript.turns == []
    assert transcript.error is not None and "503" in transcript.error


def test_an_agent_that_keeps_asking_is_stopped(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    # The model proposes the same work order again after every refusal.
    responses = [call("create_work_order", **WORK_ORDER) for _ in range(MAX_TURNS + 5)]
    agent = MaintenanceAgent(ScriptedLLM(responses), embedder, transaction)

    transcript = run_scenario(agent, scenario(["Open a work order"], confirm="decline"))

    assert len(transcript.turns) == MAX_TURNS


def test_unknown_cost_is_flagged() -> None:
    llm = MeteredModel(ScriptedLLM([with_usage(say("Hi"), cost=None)]))

    llm.complete([], [])

    assert not llm.cost_known
    assert llm.prompt_tokens == 100
