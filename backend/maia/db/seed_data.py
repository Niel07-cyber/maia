"""Fictional reference data for the demo depot. Values match the RV-200 manual."""

from datetime import date

from maia.db.models import Asset, MeasurementLimit, Part, Vehicle, VehicleStatus

DEPOT = "Mons North Depot (fictional)"
VEHICLE_IDS = ("RV200-014", "RV200-027")


def vehicles() -> list[Vehicle]:
    return [
        Vehicle(id=vehicle_id, model="RV-200", depot=DEPOT, status=VehicleStatus.IN_SERVICE)
        for vehicle_id in VEHICLE_IDS
    ]


def assets() -> list[Asset]:
    """The same set of maintainable components on every vehicle."""
    components = [
        ("B1", "bogie", "Front bogie B1"),
        ("B2", "bogie", "Rear bogie B2"),
        ("WS1", "wheelset", "Wheelset 1 (bogie B1)"),
        ("WS2", "wheelset", "Wheelset 2 (bogie B1)"),
        ("WS3", "wheelset", "Wheelset 3 (bogie B2)"),
        ("WS4", "wheelset", "Wheelset 4 (bogie B2)"),
        ("PAN", "pantograph", "Roof pantograph"),
        ("BAT", "battery_box", "110 V auxiliary battery box"),
        ("D1", "door", "Passenger door 1 (left)"),
        ("D2", "door", "Passenger door 2 (right)"),
    ]
    return [
        Asset(
            id=f"{vehicle_id}-{code}",
            vehicle_id=vehicle_id,
            kind=kind,
            name=name,
            last_inspected_on=date(2026, 10, 26),
        )
        for vehicle_id in VEHICLE_IDS
        for code, kind, name in components
    ]


def parts() -> list[Part]:
    """Spare-part stock. The door sensor is deliberately out of stock, to test how the agent
    handles a missing part. quantity_reserved is set explicitly so a reset clears it: merge()
    only copies attributes that are set."""
    stock = [
        ("BP-2207", "Brake pad", 6, "Store A3"),
        ("CS-1130", "Pantograph carbon strip", 2, "Store B1"),
        ("BF-125", "Battery main fuse", 4, "Store C2"),
        ("DS-450", "Door obstacle sensor", 0, "Store D4"),
    ]
    return [
        Part(
            part_number=part_number,
            name=name,
            quantity_on_hand=on_hand,
            quantity_reserved=0,
            location=location,
        )
        for part_number, name, on_hand, location in stock
    ]


def measurement_limits() -> list[MeasurementLimit]:
    """Limits copied from the RV-200 manual, one row per measured step. Measurements whose
    limits are a range (door opening time, flange height) have no SAF-02 bands and are left to
    the manual."""
    return [
        MeasurementLimit(
            procedure_code="PROC-BRK-01",
            step=4,
            measurement="brake pad friction material thickness",
            unit="mm",
            warning=7,
            minimum=5,
            critical=3,
            part_number="BP-2207",
            part_quantity=2,
        ),
        MeasurementLimit(
            procedure_code="PROC-WHL-02",
            step=3,
            measurement="wheel flange thickness",
            unit="mm",
            warning=27.5,
            minimum=26,
            critical=24,
            part_number=None,
            part_quantity=None,
        ),
        MeasurementLimit(
            procedure_code="PROC-PAN-03",
            step=4,
            measurement="pantograph carbon strip thickness",
            unit="mm",
            warning=8,
            minimum=5,
            critical=3,
            part_number="CS-1130",
            part_quantity=1,
        ),
        MeasurementLimit(
            procedure_code="PROC-BAT-04",
            step=3,
            measurement="battery standby voltage",
            unit="V",
            warning=100,
            minimum=96,
            critical=90,
            part_number=None,
            part_quantity=None,
        ),
    ]
