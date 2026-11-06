import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from maia.db import seed_data
from maia.db.models import MeasurementLimit, Priority
from maia.db.seed import seed
from maia.tools.assessment import Band, assess
from maia.tools.errors import ToolError
from maia.tools.steps import log_step

BRAKE_PADS = MeasurementLimit(
    procedure_code="PROC-BRK-01",
    step=4,
    measurement="brake pad friction material thickness",
    unit="mm",
    warning=7,
    minimum=5,
    critical=3,
    part_number="BP-2207",
    part_quantity=2,
)


@pytest.mark.parametrize(
    ("reading", "band", "priority", "withdraw"),
    [
        (12, Band.WITHIN_LIMITS, None, False),
        (7, Band.WITHIN_LIMITS, None, False),  # on the warning limit: within limits
        (6, Band.BELOW_WARNING, Priority.MEDIUM, False),
        (5, Band.BELOW_WARNING, Priority.MEDIUM, False),  # on the minimum limit: medium
        (4, Band.BELOW_MINIMUM, Priority.HIGH, False),
        (3.1, Band.BELOW_MINIMUM, Priority.HIGH, False),
        (3, Band.AT_OR_BELOW_CRITICAL, None, True),  # on the critical limit: withdraw
        (1.5, Band.AT_OR_BELOW_CRITICAL, None, True),
    ],
)
def test_readings_follow_saf_02(
    reading: float, band: Band, priority: Priority | None, withdraw: bool
) -> None:
    assessment = assess(BRAKE_PADS, reading)

    assert assessment.band == band
    assert assessment.work_order_priority == priority
    assert assessment.withdraw_from_service is withdraw


def test_work_orders_include_the_replacement_parts() -> None:
    assessment = assess(BRAKE_PADS, 4)

    assert [(p.part_number, p.quantity) for p in assessment.parts] == [("BP-2207", 2)]
    assert "Do not withdraw" in assessment.required_action


def test_withdrawal_reserves_no_parts_by_itself() -> None:
    assessment = assess(BRAKE_PADS, 2)

    assert assessment.parts == []
    assert "OUT OF SERVICE" in assessment.required_action


def test_log_step_returns_the_assessment_for_a_measured_step(depot: Session) -> None:
    logged = log_step(
        depot,
        session_id="s1",
        vehicle_id="RV200-014",
        asset_id="RV200-014-B2",
        procedure_code="PROC-BRK-01",
        step=4,
        reading=4,
        unit="mm",
    )

    assert logged.assessment is not None
    assert logged.assessment.work_order_priority == Priority.HIGH
    assert logged.assessment.withdraw_from_service is False


def test_log_step_has_no_assessment_for_a_step_without_limits(depot: Session) -> None:
    logged = log_step(
        depot, session_id="s1", vehicle_id="RV200-014", procedure_code="PROC-BRK-01", step=2
    )

    assert logged.assessment is None


def test_log_step_rejects_the_wrong_unit(depot: Session) -> None:
    with pytest.raises(ToolError, match="must be in mm"):
        log_step(
            depot,
            session_id="s1",
            vehicle_id="RV200-014",
            procedure_code="PROC-BRK-01",
            step=4,
            reading=0.4,
            unit="cm",
        )


def test_seed_loads_the_limits_once(db_session: Session) -> None:
    seed(db_session)
    seed(db_session)
    db_session.flush()

    count = db_session.scalar(select(func.count()).select_from(MeasurementLimit))
    assert count == len(seed_data.measurement_limits())
