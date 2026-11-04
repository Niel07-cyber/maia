"""Database tables for the RV-200 maintenance domain. All data is fictional."""

import enum
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from maia.db.base import Base

EMBEDDING_DIMENSIONS = 1536  # vector size requested from the embedding model


class VehicleStatus(enum.StrEnum):
    IN_SERVICE = "in_service"
    OUT_OF_SERVICE = "out_of_service"


class Priority(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WorkOrderStatus(enum.StrEnum):
    OPEN = "open"
    CLOSED = "closed"


def _str_enum(enum_class: type[enum.StrEnum]) -> Enum:
    """Store enums as plain strings (not native Postgres enums), so adding a value needs no
    database migration."""
    return Enum(
        enum_class,
        native_enum=False,
        length=20,
        values_callable=lambda members: [member.value for member in members],
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # e.g. "RV200-014"
    model: Mapped[str] = mapped_column(String(20))
    depot: Mapped[str] = mapped_column(String(50))
    status: Mapped[VehicleStatus] = mapped_column(
        _str_enum(VehicleStatus), default=VehicleStatus.IN_SERVICE
    )

    assets: Mapped[list["Asset"]] = relationship(back_populates="vehicle")


class Asset(Base):
    """A maintainable component of a vehicle: a bogie, the pantograph, a door, and so on."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)  # e.g. "RV200-014-B2"
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    kind: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    last_inspected_on: Mapped[date | None] = mapped_column(Date)

    vehicle: Mapped[Vehicle] = relationship(back_populates="assets")


class Part(Base):
    """A spare part in the depot store."""

    __tablename__ = "parts"
    __table_args__ = (
        CheckConstraint(
            "quantity_reserved >= 0 AND quantity_reserved <= quantity_on_hand",
            name="stock_within_bounds",
        ),
    )

    part_number: Mapped[str] = mapped_column(String(20), primary_key=True)  # e.g. "BP-2207"
    name: Mapped[str] = mapped_column(String(100))
    quantity_on_hand: Mapped[int]
    quantity_reserved: Mapped[int] = mapped_column(default=0)
    location: Mapped[str] = mapped_column(String(30))

    @property
    def quantity_available(self) -> int:
        return self.quantity_on_hand - self.quantity_reserved


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"))
    procedure_code: Mapped[str] = mapped_column(String(20))
    priority: Mapped[Priority] = mapped_column(_str_enum(Priority))
    status: Mapped[WorkOrderStatus] = mapped_column(
        _str_enum(WorkOrderStatus), default=WorkOrderStatus.OPEN
    )
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reservations: Mapped[list["PartReservation"]] = relationship(back_populates="work_order")


class PartReservation(Base):
    __tablename__ = "part_reservations"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"))
    part_number: Mapped[str] = mapped_column(ForeignKey("parts.part_number"))
    quantity: Mapped[int]

    work_order: Mapped[WorkOrder] = relationship(back_populates="reservations")


class StepLog(Base):
    """One completed procedure step, with its measured value if the step has one."""

    __tablename__ = "step_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"))
    procedure_code: Mapped[str] = mapped_column(String(20))
    step: Mapped[int]
    reading: Mapped[float | None]
    unit: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ManualChunk(Base):
    """One section of the maintenance manual, with its embedding for semantic search."""

    __tablename__ = "manual_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_code: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. "PROC-BRK-01"
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
