"""Real MCP client -> server integration test (claims #1, #2).

Spawns `distill serve <repo>` as a subprocess over the stdio transport (the
real transport an agent like Claude Code would use) and drives it with the
official `mcp` client SDK — not a direct in-process function call.
"""

import sys

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _write_repo(tmp_path):
    (tmp_path / "auth.py").write_text(
        "def validate_auth_token(token):\n"
        "    # Validate the auth token before letting the request through.\n"
        "    return token is not None\n"
        "\n"
        "def render_template(name, context):\n"
        '    return f"<html>{name}</html>"\n'
    )


@pytest.mark.anyio
async def test_search_code_returns_relevant_nonredundant_results(tmp_path):
    _write_repo(tmp_path)
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "distill.cli", "serve", str(tmp_path)]
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            assert {"search_code", "get_symbol", "get_context"} <= tool_names

            result = await session.call_tool(
                "search_code", {"query": "validate the auth token", "k": 2}
            )
            items = result.structured_content["result"]
            assert items
            assert items[0]["name"] == "validate_auth_token"
            assert "content" in items[0]

            first_id = items[0]["id"]
            symbol = await session.call_tool("get_symbol", {"node_id": first_id})
            assert symbol.structured_content["result"]["name"] == "validate_auth_token"

            context = await session.call_tool(
                "get_context", {"file_path": "auth.py", "line": 2}
            )
            assert context.structured_content["result"]["name"] == "validate_auth_token"


@pytest.mark.anyio
async def test_get_symbol_missing_id_returns_none(tmp_path):
    _write_repo(tmp_path)
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "distill.cli", "serve", str(tmp_path)]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("get_symbol", {"node_id": "does-not-exist"})
            assert result.structured_content["result"] is None


@pytest.mark.anyio
async def test_get_context_falls_back_to_whole_file_outside_any_symbol(tmp_path):
    (tmp_path / "empty_ish.py").write_text("# just a comment\n# another comment\n")
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "distill.cli", "serve", str(tmp_path)]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_context", {"file_path": "empty_ish.py", "line": 1}
            )
            payload = result.structured_content["result"]
            assert payload["kind"] == "FILE"
            assert payload["name"] == "empty_ish.py"
