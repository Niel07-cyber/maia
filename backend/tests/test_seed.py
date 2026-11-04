from sqlalchemy import func, select
from sqlalchemy.orm import Session

from maia.db import seed_data
from maia.db.models import Asset, Part, Priority, Vehicle, WorkOrder
from maia.db.seed import reset_demo, seed


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_loads_reference_data(db_session: Session) -> None:
    seed(db_session)
    db_session.flush()

    assert count(db_session, Vehicle) == len(seed_data.VEHICLE_IDS)
    assert count(db_session, Asset) == len(seed_data.assets())
    assert count(db_session, Part) == len(seed_data.parts())


def test_seed_is_idempotent(db_session: Session) -> None:
    seed(db_session)
    seed(db_session)
    db_session.flush()

    assert count(db_session, Vehicle) == len(seed_data.VEHICLE_IDS)
    assert count(db_session, Asset) == len(seed_data.assets())


def test_reset_removes_work_orders_and_restores_stock(db_session: Session) -> None:
    seed(db_session)
    db_session.flush()
    brake_pads = db_session.get_one(Part, "BP-2207")
    brake_pads.quantity_reserved = 2
    db_session.add(
        WorkOrder(
            vehicle_id="RV200-014",
            procedure_code="PROC-BRK-01",
            priority=Priority.HIGH,
            description="test",
        )
    )
    db_session.flush()

    reset_demo(db_session)
    db_session.flush()

    assert count(db_session, WorkOrder) == 0
    assert db_session.get_one(Part, "BP-2207").quantity_reserved == 0
