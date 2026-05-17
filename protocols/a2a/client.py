"""Async A2A client for agent discovery and task delegation."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

JsonDict = dict[str, Any]


class A2AClient:
    """Small HTTP/JSON-RPC client for Atlas A2A agents."""

    def __init__(self, *, timeout: float = 180.0) -> None:
        self.timeout = timeout
        self._next_id = 0

    async def discover(self, url: str) -> JsonDict:
        """Fetch an Agent Card from `/.well-known/agent.json`.

        Discovery is intentionally HTTP-native: a synthesis process only needs an
        agent URL to learn what skills it offers and where to send tasks.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{url.rstrip('/')}/.well-known/agent.json")
            response.raise_for_status()
            card = response.json()
        if not isinstance(card, dict):
            raise RuntimeError(f"unexpected Agent Card response: {card!r}")
        return card

    async def send_task(self, url: str, message: str) -> JsonDict:
        """Delegate a text task to another agent via JSON-RPC `tasks/send`."""
        result = await self._json_rpc(
            url,
            "tasks/send",
            {
                "id": str(uuid.uuid4()),
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": message}],
                },
            },
        )
        if not isinstance(result, dict):
            raise RuntimeError(f"unexpected tasks/send result: {result!r}")
        return result

    async def agent_card(self, url: str) -> JsonDict:
        """Fetch the card through the JSON-RPC method, not the well-known URL."""
        result = await self._json_rpc(url, "agent/card", {})
        if not isinstance(result, dict):
            raise RuntimeError(f"unexpected agent/card result: {result!r}")
        return result

    async def _json_rpc(self, url: str, method: str, params: JsonDict) -> Any:
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
            "params": params,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{url.rstrip('/')}/a2a", json=payload)
            response.raise_for_status()
            body = response.json()

        if "error" in body:
            error = body["error"]
            raise RuntimeError(f"A2A error {error.get('code')}: {error.get('message')}")
        return body.get("result")


async def discover(url: str) -> JsonDict:
    return await A2AClient().discover(url)


async def send_task(url: str, message: str) -> JsonDict:
    return await A2AClient().send_task(url, message)
