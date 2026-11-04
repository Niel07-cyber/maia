import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from maia.db.models import (
    Asset,
    Part,
    PartReservation,
    Priority,
    Vehicle,
    VehicleStatus,
    WorkOrder,
    WorkOrderStatus,
)


def test_work_order_with_reservation_is_saved(db_session: Session) -> None:
    vehicle = Vehicle(id="RV200-001", model="RV-200", depot="Test depot")
    asset = Asset(id="RV200-001-B2", vehicle=vehicle, kind="bogie", name="Bogie B2")
    part = Part(part_number="BP-2207", name="Brake pad", quantity_on_hand=10, location="A3")
    db_session.add_all([vehicle, asset, part])
    db_session.flush()  # the vehicle, asset and part exist before any work order refers to them

    order = WorkOrder(
        vehicle_id=vehicle.id,
        asset_id=asset.id,
        procedure_code="PROC-BRK-01",
        priority=Priority.HIGH,
        description="Replace brake pads on bogie B2",
    )
    order.reservations.append(PartReservation(part_number=part.part_number, quantity=2))
    db_session.add(order)
    db_session.flush()

    saved = db_session.scalars(select(WorkOrder)).one()

    assert saved.status == WorkOrderStatus.OPEN
    assert saved.created_at is not None
    assert [r.quantity for r in saved.reservations] == [2]
    assert vehicle.status == VehicleStatus.IN_SERVICE


def test_part_cannot_reserve_more_than_on_hand(db_session: Session) -> None:
    db_session.add(
        Part(
            part_number="CS-1130",
            name="Carbon strip",
            quantity_on_hand=1,
            quantity_reserved=2,
            location="B1",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_quantity_available_subtracts_reserved() -> None:
    part = Part(part_number="X", name="X", quantity_on_hand=5, quantity_reserved=2, location="A")

    assert part.quantity_available == 3
