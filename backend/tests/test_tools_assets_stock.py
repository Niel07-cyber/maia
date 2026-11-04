import pytest
from sqlalchemy.orm import Session

from maia.db.models import Priority
from maia.tools.assets import get_asset
from maia.tools.errors import ToolError
from maia.tools.stock import check_stock, reserve_parts
from maia.tools.work_orders import create_work_order


def open_order(depot: Session) -> int:
    order = create_work_order(
        depot,
        vehicle_id="RV200-014",
        asset_id="RV200-014-B2",
        procedure_code="PROC-BRK-01",
        priority=Priority.HIGH,
        description="Replace brake pads",
    )
    return order.work_order_id


def test_get_asset_returns_details(depot: Session) -> None:
    asset = get_asset(depot, "RV200-014-B2")

    assert asset.kind == "bogie"
    assert asset.vehicle_id == "RV200-014"
    assert asset.open_work_orders == 0


def test_get_asset_counts_open_work_orders(depot: Session) -> None:
    open_order(depot)

    assert get_asset(depot, "RV200-014-B2").open_work_orders == 1


def test_get_asset_rejects_unknown_id(depot: Session) -> None:
    with pytest.raises(ToolError, match="Unknown asset"):
        get_asset(depot, "RV200-999-B2")


def test_check_stock_reports_availability(depot: Session) -> None:
    stock = check_stock(depot, "BP-2207")

    assert stock.quantity_available == 6
    assert stock.location == "Store A3"


def test_check_stock_rejects_unknown_part(depot: Session) -> None:
    with pytest.raises(ToolError, match="Unknown part"):
        check_stock(depot, "XX-0000")


def test_reserve_parts_reduces_availability(depot: Session) -> None:
    order_id = open_order(depot)

    reservation = reserve_parts(depot, order_id, "BP-2207", 2)

    assert reservation.quantity_available_after == 4
    assert check_stock(depot, "BP-2207").quantity_reserved == 2


def test_reserve_parts_refuses_when_out_of_stock(depot: Session) -> None:
    order_id = open_order(depot)

    with pytest.raises(ToolError, match="Not enough"):
        reserve_parts(depot, order_id, "DS-450", 1)


def test_reserve_parts_refuses_more_than_available(depot: Session) -> None:
    order_id = open_order(depot)

    with pytest.raises(ToolError, match="6 available, 7 requested"):
        reserve_parts(depot, order_id, "BP-2207", 7)


def test_reserve_parts_requires_existing_work_order(depot: Session) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        reserve_parts(depot, 99999, "BP-2207", 1)


def test_reserve_parts_rejects_zero_quantity(depot: Session) -> None:
    order_id = open_order(depot)

    with pytest.raises(ToolError, match="at least 1"):
        reserve_parts(depot, order_id, "BP-2207", 0)
