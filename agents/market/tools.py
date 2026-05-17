"""MCP tool helpers for the Market Intelligence Agent."""

from __future__ import annotations

import json
from typing import Any

from protocols.mcp.client import McpClient

# Populated at runtime from tools/list on the MCP server.
AVAILABLE_TOOLS: list[dict[str, Any]] = []


async def load_tools(client: McpClient) -> list[dict[str, Any]]:
    """Refresh AVAILABLE_TOOLS from the Rust MCP server."""
    global AVAILABLE_TOOLS
    await client.initialize()
    AVAILABLE_TOOLS = await client.list_tools()
    return AVAILABLE_TOOLS


def tool_names() -> list[str]:
    return [t.get("name", "") for t in AVAILABLE_TOOLS if t.get("name")]


def format_tools_for_prompt() -> str:
    """Serialize tool schemas for the planning LLM prompt."""
    if not AVAILABLE_TOOLS:
        return "(no tools loaded — call load_tools first)"
    return json.dumps(AVAILABLE_TOOLS, indent=2)


def extract_text_content(mcp_result: dict[str, Any]) -> str:
    """Pull plain text from an MCP tools/call content block list."""
    chunks: list[str] = []
    for block in mcp_result.get("content", []):
        if block.get("type") == "text":
            chunks.append(str(block.get("text", "")))
    return "\n".join(chunks).strip()


async def call_get_quote(client: McpClient, symbol: str) -> dict[str, Any]:
    """Invoke get_quote on mcp-market-data and return parsed quote data."""
    raw = await client.call_tool("get_quote", {"symbol": symbol})
    text = extract_text_content(raw)

    if raw.get("isError"):
        return {"error": text or "tool returned isError", "symbol": symbol}

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"error": "invalid JSON from MCP", "raw": text, "symbol": symbol}

    if isinstance(data, dict) and "error" in data:
        return data

    return data
