"""Summarise a technician's session for the shift supervisor."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from maia.db.models import StepLog, WorkOrder
from maia.tools.schemas import ShiftReport
from maia.tools.steps import to_step_logged
from maia.tools.work_orders import to_work_order_info


def generate_shift_report(session: Session, session_id: str) -> ShiftReport:
    """Collect every step logged and work order opened during one session."""
    steps = session.scalars(
        select(StepLog).where(StepLog.session_id == session_id).order_by(StepLog.id)
    ).all()
    orders = session.scalars(
        select(WorkOrder).where(WorkOrder.session_id == session_id).order_by(WorkOrder.id)
    ).all()

    readings = sum(1 for s in steps if s.reading is not None)
    summary = (
        f"{len(steps)} step(s) logged, {readings} with a measurement; "
        f"{len(orders)} work order(s) opened."
    )
    return ShiftReport(
        session_id=session_id,
        steps=[to_step_logged(s) for s in steps],
        work_orders=[to_work_order_info(o) for o in orders],
        summary=summary,
    )
