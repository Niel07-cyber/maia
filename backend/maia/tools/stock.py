"""Check and reserve spare parts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from maia.db.models import Part, PartReservation, WorkOrder, WorkOrderStatus
from maia.tools.errors import ToolError
from maia.tools.schemas import ReservationInfo, StockInfo


def check_stock(session: Session, part_number: str) -> StockInfo:
    """Return how many of a spare part are on hand, already reserved, and available."""
    part = session.get(Part, part_number)
    if part is None:
        raise ToolError(f"Unknown part number '{part_number}'.")
    return _stock_info(part)


def reserve_parts(
    session: Session, work_order_id: int, part_number: str, quantity: int
) -> ReservationInfo:
    """Set spare parts aside for an open work order. Fails if there are not enough available.

    The part row is locked (SELECT ... FOR UPDATE) so two reservations made at the same time
    cannot both take the last parts."""
    if quantity < 1:
        raise ToolError("Quantity must be at least 1.")

    work_order = session.get(WorkOrder, work_order_id)
    if work_order is None:
        raise ToolError(f"Work order {work_order_id} does not exist.")
    if work_order.status != WorkOrderStatus.OPEN:
        raise ToolError(f"Work order {work_order_id} is closed.")

    part = session.scalar(select(Part).where(Part.part_number == part_number).with_for_update())
    if part is None:
        raise ToolError(f"Unknown part number '{part_number}'.")
    if part.quantity_available < quantity:
        raise ToolError(
            f"Not enough {part.name} ({part_number}): {part.quantity_available} available, "
            f"{quantity} requested."
        )

    part.quantity_reserved += quantity
    session.add(
        PartReservation(work_order_id=work_order_id, part_number=part_number, quantity=quantity)
    )
    session.flush()
    return ReservationInfo(
        work_order_id=work_order_id,
        part_number=part_number,
        quantity=quantity,
        quantity_available_after=part.quantity_available,
    )


def _stock_info(part: Part) -> StockInfo:
    return StockInfo(
        part_number=part.part_number,
        name=part.name,
        quantity_on_hand=part.quantity_on_hand,
        quantity_reserved=part.quantity_reserved,
        quantity_available=part.quantity_available,
        location=part.location,
    )
