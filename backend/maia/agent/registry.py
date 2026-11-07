"""The tools the agent can call: their arguments, their JSON schema for the LLM, whether
they need the technician's confirmation, and how to run them."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from maia.db.models import Priority
from maia.manual.embeddings import Embedder
from maia.tools import assets, manual, reports, steps, stock, work_orders


@dataclass(frozen=True)
class ToolContext:
    session: Session
    embedder: Embedder
    session_id: str


# ---------- Arguments the LLM must provide, validated by Pydantic ----------


class SearchManualArgs(BaseModel):
    query: str = Field(description="What to look up, in natural language.")


class GetAssetArgs(BaseModel):
    asset_id: str = Field(description="Component id, for example RV200-014-B2.")


class CheckStockArgs(BaseModel):
    part_number: str = Field(description="Spare part number, for example BP-2207.")


class LogStepArgs(BaseModel):
    vehicle_id: str = Field(description="Vehicle id, for example RV200-014.")
    procedure_code: str = Field(description="Manual section code, for example PROC-BRK-01.")
    step: int = Field(ge=1, description="Step number from the manual.")
    asset_id: str | None = Field(default=None, description="Component id, if the step has one.")
    reading: float | None = Field(default=None, description="Measured value, if any.")
    unit: str | None = Field(default=None, description="Unit of the reading, for example mm.")
    note: str | None = Field(default=None, description="Anything the technician observed.")


class PartRequest(BaseModel):
    part_number: str = Field(description="Spare part number.")
    quantity: int = Field(ge=1, description="How many to reserve.")


class CreateWorkOrderArgs(BaseModel):
    vehicle_id: str = Field(description="Vehicle id.")
    procedure_code: str = Field(description="Manual section the work order comes from.")
    priority: Priority = Field(description="low, medium or high, following SAF-02.")
    description: str = Field(description="What must be done.")
    asset_id: str | None = Field(default=None, description="Component id, if any.")
    parts: list[PartRequest] = Field(
        default_factory=list, description="Spare parts to reserve for this work order."
    )


class ReservePartsArgs(BaseModel):
    work_order_id: int = Field(description="Id of an open work order.")
    part_number: str = Field(description="Spare part number.")
    quantity: int = Field(ge=1, description="How many to reserve.")


class NoArgs(BaseModel):
    pass


# ---------- Running each tool ----------

ToolResult = BaseModel | list[BaseModel] | dict[str, Any]


def _search_manual(ctx: ToolContext, args: SearchManualArgs) -> ToolResult:
    return list(manual.search_manual(ctx.session, ctx.embedder, args.query))


def _get_asset(ctx: ToolContext, args: GetAssetArgs) -> ToolResult:
    return assets.get_asset(ctx.session, args.asset_id)


def _check_stock(ctx: ToolContext, args: CheckStockArgs) -> ToolResult:
    return stock.check_stock(ctx.session, args.part_number)


def _log_step(ctx: ToolContext, args: LogStepArgs) -> ToolResult:
    return steps.log_step(ctx.session, session_id=ctx.session_id, **args.model_dump())


def _create_work_order(ctx: ToolContext, args: CreateWorkOrderArgs) -> ToolResult:
    """Open the work order and reserve its parts in the same transaction: if any part is
    unavailable, nothing is created."""
    order = work_orders.create_work_order(
        ctx.session,
        session_id=ctx.session_id,
        vehicle_id=args.vehicle_id,
        asset_id=args.asset_id,
        procedure_code=args.procedure_code,
        priority=args.priority,
        description=args.description,
    )
    reservations = [
        stock.reserve_parts(ctx.session, order.work_order_id, part.part_number, part.quantity)
        for part in args.parts
    ]
    return {
        "work_order": order.model_dump(mode="json"),
        "reservations": [r.model_dump(mode="json") for r in reservations],
    }


def _reserve_parts(ctx: ToolContext, args: ReservePartsArgs) -> ToolResult:
    return stock.reserve_parts(ctx.session, args.work_order_id, args.part_number, args.quantity)


def _shift_report(ctx: ToolContext, args: NoArgs) -> ToolResult:
    return reports.generate_shift_report(ctx.session, ctx.session_id)


# ---------- Plain-language summaries shown when asking for confirmation ----------


def _describe_work_order(args: CreateWorkOrderArgs) -> str:
    target = args.asset_id or args.vehicle_id
    text = f"Open a {args.priority.value} priority work order on {target}: {args.description}"
    if args.parts:
        parts = ", ".join(f"{p.quantity} x {p.part_number}" for p in args.parts)
        text += f" (reserve {parts})"
    return text


def _describe_reservation(args: ReservePartsArgs) -> str:
    return f"Reserve {args.quantity} x {args.part_number} for work order {args.work_order_id}"


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    args_model: type[BaseModel]
    run: Callable[[ToolContext, Any], ToolResult]
    requires_confirmation: bool = False
    describe: Callable[[Any], str] | None = None

    def schema(self) -> dict[str, Any]:
        """The tool in the OpenAI function-calling format, which LiteLLM converts per provider."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": clean_schema(self.args_model.model_json_schema()),
            },
        }


TOOLS: dict[str, AgentTool] = {
    tool.name: tool
    for tool in [
        AgentTool(
            "search_manual",
            "Search the RV-200 maintenance manual. Returns the closest sections, best first.",
            SearchManualArgs,
            _search_manual,
        ),
        AgentTool(
            "get_asset",
            "Get a component's details, its vehicle's status and its open work orders.",
            GetAssetArgs,
            _get_asset,
        ),
        AgentTool(
            "check_stock",
            "Get how many of a spare part are on hand, reserved and available.",
            CheckStockArgs,
            _check_stock,
        ),
        AgentTool(
            "log_step",
            "Record a completed procedure step, with its measurement if it has one.",
            LogStepArgs,
            _log_step,
        ),
        AgentTool(
            "create_work_order",
            "Open a work order, optionally reserving its spare parts. Needs confirmation.",
            CreateWorkOrderArgs,
            _create_work_order,
            requires_confirmation=True,
            describe=_describe_work_order,
        ),
        AgentTool(
            "reserve_parts",
            "Reserve spare parts for an existing open work order. Needs confirmation.",
            ReservePartsArgs,
            _reserve_parts,
            requires_confirmation=True,
            describe=_describe_reservation,
        ),
        AgentTool(
            "generate_shift_report",
            "Summarise the steps logged and work orders opened in this session.",
            NoArgs,
            _shift_report,
        ),
    ]
}


def clean_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a Pydantic JSON schema simple enough for every provider: inline $ref
    definitions, turn optional fields (anyOf with null) into plain types, drop titles."""
    definitions = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = resolve(definitions[node["$ref"].split("/")[-1]])
            return {**target, **resolve({k: v for k, v in node.items() if k != "$ref"})}
        if "anyOf" in node:
            options = [o for o in node["anyOf"] if o.get("type") != "null"]
            merged = {**resolve(options[0]), **{k: v for k, v in node.items() if k != "anyOf"}}
            return resolve(merged)
        return {
            key: resolve(value)
            for key, value in node.items()
            if key not in {"title", "$defs", "default"}
        }

    cleaned: dict[str, Any] = resolve(schema)
    return cleaned


def to_json(result: ToolResult) -> Any:
    """A tool result as plain JSON data, for the LLM, the API and MCP clients."""
    if isinstance(result, BaseModel):
        return result.model_dump(mode="json")
    if isinstance(result, list):
        return [item.model_dump(mode="json") for item in result]
    return result
