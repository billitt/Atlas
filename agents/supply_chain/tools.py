"""MCP tool helpers for UN Comtrade supply-chain research."""

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
        return "(no Comtrade tools loaded)"
    return json.dumps(AVAILABLE_TOOLS, indent=2)


def extract_text_content(mcp_result: dict[str, Any]) -> str:
    chunks: list[str] = []
    for block in mcp_result.get("content", []):
        if block.get("type") == "text":
            chunks.append(str(block.get("text", "")))
    return "\n".join(chunks).strip()


async def call_get_trade_data(
    client: McpClient,
    *,
    reporter_code: str,
    period: str,
    partner_code: str | None = None,
    cmd_code: str | None = None,
    flow_code: str | None = None,
    type_code: str = "C",
    freq_code: str = "A",
    cl_code: str = "HS",
    max_records: int | None = None,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "reporterCode": reporter_code,
        "period": period,
        "typeCode": type_code,
        "freqCode": freq_code,
        "clCode": cl_code,
    }
    if partner_code:
        args["partnerCode"] = partner_code
    if cmd_code:
        args["cmdCode"] = cmd_code
    if flow_code:
        args["flowCode"] = flow_code
    if max_records is not None:
        args["maxRecords"] = max_records
    raw = await client.call_tool("get_trade_data", args)
    return _parse_tool_result(raw)


async def call_get_tariffline(
    client: McpClient,
    *,
    reporter_code: str,
    period: str,
    partner_code: str | None = None,
    cmd_code: str | None = None,
    flow_code: str | None = None,
    type_code: str = "C",
    freq_code: str = "A",
    cl_code: str = "HS",
    max_records: int | None = None,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "reporterCode": reporter_code,
        "period": period,
        "typeCode": type_code,
        "freqCode": freq_code,
        "clCode": cl_code,
    }
    if partner_code:
        args["partnerCode"] = partner_code
    if cmd_code:
        args["cmdCode"] = cmd_code
    if flow_code:
        args["flowCode"] = flow_code
    if max_records is not None:
        args["maxRecords"] = max_records
    raw = await client.call_tool("get_tariffline", args)
    return _parse_tool_result(raw)


def _parse_tool_result(raw: dict[str, Any]) -> dict[str, Any]:
    text = extract_text_content(raw)
    if raw.get("isError"):
        return {"error": text or "tool returned isError"}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    if isinstance(parsed, dict):
        return parsed
    return {"result": parsed}
