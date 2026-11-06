"""Record procedure steps as the technician completes them."""

from sqlalchemy.orm import Session

from maia.db.models import Asset, MeasurementLimit, StepLog, Vehicle
from maia.tools.assessment import assess
from maia.tools.errors import ToolError
from maia.tools.schemas import StepLogged


def log_step(
    session: Session,
    *,
    session_id: str,
    vehicle_id: str,
    procedure_code: str,
    step: int,
    asset_id: str | None = None,
    reading: float | None = None,
    unit: str | None = None,
    note: str | None = None,
) -> StepLogged:
    """Record that a step is done, with the measured value if the step has one. For steps
    the manual gives limits for, the result includes an assessment of the reading."""
    if step < 1:
        raise ToolError("Step numbers start at 1.")
    if session.get(Vehicle, vehicle_id) is None:
        raise ToolError(f"Unknown vehicle '{vehicle_id}'.")
    if asset_id is not None and session.get(Asset, asset_id) is None:
        raise ToolError(f"Unknown asset '{asset_id}'.")
    if (reading is None) != (unit is None):
        raise ToolError("A reading and its unit must be given together.")
    limit = session.get(MeasurementLimit, (procedure_code, step))
    if limit is not None and unit is not None and unit != limit.unit:
        raise ToolError(f"Readings for {procedure_code} step {step} must be in {limit.unit}.")

    entry = StepLog(
        session_id=session_id,
        vehicle_id=vehicle_id,
        asset_id=asset_id,
        procedure_code=procedure_code,
        step=step,
        reading=reading,
        unit=unit,
        note=note,
    )
    session.add(entry)
    session.flush()
    logged = to_step_logged(entry)
    if limit is not None and reading is not None:
        logged.assessment = assess(limit, reading)
    return logged


def to_step_logged(entry: StepLog) -> StepLogged:
    return StepLogged(
        step_log_id=entry.id,
        procedure_code=entry.procedure_code,
        step=entry.step,
        reading=entry.reading,
        unit=entry.unit,
    )
