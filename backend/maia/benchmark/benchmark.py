"""Run every scenario for every agent and model, several times, and summarise the results."""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from maia.agent.agent import TransactionFactory
from maia.agent.llm import ChatModel
from maia.benchmark.runner import Agent, MeteredModel, Transcript, run_scenario
from maia.benchmark.scenario import Scenario
from maia.benchmark.scoring import Score, score
from maia.db.seed import reset_demo

# Builds an agent around a chat model. A new agent per run, so runs share nothing.
AgentFactory = Callable[[ChatModel], Agent]


@dataclass(frozen=True)
class Setup:
    """One configuration to compare: an agent implementation and a model."""

    agent: str
    model: str


@dataclass
class RunResult:
    agent: str
    model: str
    scenario_id: str
    repeat: int
    passed: bool
    safety_violations: list[str]
    checks: list[dict[str, Any]]
    seconds: float
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    error: str | None
    turns: list[dict[str, Any]]


@dataclass
class Summary:
    agent: str
    model: str
    runs: int
    passed: int
    pass_rate: float
    safety_violations: int
    errors: int
    mean_seconds: float
    mean_llm_calls: float
    mean_cost_usd: float | None
    total_cost_usd: float | None
    passed_by_scenario: dict[str, int] = field(default_factory=dict)


def run_benchmark(
    scenarios: list[Scenario],
    setups: list[Setup],
    repeats: int,
    *,
    make_llm: Callable[[str], ChatModel],
    agents: dict[str, AgentFactory],
    transaction: TransactionFactory,
    on_result: Callable[[RunResult], None] = lambda result: None,
) -> list[RunResult]:
    """Runs one after the other, each on freshly reset demo data."""
    results = []
    for setup in setups:
        for scenario in scenarios:
            for repeat in range(1, repeats + 1):
                with transaction() as session:
                    reset_demo(session)
                llm = MeteredModel(make_llm(setup.model))
                transcript = run_scenario(agents[setup.agent](llm), scenario)
                with transaction() as session:
                    result = _record(
                        setup, repeat, transcript, score(transcript, scenario, session), llm
                    )
                on_result(result)
                results.append(result)
    return results


def summarize(results: list[RunResult]) -> list[Summary]:
    summaries = []
    setups = dict.fromkeys((r.agent, r.model) for r in results)
    for agent, model in setups:
        runs = [r for r in results if (r.agent, r.model) == (agent, model)]
        costs = [r.cost_usd for r in runs]
        known = all(cost is not None for cost in costs)
        total = sum(cost for cost in costs if cost is not None)
        passed_by_scenario: dict[str, int] = {}
        for run in runs:
            passed_by_scenario[run.scenario_id] = (
                passed_by_scenario.get(run.scenario_id, 0) + run.passed
            )
        passed = sum(run.passed for run in runs)
        summaries.append(
            Summary(
                agent=agent,
                model=model,
                runs=len(runs),
                passed=passed,
                pass_rate=passed / len(runs),
                safety_violations=sum(len(run.safety_violations) for run in runs),
                errors=sum(run.error is not None for run in runs),
                mean_seconds=mean(run.seconds for run in runs),
                mean_llm_calls=mean(run.llm_calls for run in runs),
                mean_cost_usd=total / len(runs) if known else None,
                total_cost_usd=total if known else None,
                passed_by_scenario=passed_by_scenario,
            )
        )
    return summaries


def report(scenarios: list[Scenario], repeats: int, results: list[RunResult]) -> dict[str, Any]:
    """Everything the results page needs, as plain JSON-ready data."""
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "repeats": repeats,
        "scenarios": [
            {"id": s.id, "title": s.title, "description": s.description.strip()} for s in scenarios
        ],
        "summaries": [asdict(summary) for summary in summarize(results)],
        "runs": [asdict(result) for result in results],
    }


def _record(
    setup: Setup, repeat: int, transcript: Transcript, result: Score, llm: MeteredModel
) -> RunResult:
    return RunResult(
        agent=setup.agent,
        model=setup.model,
        scenario_id=result.scenario_id,
        repeat=repeat,
        passed=result.passed,
        safety_violations=[check.name for check in result.safety_violations],
        checks=[
            {"name": c.name, "passed": c.passed, "detail": c.detail, "safety": c.safety}
            for c in result.checks
        ],
        seconds=round(transcript.seconds, 2),
        llm_calls=llm.calls,
        prompt_tokens=llm.prompt_tokens,
        completion_tokens=llm.completion_tokens,
        cost_usd=round(llm.cost_usd, 6) if llm.cost_known else None,
        error=transcript.error,
        turns=[
            {
                "technician": turn.technician,
                "reply": turn.reply,
                "tools": [
                    {"name": e.name, "ok": e.ok, "confirmed": e.confirmed} for e in turn.events
                ],
                "pending": turn.pending,
                "seconds": round(turn.seconds, 2),
            }
            for turn in transcript.turns
        ],
    )
