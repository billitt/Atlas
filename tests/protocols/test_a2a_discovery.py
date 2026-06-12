"""Boundary tests for A2A Agent Card discovery registry."""

from __future__ import annotations

import pytest

from protocols.a2a.discovery import AgentRegistry


def test_register_rejects_empty_name() -> None:
    registry = AgentRegistry()
    with pytest.raises(ValueError, match="non-empty name"):
        registry.register({"name": "   ", "skills": []})


def test_find_by_skill_returns_matching_cards() -> None:
    registry = AgentRegistry()
    registry.register(
        {
            "name": "Market Intelligence Agent",
            "skills": [{"id": "market_snapshot", "name": "Market Snapshot"}],
        }
    )
    registry.register(
        {
            "name": "Geopolitical Risk Agent",
            "skills": [{"id": "risk_assessment", "name": "Risk Assessment"}],
        }
    )

    matches = registry.find_by_skill("market_snapshot")

    assert len(matches) == 1
    assert matches[0]["name"] == "Market Intelligence Agent"


def test_find_by_skill_skips_malformed_skills() -> None:
    registry = AgentRegistry()
    registry.register({"name": "Broken Agent", "skills": "not-a-list"})
    registry.register(
        {
            "name": "Valid Agent",
            "skills": [{"id": "validate", "name": "Validate"}],
        }
    )

    assert registry.find_by_skill("validate") == [{"name": "Valid Agent", "skills": [{"id": "validate", "name": "Validate"}]}]
    assert registry.find_by_skill("missing") == []


def test_load_from_files_loads_real_agent_cards() -> None:
    registry = AgentRegistry()
    registry.load_from_files("agents")

    cards = registry.discover_all()
    assert len(cards) >= 4

    market_matches = registry.find_by_skill("market_snapshot")
    assert len(market_matches) >= 1
    assert market_matches[0]["name"] == "Market Intelligence Agent"
