"""Open corrective maintenance work orders."""

from sqlalchemy.orm import Session

from maia.db.models import Asset, Priority, Vehicle, WorkOrder
from maia.tools.errors import ToolError
from maia.tools.schemas import WorkOrderInfo


def create_work_order(
    session: Session,
    *,
    vehicle_id: str,
    procedure_code: str,
    priority: Priority,
    description: str,
    asset_id: str | None = None,
    session_id: str | None = None,
) -> WorkOrderInfo:
    """Open a work order on a vehicle, optionally on one of its components."""
    if session.get(Vehicle, vehicle_id) is None:
        raise ToolError(f"Unknown vehicle '{vehicle_id}'.")
    if asset_id is not None:
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise ToolError(f"Unknown asset '{asset_id}'.")
        if asset.vehicle_id != vehicle_id:
            raise ToolError(f"Asset '{asset_id}' does not belong to vehicle '{vehicle_id}'.")
    if not description.strip():
        raise ToolError("A work order needs a description.")

    order = WorkOrder(
        session_id=session_id,
        vehicle_id=vehicle_id,
        asset_id=asset_id,
        procedure_code=procedure_code,
        priority=priority,
        description=description.strip(),
    )
    session.add(order)
    session.flush()  # assigns the id and server-side defaults
    session.refresh(order)
    return to_work_order_info(order)


def to_work_order_info(order: WorkOrder) -> WorkOrderInfo:
    return WorkOrderInfo(
        work_order_id=order.id,
        vehicle_id=order.vehicle_id,
        asset_id=order.asset_id,
        procedure_code=order.procedure_code,
        priority=order.priority,
        status=order.status,
        description=order.description,
        created_at=order.created_at,
    )
