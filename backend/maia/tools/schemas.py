"""What each tool returns. Pydantic models give the agent a predictable, typed answer and
can be turned into JSON for the LLM."""

from datetime import date, datetime

from pydantic import BaseModel

from maia.db.models import Priority, VehicleStatus, WorkOrderStatus


class AssetInfo(BaseModel):
    asset_id: str
    vehicle_id: str
    vehicle_status: VehicleStatus
    kind: str
    name: str
    last_inspected_on: date | None
    open_work_orders: int


class StockInfo(BaseModel):
    part_number: str
    name: str
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    location: str


class WorkOrderInfo(BaseModel):
    work_order_id: int
    vehicle_id: str
    asset_id: str | None
    procedure_code: str
    priority: Priority
    status: WorkOrderStatus
    description: str
    created_at: datetime


class ReservationInfo(BaseModel):
    work_order_id: int
    part_number: str
    quantity: int
    quantity_available_after: int


class StepLogged(BaseModel):
    step_log_id: int
    procedure_code: str
    step: int
    reading: float | None
    unit: str | None


class ShiftReport(BaseModel):
    session_id: str
    steps: list[StepLogged]
    work_orders: list[WorkOrderInfo]
    summary: str
