from pathlib import Path

import pytest
from pydantic import ValidationError

from maia.agent.registry import TOOLS
from maia.benchmark.scenario import Expectations, Scenario, load_scenario, load_scenarios
from maia.db import seed_data

SCENARIOS = load_scenarios()


def test_scenarios_are_found() -> None:
    assert len(SCENARIOS) >= 3


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_scenario_refers_to_real_tools_and_parts(scenario: Scenario) -> None:
    known_parts = {part.part_number for part in seed_data.parts()}
    assert set(scenario.expect.tools_called) <= TOOLS.keys()
    if scenario.expect.work_order:
        assert set(scenario.expect.work_order.parts) <= known_parts


def test_work_order_and_no_work_order_cannot_both_be_set() -> None:
    with pytest.raises(ValidationError, match="not both"):
        Expectations.model_validate({"work_order": {"priority": "high"}, "no_work_order": True})


def test_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Expectations.model_validate({"step_logged": [1]})


def test_id_must_match_the_file_name(tmp_path: Path) -> None:
    path = tmp_path / "other-name.yaml"
    path.write_text(
        "id: brake-check\ntitle: t\ndescription: d\ntechnician:\n  messages: [hi]\nexpect: {}\n"
    )
    with pytest.raises(ValueError, match="must match the file name"):
        load_scenario(path)
