"""MAIA's depot tools over the Model Context Protocol (MCP).

Any MCP client (Claude Desktop, an IDE, another agent) can search the RV-200 manual, look up
assets and stock, log steps and open work orders, with the same validation and safety rules
as the MAIA chat. The tools come from the same registry, so there is one definition of each.

Run it with:  uv run python -m maia.mcp_server   (stdio transport)
"""

import json
import uuid
from typing import Any

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from pydantic import ValidationError

from maia.agent.agent import TransactionFactory
from maia.agent.registry import TOOLS, AgentTool, ToolContext, to_json
from maia.manual.embeddings import Embedder
from maia.tools.errors import ToolError

INSTRUCTIONS = (
    "Tools for the fictional RV-200 railcar depot. Search the manual before stating any "
    "procedure, limit or part number. Start every procedure with lockout/tagout (SAF-01). "
    "Tools that change records need the user's approval: ask before calling them."
)


# Tools that only read: MCP clients may run these without asking the user.
READ_ONLY = {"search_manual", "get_asset", "check_stock", "generate_shift_report"}


def describe(tool: AgentTool) -> types.Tool:
    """An MCP tool definition from our registry entry."""
    read_only = tool.name in READ_ONLY
    description = tool.description
    if tool.requires_confirmation:
        description += " Only call this after the user has explicitly approved it."
    return types.Tool(
        name=tool.name,
        description=description,
        input_schema=tool.args_model.model_json_schema(),
        annotations=types.ToolAnnotations(
            read_only_hint=read_only,
            destructive_hint=False,
            idempotent_hint=read_only,
            open_world_hint=False,
        ),
    )


def build_server(
    embedder: Embedder, transaction: TransactionFactory, session_id: str | None = None
) -> Server[Any]:
    """One server per connection; its steps and work orders share one session id, like a
    chat conversation."""
    session_id = session_id or f"mcp-{uuid.uuid4().hex[:12]}"

    def run(name: str, arguments: dict[str, Any]) -> tuple[Any, bool]:
        tool = TOOLS.get(name)
        if tool is None:
            return {"error": f"There is no tool called '{name}'."}, False
        try:
            args = tool.args_model.model_validate(arguments)
            with transaction() as session:
                return to_json(tool.run(ToolContext(session, embedder, session_id), args)), True
        except ValidationError as exc:
            return {"error": f"Invalid arguments: {exc.errors(include_url=False)}"}, False
        except ToolError as exc:
            return {"error": str(exc)}, False

    async def list_tools(
        context: Any, params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[describe(tool) for tool in TOOLS.values()])

    async def call_tool(context: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        # Database and embedding calls are blocking: run them off the event loop.
        result, ok = await anyio.to_thread.run_sync(run, params.name, params.arguments or {})
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, indent=2))],
            is_error=not ok,
        )

    return Server(
        "maia",
        version="0.1.0",
        instructions=INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def _serve() -> None:
    from maia.db.session import transaction
    from maia.manual.embeddings import LiteLLMEmbedder

    server = build_server(LiteLLMEmbedder(), transaction)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(_serve)
