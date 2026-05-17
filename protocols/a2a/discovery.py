"""Local Agent Card registry for Atlas A2A discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


class AgentRegistry:
    """In-memory registry of A2A Agent Cards.

    The registry is deliberately card-first: orchestration code can ask "who has
    skill X?" without importing or knowing the specialist agent implementation.
    """

    def __init__(self) -> None:
        self._cards: dict[str, JsonDict] = {}

    def register(self, agent_card: JsonDict) -> None:
        name = str(agent_card.get("name", "")).strip()
        if not name:
            raise ValueError("Agent Card requires a non-empty name")
        self._cards[name] = agent_card

    def discover_all(self) -> list[JsonDict]:
        return list(self._cards.values())

    def find_by_skill(self, skill_id: str) -> list[JsonDict]:
        matches: list[JsonDict] = []
        for card in self._cards.values():
            skills = card.get("skills", [])
            if not isinstance(skills, list):
                continue
            if any(isinstance(skill, dict) and skill.get("id") == skill_id for skill in skills):
                matches.append(card)
        return matches

    def load_from_files(self, root: str | Path = "agents") -> None:
        """Load all `agents/*/agent_card.json` files into the registry."""
        root_path = Path(root)
        for path in sorted(root_path.glob("*/agent_card.json")):
            with path.open("r", encoding="utf-8") as f:
                card = json.load(f)
            if not isinstance(card, dict):
                raise ValueError(f"Agent Card must be an object: {path}")
            self.register(card)


_DEFAULT_REGISTRY = AgentRegistry()


def register(agent_card: JsonDict) -> None:
    _DEFAULT_REGISTRY.register(agent_card)


def discover_all() -> list[JsonDict]:
    return _DEFAULT_REGISTRY.discover_all()


def find_by_skill(skill_id: str) -> list[JsonDict]:
    return _DEFAULT_REGISTRY.find_by_skill(skill_id)


def load_cards(root: str | Path = "agents") -> AgentRegistry:
    _DEFAULT_REGISTRY.load_from_files(root)
    return _DEFAULT_REGISTRY
