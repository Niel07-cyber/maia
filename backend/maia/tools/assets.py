"""Look up a vehicle component."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from maia.db.models import Asset, WorkOrder, WorkOrderStatus
from maia.tools.errors import ToolError
from maia.tools.schemas import AssetInfo


def get_asset(session: Session, asset_id: str) -> AssetInfo:
    """Return a component's details, its vehicle's status and how many work orders are open
    on it. Asset ids look like "RV200-014-B2" (vehicle id, then component code)."""
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise ToolError(f"Unknown asset '{asset_id}'. Ids look like RV200-014-B2.")

    open_orders = session.scalar(
        select(func.count())
        .select_from(WorkOrder)
        .where(WorkOrder.asset_id == asset_id, WorkOrder.status == WorkOrderStatus.OPEN)
    )
    return AssetInfo(
        asset_id=asset.id,
        vehicle_id=asset.vehicle_id,
        vehicle_status=asset.vehicle.status,
        kind=asset.kind,
        name=asset.name,
        last_inspected_on=asset.last_inspected_on,
        open_work_orders=open_orders or 0,
    )
