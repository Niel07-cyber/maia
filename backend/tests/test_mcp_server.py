import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from mcp import Client, types
from sqlalchemy.orm import Session

from maia.agent.registry import TOOLS
from maia.manual.embeddings import Embedder
from maia.mcp_server import READ_ONLY, build_server
from maia.tools.steps import log_step

Transaction = Callable[[], AbstractContextManager[Session]]

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def payload(result: types.CallToolResult) -> Any:
    [content] = result.content
    assert isinstance(content, types.TextContent)
    return json.loads(content.text)


async def test_every_registry_tool_is_offered(embedder: Embedder, transaction: Transaction) -> None:
    async with Client(build_server(embedder, transaction)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert tools.keys() == TOOLS.keys()
    assert tools["check_stock"].annotations is not None
    assert tools["check_stock"].annotations.read_only_hint is True
    assert tools["create_work_order"].annotations is not None
    assert tools["create_work_order"].annotations.read_only_hint is False
    assert "approved" in (tools["create_work_order"].description or "")
    assert tools.keys() >= READ_ONLY


async def test_a_tool_returns_its_result_as_json(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    async with Client(build_server(embedder, transaction)) as client:
        result = await client.call_tool("check_stock", {"part_number": "BP-2207"})

    assert not result.is_error
    assert payload(result)["part_number"] == "BP-2207"


async def test_the_safety_rules_apply_to_mcp_clients_too(
    depot: Session, embedder: Embedder, transaction: Transaction
) -> None:
    log_step(
        depot,
        session_id="mcp-test",
        vehicle_id="RV200-014",
        procedure_code="PROC-BRK-01",
        step=4,
        reading=2,
        unit="mm",
    )
    server = build_server(embedder, transaction, session_id="mcp-test")

    async with Client(server) as client:
        result = await client.call_tool(
            "create_work_order",
            {
                "vehicle_id": "RV200-014",
                "procedure_code": "PROC-BRK-01",
                "priority": "medium",
                "description": "Replace brake pads",
            },
        )

    assert result.is_error
    assert "must be withdrawn from service" in payload(result)["error"]


async def test_bad_calls_are_reported_as_errors(
    embedder: Embedder, transaction: Transaction
) -> None:
    async with Client(build_server(embedder, transaction)) as client:
        unknown = await client.call_tool("open_the_doors", {})
        invalid = await client.call_tool("log_step", {"vehicle_id": "RV200-014"})

    assert unknown.is_error and "no tool called" in payload(unknown)["error"]
    assert invalid.is_error and "Invalid arguments" in payload(invalid)["error"]
