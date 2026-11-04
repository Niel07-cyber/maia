import pytest
from sqlalchemy.orm import Session

from maia.db.models import Priority, WorkOrderStatus
from maia.tools.errors import ToolError
from maia.tools.reports import generate_shift_report
from maia.tools.steps import log_step
from maia.tools.work_orders import create_work_order


def test_create_work_order_opens_it(depot: Session) -> None:
    order = create_work_order(
        depot,
        vehicle_id="RV200-014",
        asset_id="RV200-014-B2",
        procedure_code="PROC-BRK-01",
        priority=Priority.HIGH,
        description="  Replace brake pads  ",
    )

    assert order.status == WorkOrderStatus.OPEN
    assert order.description == "Replace brake pads"
    assert order.created_at is not None


def test_create_work_order_rejects_asset_of_another_vehicle(depot: Session) -> None:
    with pytest.raises(ToolError, match="does not belong"):
        create_work_order(
            depot,
            vehicle_id="RV200-014",
            asset_id="RV200-027-B2",
            procedure_code="PROC-BRK-01",
            priority=Priority.HIGH,
            description="Replace brake pads",
        )


def test_create_work_order_requires_description(depot: Session) -> None:
    with pytest.raises(ToolError, match="description"):
        create_work_order(
            depot,
            vehicle_id="RV200-014",
            procedure_code="PROC-BRK-01",
            priority=Priority.LOW,
            description="   ",
        )


def test_log_step_records_reading(depot: Session) -> None:
    logged = log_step(
        depot,
        session_id="s1",
        vehicle_id="RV200-014",
        asset_id="RV200-014-B2",
        procedure_code="PROC-BRK-01",
        step=4,
        reading=4.0,
        unit="mm",
    )

    assert logged.step == 4
    assert logged.reading == 4.0


def test_log_step_requires_reading_and_unit_together(depot: Session) -> None:
    with pytest.raises(ToolError, match="together"):
        log_step(
            depot,
            session_id="s1",
            vehicle_id="RV200-014",
            procedure_code="PROC-BRK-01",
            step=4,
            reading=4.0,
        )


def test_log_step_rejects_step_zero(depot: Session) -> None:
    with pytest.raises(ToolError, match="start at 1"):
        log_step(depot, session_id="s1", vehicle_id="RV200-014", procedure_code="X", step=0)


def test_shift_report_collects_only_this_session(depot: Session) -> None:
    log_step(depot, session_id="s1", vehicle_id="RV200-014", procedure_code="PROC-BRK-01", step=1)
    log_step(
        depot,
        session_id="s1",
        vehicle_id="RV200-014",
        procedure_code="PROC-BRK-01",
        step=4,
        reading=4.0,
        unit="mm",
    )
    log_step(depot, session_id="other", vehicle_id="RV200-027", procedure_code="X", step=1)
    create_work_order(
        depot,
        session_id="s1",
        vehicle_id="RV200-014",
        procedure_code="PROC-BRK-01",
        priority=Priority.HIGH,
        description="Replace brake pads",
    )

    report = generate_shift_report(depot, "s1")

    assert len(report.steps) == 2
    assert len(report.work_orders) == 1
    assert report.summary == "2 step(s) logged, 1 with a measurement; 1 work order(s) opened."
