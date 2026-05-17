"""Working memory: explicit per-query scratchpad."""

from __future__ import annotations

import json
from typing import Any


class WorkingMemory:
    """Small dict wrapper for in-context, per-run state."""

    def __init__(self) -> None:
        self._scratchpad: dict[str, Any] = {}

    def add(self, key: str, value: Any) -> None:
        self._scratchpad[key] = value

    def get(self, key: str) -> Any:
        return self._scratchpad.get(key)

    def get_all(self) -> dict[str, Any]:
        return dict(self._scratchpad)

    def clear(self) -> None:
        self._scratchpad.clear()

    def to_context_string(self) -> str:
        if not self._scratchpad:
            return "(working memory empty)"
        return json.dumps(self._scratchpad, indent=2, default=str)
