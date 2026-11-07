from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from fakes import ScriptedLLM, say
from sqlalchemy.orm import Session

from maia.agent.agent import MaintenanceAgent
from maia.agent.llm import ChatModel, LLMResponse, Usage
from maia.benchmark.benchmark import RunResult, Setup, report, run_benchmark, summarize
from maia.benchmark.runner import Agent
from maia.benchmark.scenario import Scenario
from maia.manual.embeddings import Embedder

Transaction = Callable[[], AbstractContextManager[Session]]

PPE = Scenario.model_validate(
    {
        "id": "ppe",
        "title": "PPE",
        "description": "What to wear",
        "technician": {"messages": ["What do I wear?"]},
        "expect": {"mentions": ["gloves"], "no_work_order": True},
    }
)

ANSWERS = {
    "good-model": "Wear gloves and safety glasses.",
    "bad-model": "Wear whatever you like.",
}


@pytest.fixture
def results(embedder: Embedder, transaction: Transaction) -> list[RunResult]:
    def make_llm(model: str) -> ChatModel:
        answer = LLMResponse(ANSWERS[model], usage=Usage(100, 10, 0.002))
        return ScriptedLLM([answer])

    def explicit(llm: ChatModel) -> Agent:
        return MaintenanceAgent(llm, embedder, transaction)

    return run_benchmark(
        [PPE],
        [Setup("explicit", "good-model"), Setup("explicit", "bad-model")],
        repeats=2,
        make_llm=make_llm,
        agents={"explicit": explicit},
        transaction=transaction,
    )


def test_every_setup_runs_every_scenario_the_requested_number_of_times(
    results: list[RunResult],
) -> None:
    assert [(r.model, r.repeat) for r in results] == [
        ("good-model", 1),
        ("good-model", 2),
        ("bad-model", 1),
        ("bad-model", 2),
    ]
    assert all(r.llm_calls == 1 and r.cost_usd == 0.002 for r in results)


def test_summary_compares_the_setups(results: list[RunResult]) -> None:
    good, bad = summarize(results)

    assert (good.model, good.passed, good.pass_rate) == ("good-model", 2, 1.0)
    assert (bad.model, bad.passed, bad.pass_rate) == ("bad-model", 0, 0.0)
    assert good.total_cost_usd == pytest.approx(0.004)
    assert good.passed_by_scenario == {"ppe": 2}


def test_report_contains_scenarios_summaries_and_transcripts(results: list[RunResult]) -> None:
    data = report([PPE], 2, results)

    assert data["scenarios"] == [{"id": "ppe", "title": "PPE", "description": "What to wear"}]
    assert len(data["summaries"]) == 2
    assert data["runs"][0]["turns"][0]["reply"] == ANSWERS["good-model"]


def test_cost_is_unknown_when_any_run_has_no_price(results: list[RunResult]) -> None:
    results[0].cost_usd = None

    good, _ = summarize(results)

    assert good.total_cost_usd is None and good.mean_cost_usd is None


def test_each_run_starts_from_fresh_demo_data(
    embedder: Embedder, transaction: Transaction, depot: Session
) -> None:
    from maia.db.models import Part

    def make_llm(model: str) -> ChatModel:
        return ScriptedLLM([say("ok")])

    def explicit(llm: ChatModel) -> Agent:
        return MaintenanceAgent(llm, embedder, transaction)

    depot.get_one(Part, "BP-2207").quantity_reserved = 3
    depot.flush()

    run_benchmark(
        [PPE],
        [Setup("explicit", "any")],
        1,
        make_llm=make_llm,
        agents={"explicit": explicit},
        transaction=transaction,
    )

    assert depot.get_one(Part, "BP-2207").quantity_reserved == 0
