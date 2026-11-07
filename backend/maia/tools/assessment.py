"""Classify a measurement against the manual's limits and apply the escalation rules (SAF-02).

This is deliberately plain code, not a model decision: the same reading must always lead to
the same safety action.

SAF-02, for measurements where lower is worse:
- below the critical limit: withdraw the vehicle from service and notify the supervisor
- below the minimum limit, above the critical limit: work order, priority high, before the
  next service run
- between the minimum and the warning limit: work order, priority medium, within 7 days

Readings exactly on a limit fall on the safer side: on the critical limit means withdraw, on
the minimum limit means medium, on the warning limit means within limits."""

import enum

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from maia.db.models import MeasurementLimit, Priority, StepLog


class Band(enum.StrEnum):
    WITHIN_LIMITS = "within_limits"
    BELOW_WARNING = "below_warning"
    BELOW_MINIMUM = "below_minimum"
    AT_OR_BELOW_CRITICAL = "at_or_below_critical"


class PartToReserve(BaseModel):
    part_number: str
    quantity: int


class Assessment(BaseModel):
    measurement: str
    reading: float
    unit: str
    band: Band
    limits: str
    withdraw_from_service: bool
    work_order_priority: Priority | None
    parts: list[PartToReserve]
    required_action: str


def assess(limit: MeasurementLimit, reading: float) -> Assessment:
    if reading <= limit.critical:
        band = Band.AT_OR_BELOW_CRITICAL
    elif reading < limit.minimum:
        band = Band.BELOW_MINIMUM
    elif reading < limit.warning:
        band = Band.BELOW_WARNING
    else:
        band = Band.WITHIN_LIMITS

    priority = {Band.BELOW_MINIMUM: Priority.HIGH, Band.BELOW_WARNING: Priority.MEDIUM}.get(band)
    parts = (
        [PartToReserve(part_number=limit.part_number, quantity=limit.part_quantity)]
        if priority is not None and limit.part_number and limit.part_quantity
        else []
    )
    return Assessment(
        measurement=limit.measurement,
        reading=reading,
        unit=limit.unit,
        band=band,
        limits=(
            f"warning {limit.warning:g} {limit.unit}, minimum {limit.minimum:g} {limit.unit}, "
            f"critical {limit.critical:g} {limit.unit} ({limit.procedure_code})"
        ),
        withdraw_from_service=band == Band.AT_OR_BELOW_CRITICAL,
        work_order_priority=priority,
        parts=parts,
        required_action=_REQUIRED_ACTION[band],
    )


_REQUIRED_ACTION = {
    Band.WITHIN_LIMITS: "None. The reading is within limits.",
    Band.BELOW_WARNING: (
        "Open a work order with priority medium, to be done within 7 days (SAF-02)."
    ),
    Band.BELOW_MINIMUM: (
        "Open a work order with priority high, to be done before the next service run (SAF-02). "
        "Do not withdraw the vehicle from service."
    ),
    Band.AT_OR_BELOW_CRITICAL: (
        "Stop the procedure, withdraw the vehicle from service, tag it OUT OF SERVICE and notify "
        "the shift supervisor immediately (SAF-02)."
    ),
}


def withdrawing_reading(session: Session, session_id: str, vehicle_id: str) -> StepLog | None:
    """The first reading logged in this session that put the vehicle at or below a critical
    limit, if any. From then on the procedure is stopped (SAF-02)."""
    readings = session.scalars(
        select(StepLog)
        .where(
            StepLog.session_id == session_id,
            StepLog.vehicle_id == vehicle_id,
            StepLog.reading.is_not(None),
        )
        .order_by(StepLog.id)
    )
    for entry in readings:
        limit = session.get(MeasurementLimit, (entry.procedure_code, entry.step))
        if (
            limit is not None
            and entry.reading is not None
            and entry.unit == limit.unit
            and assess(limit, entry.reading).withdraw_from_service
        ):
            return entry
    return None
