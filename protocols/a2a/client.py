"""Async A2A client for agent discovery and task delegation."""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx

from observability.tracing import get_tracer
from protocols.auth import a2a_auth_token, auth_headers, tls_verify_enabled

JsonDict = dict[str, Any]
_tracer = get_tracer("protocols.a2a")

# Default A2A request timeout. The research agent issues many sequential Granite
# calls (plan, per-company filing selection, analysis, reflect) that, under
# single-GPU Ollama contention, can run several minutes. Configurable via
# ATLAS_A2A_TIMEOUT so demo hosts can tune without code edits.
_DEFAULT_A2A_TIMEOUT = 600.0


def default_a2a_timeout() -> float:
    raw = os.getenv("ATLAS_A2A_TIMEOUT")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return _DEFAULT_A2A_TIMEOUT


class A2AClient:
    """Small HTTP/JSON-RPC client for Atlas A2A agents."""

    def __init__(
        self,
        *,
        timeout: float | None = None,
        auth_token: str | None = None,
        verify_tls: bool | None = None,
    ) -> None:
        self.timeout = timeout if timeout is not None else default_a2a_timeout()
        self._auth_token = auth_token if auth_token is not None else a2a_auth_token()
        self._verify_tls = tls_verify_enabled() if verify_tls is None else verify_tls
        self._next_id = 0

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout,
            verify=self._verify_tls,
            headers=auth_headers(self._auth_token),
        )

    async def discover(self, url: str) -> JsonDict:
        """Fetch an Agent Card from `/.well-known/agent.json`."""
        async with self._http_client() as client:
            response = await client.get(f"{url.rstrip('/')}/.well-known/agent.json")
            response.raise_for_status()
            card = response.json()
        if not isinstance(card, dict):
            raise RuntimeError(f"unexpected Agent Card response: {card!r}")
        return card

    async def send_task(self, url: str, message: str) -> JsonDict:
        """Delegate a text task to another agent via JSON-RPC `tasks/send`."""
        with _tracer.start_as_current_span("a2a.send_task") as span:
            span.set_attribute("target_url", url)
            span.set_attribute("task_summary", message[:500])
            try:
                card = await self.discover(url)
                span.set_attribute("target_agent", str(card.get("name", url)))
            except httpx.HTTPError:
                span.set_attribute("target_agent", url)

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
        async with self._http_client() as client:
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
