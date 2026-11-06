"""Run the benchmark with the real models and write the results to a JSON file.

Usage:
    uv run python -m maia.benchmark                      # both configured models, 3 repeats
    uv run python -m maia.benchmark --repeats 1 --scenarios ppe-question

Warning: every run resets the demo data (work orders, reservations, logged steps).
"""

import argparse
import json
import logging
from pathlib import Path

from maia.agent.agent import MaintenanceAgent
from maia.agent.llm import ChatModel, LiteLLMChat
from maia.benchmark.benchmark import (
    AgentFactory,
    RunResult,
    Setup,
    report,
    run_benchmark,
    summarize,
)
from maia.benchmark.runner import Agent
from maia.benchmark.scenario import load_scenarios
from maia.config import get_settings
from maia.db.session import transaction
from maia.manual.embeddings import LiteLLMEmbedder


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Benchmark the MAIA agent.")
    parser.add_argument("--models", nargs="+", default=[settings.llm_model, settings.llm_model_alt])
    parser.add_argument("--agents", nargs="+", default=["explicit"])
    parser.add_argument("--scenarios", nargs="+", help="scenario ids (default: all)")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("results/benchmark.json"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    scenarios = load_scenarios()
    if args.scenarios:
        unknown = set(args.scenarios) - {s.id for s in scenarios}
        if unknown:
            parser.error(f"unknown scenarios: {sorted(unknown)}")
        scenarios = [s for s in scenarios if s.id in args.scenarios]

    embedder = LiteLLMEmbedder()

    def explicit(llm: ChatModel) -> Agent:
        return MaintenanceAgent(llm, embedder, transaction)

    agents: dict[str, AgentFactory] = {"explicit": explicit}
    unknown_agents = set(args.agents) - agents.keys()
    if unknown_agents:
        parser.error(f"unknown agents: {sorted(unknown_agents)}")

    setups = [Setup(agent, model) for agent in args.agents for model in args.models]
    total = len(setups) * len(scenarios) * args.repeats
    print(f"Running {total} runs. The demo data is reset before each one.\n")

    results = run_benchmark(
        scenarios,
        setups,
        args.repeats,
        make_llm=lambda model: LiteLLMChat(model),
        agents=agents,
        transaction=transaction,
        on_result=show,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report(scenarios, args.repeats, results), indent=2))

    print()
    for summary in summarize(results):
        cost = f"${summary.total_cost_usd:.4f}" if summary.total_cost_usd is not None else "unknown"
        print(
            f"{summary.agent} / {summary.model}: {summary.passed}/{summary.runs} passed, "
            f"{summary.safety_violations} safety violations, "
            f"{summary.mean_seconds:.1f} s per run, total cost {cost}"
        )
    print(f"\nResults written to {args.output}")


def show(result: RunResult) -> None:
    mark = "PASS" if result.passed else "FAIL"
    cost = f"${result.cost_usd:.4f}" if result.cost_usd is not None else "$?"
    print(
        f"{mark}  {result.model:<24} {result.scenario_id:<24} #{result.repeat}  "
        f"{result.seconds:5.1f}s  {cost}"
    )
    for check in result.checks:
        if not check["passed"]:
            label = "SAFETY" if check["safety"] else "miss"
            print(f"      {label}: {check['name']} ({check['detail']})")


if __name__ == "__main__":
    main()
