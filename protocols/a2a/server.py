"""Minimal A2A HTTP server for Atlas agents.

This is a small, portfolio-readable implementation of the A2A layer over HTTP
and JSON-RPC 2.0. It intentionally keeps the wire protocol explicit so the next
phases can show exactly how agents discover and delegate work.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from protocols.auth import a2a_auth_token, bearer_authorized

JsonDict = dict[str, Any]


class A2AServer:
    """Expose one Atlas agent through A2A-style HTTP endpoints.

    Endpoints:
      - GET /.well-known/agent.json: discovery document (Agent Card)
      - POST /a2a: JSON-RPC 2.0 endpoint for `agent/card` and `tasks/send`

    The Agent Card is the public contract. Callers learn the agent's URL,
    capabilities, and skills from the card rather than importing Python classes.
    """

    def __init__(
        self,
        *,
        agent: BaseAgent,
        agent_card_path: str | Path,
        host: str = "127.0.0.1",
        port: int = 9001,
    ) -> None:
        self.agent = agent
        self.agent_card_path = Path(agent_card_path)
        self.host = host
        self.port = port
        self.agent_card = self._load_agent_card()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._setup_complete = False

    def _load_agent_card(self) -> JsonDict:
        with self.agent_card_path.open("r", encoding="utf-8") as f:
            card = json.load(f)
        if not isinstance(card, dict):
            raise ValueError(f"agent card must be a JSON object: {self.agent_card_path}")
        return card

    def serve_forever(self) -> None:
        """Run the server in the current thread."""
        handler = self._make_handler()
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        print(f"[a2a] {self.agent_card['name']} listening at http://{self.host}:{self.port}")
        print("[a2a] GET  /.well-known/agent.json")
        print("[a2a] POST /a2a (agent/card, tasks/send)")
        self._httpd.serve_forever()

    def start_background(self) -> None:
        """Run the server in a daemon thread for demos/tests."""
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def shutdown(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()

    async def _run_agent(self, message: str) -> JsonDict:
        setup = getattr(self.agent, "setup", None)
        if setup is not None and not self._setup_complete:
            await setup()
            self._setup_complete = True
        return await self.agent.run(message)

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            """Request handler bound to a specific A2AServer instance."""

            def do_GET(self) -> None:  # noqa: N802 - stdlib handler method name
                if self.path == "/.well-known/agent.json":
                    if not bearer_authorized(
                        self.headers.get("Authorization"),
                        a2a_auth_token(),
                    ):
                        self._send_json(
                            {"error": "unauthorized"},
                            status=HTTPStatus.UNAUTHORIZED,
                        )
                        return
                    self._send_json(server.agent_card)
                    return
                self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:  # noqa: N802 - stdlib handler method name
                if self.path != "/a2a":
                    self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
                    return

                if not bearer_authorized(
                    self.headers.get("Authorization"),
                    a2a_auth_token(),
                ):
                    self._send_json(
                        {"error": "unauthorized"},
                        status=HTTPStatus.UNAUTHORIZED,
                    )
                    return

                try:
                    request = self._read_json()
                    response = server._handle_json_rpc(request)
                except Exception as exc:  # keep protocol errors JSON-shaped for clients
                    response = _json_rpc_error(None, -32603, f"internal error: {exc}")

                self._send_json(response)

            def _read_json(self) -> JsonDict:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body or "{}")
                if not isinstance(data, dict):
                    raise ValueError("JSON-RPC request must be a JSON object")
                return data

            def _send_json(
                self,
                payload: JsonDict,
                *,
                status: HTTPStatus = HTTPStatus.OK,
            ) -> None:
                data = json.dumps(payload, indent=2).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: Any) -> None:
                # Keep demo output focused on agent steps rather than access logs.
                return

        return Handler

    def _handle_json_rpc(self, request: JsonDict) -> JsonDict:
        """Route one JSON-RPC request.

        JSON-RPC gives A2A a small method envelope: clients send a method name
        (`tasks/send`) and params; the server returns either `result` or `error`.
        """
        request_id = request.get("id")
        if request.get("jsonrpc") != "2.0":
            return _json_rpc_error(request_id, -32600, 'jsonrpc must be "2.0"')

        method = request.get("method")
        params = request.get("params", {})
        if method == "agent/card":
            return _json_rpc_success(request_id, self.agent_card)
        if method == "tasks/send":
            return _json_rpc_success(request_id, self._handle_task_send(params))
        return _json_rpc_error(request_id, -32601, f"method not found: {method}")

    def _handle_task_send(self, params: Any) -> JsonDict:
        if not isinstance(params, dict):
            raise ValueError("tasks/send params must be an object")

        task_id = str(params.get("id") or uuid.uuid4())
        message = _extract_message_text(params)
        print(f"[a2a] tasks/send {task_id}: {message}")

        result = asyncio.run(self._run_agent(message))
        return {
            "id": task_id,
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "name": "agent_result",
                    "description": "Structured Atlas agent result",
                    "parts": [
                        {
                            "kind": "text",
                            "text": result["analysis"],
                        }
                    ],
                    "metadata": result,
                }
            ],
        }


def _extract_message_text(params: JsonDict) -> str:
    """Accept a few common A2A task shapes and normalize to plain text."""
    message = params.get("message") or params.get("task") or params
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        if isinstance(message.get("text"), str):
            return message["text"]
        parts = message.get("parts")
        if isinstance(parts, list):
            texts = [str(p.get("text", "")) for p in parts if isinstance(p, dict)]
            text = "\n".join(t for t in texts if t).strip()
            if text:
                return text
    raise ValueError("tasks/send requires a text message")


def _json_rpc_success(request_id: Any, result: Any) -> JsonDict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _json_rpc_error(request_id: Any, code: int, message: str) -> JsonDict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
