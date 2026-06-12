"""Minimal MCP JSON-RPC client for Atlas Rust MCP servers."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from observability.tracing import get_tracer
from protocols.auth import auth_headers, mcp_auth_token, tls_verify_enabled

_tracer = get_tracer("protocols.mcp")


class McpClient:
    """HTTP client for MCP servers that expose a single POST /mcp JSON-RPC endpoint."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 60.0,
        auth_token: str | None = None,
        verify_tls: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._auth_token = auth_token if auth_token is not None else mcp_auth_token()
        self._verify_tls = tls_verify_enabled() if verify_tls is None else verify_tls
        self._next_id = 0

    def _rpc_url(self) -> str:
        return f"{self.base_url}/mcp"

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            verify=self._verify_tls,
            headers=auth_headers(self._auth_token),
        )

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        async with self._http_client() as client:
            response = await client.post(self._rpc_url(), json=payload)
            response.raise_for_status()
            body = response.json()

        if "error" in body:
            err = body["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")

        return body.get("result")

    async def initialize(self) -> dict[str, Any]:
        """MCP handshake — must be called before tools/list or tools/call."""
        result = await self._request("initialize", {"capabilities": {}})
        if not isinstance(result, dict):
            raise RuntimeError(f"unexpected initialize result: {result!r}")
        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions advertised by the server."""
        result = await self._request("tools/list")
        if not isinstance(result, dict):
            raise RuntimeError(f"unexpected tools/list result: {result!r}")
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise RuntimeError(f"unexpected tools list: {tools!r}")
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool by name with JSON arguments."""
        with _tracer.start_as_current_span("mcp.call_tool") as span:
            span.set_attribute("tool_name", name)
            span.set_attribute("server_url", self.base_url)
            span.set_attribute("arguments", json.dumps(arguments)[:2000])
            result = await self._request(
                "tools/call",
                {"name": name, "arguments": arguments},
            )
            if not isinstance(result, dict):
                raise RuntimeError(f"unexpected tools/call result: {result!r}")
            span.set_attribute("response_size", len(json.dumps(result)))
            return result


async def main() -> None:
    base_url = "http://localhost:8001"
    client = McpClient(base_url)

    print(f"Connecting to {base_url} ...")
    init = await client.initialize()
    print(f"initialize: {json.dumps(init, indent=2)}")
    print()

    tools = await client.list_tools()
    print("tools/list:")
    for tool in tools:
        print(f"  - {tool.get('name')}: {tool.get('description', '')}")
    print()

    print('tools/call get_quote(symbol="AAPL") ...')
    result = await client.call_tool("get_quote", {"symbol": "AAPL"})
    for block in result.get("content", []):
        if block.get("type") == "text":
            print(block.get("text", ""))
        else:
            print(json.dumps(block, indent=2))

    if result.get("isError"):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
