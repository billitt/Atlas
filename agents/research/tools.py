"""MCP tool helpers for SEC EDGAR research."""

from __future__ import annotations

import json
from typing import Any

from protocols.mcp.client import McpClient

AVAILABLE_TOOLS: list[dict[str, Any]] = []


async def load_tools(client: McpClient) -> list[dict[str, Any]]:
    global AVAILABLE_TOOLS
    await client.initialize()
    AVAILABLE_TOOLS = await client.list_tools()
    return AVAILABLE_TOOLS


def format_tools_for_prompt() -> str:
    if not AVAILABLE_TOOLS:
        return "(no EDGAR tools loaded)"
    return json.dumps(AVAILABLE_TOOLS, indent=2)


def extract_text_content(mcp_result: dict[str, Any]) -> str:
    chunks: list[str] = []
    for block in mcp_result.get("content", []):
        if block.get("type") == "text":
            chunks.append(str(block.get("text", "")))
    return "\n".join(chunks).strip()


async def call_company_filings(
    client: McpClient,
    *,
    ticker: str | None = None,
    cik: str | None = None,
) -> dict[str, Any]:
    args = {k: v for k, v in {"ticker": ticker, "cik": cik}.items() if v}
    raw = await client.call_tool("company_filings", args)
    return _parse_tool_result(raw)


async def call_filing_text(client: McpClient, accession_number: str, cik: str) -> dict[str, Any]:
    raw = await client.call_tool(
        "filing_text",
        {"accession_number": accession_number, "cik": cik},
    )
    return _parse_tool_result(raw)


async def call_full_text_search(
    client: McpClient,
    query: str,
    form_type: str | None = None,
    date_from: str | None = None,
) -> dict[str, Any]:
    args = {
        k: v
        for k, v in {"query": query, "form_type": form_type, "date_from": date_from}.items()
        if v
    }
    raw = await client.call_tool("full_text_search", args)
    return _parse_tool_result(raw)


def _parse_tool_result(raw: dict[str, Any]) -> dict[str, Any]:
    text = extract_text_content(raw)
    if raw.get("isError"):
        return {"error": text or "tool returned isError"}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"result": parsed}
