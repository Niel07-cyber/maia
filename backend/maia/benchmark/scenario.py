"""What a benchmark scenario is, and how to load them from YAML files.

A scenario is a scripted technician (what they say, and how they answer confirmation
requests) plus the outcomes we expect. Outcomes are checked from tool calls and the
database, never from how the model phrases its answer."""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from maia.db.models import Priority

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


class Strict(BaseModel):
    # A typo in a YAML key should fail loudly, not be silently ignored.
    model_config = ConfigDict(extra="forbid")


class Technician(Strict):
    messages: list[str] = Field(min_length=1, description="What the technician says, in order.")
    confirm: Literal["approve", "decline"] = Field(
        default="approve", description="How they answer when MAIA asks for confirmation."
    )


class WorkOrderExpectation(Strict):
    priority: Priority
    parts: dict[str, int] = Field(default_factory=dict, description="Part number -> quantity.")


class Expectations(Strict):
    steps_logged: list[int] = Field(default_factory=list, description="Steps that must be logged.")
    work_order: WorkOrderExpectation | None = None
    no_work_order: bool = False
    withdraw: bool | None = Field(
        default=None, description="Whether an assessment must (or must not) withdraw the vehicle."
    )
    tools_called: list[str] = Field(default_factory=list)
    cites: list[str] = Field(default_factory=list, description="Manual sections to mention.")
    mentions: list[str] = Field(default_factory=list, description="Phrases, case-insensitive.")

    @model_validator(mode="after")
    def _work_order_is_consistent(self) -> Self:
        if self.work_order is not None and self.no_work_order:
            raise ValueError("Use either work_order or no_work_order, not both.")
        return self


class Scenario(Strict):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    title: str
    description: str
    technician: Technician
    expect: Expectations


def load_scenario(path: Path) -> Scenario:
    scenario = Scenario.model_validate(yaml.safe_load(path.read_text()))
    if scenario.id != path.stem:
        raise ValueError(f"{path.name}: the id must match the file name ('{path.stem}').")
    return scenario


def load_scenarios(directory: Path = SCENARIOS_DIR) -> list[Scenario]:
    return [load_scenario(path) for path in sorted(directory.glob("*.yaml"))]
