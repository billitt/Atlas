"""Boundary tests for Guardian verdict parsing and fallback behavior."""

from __future__ import annotations

import json
from unittest.mock import patch

from agents.guardian.agent import (
    GuardianAgent,
    _fallback_verdict,
    _normalize_verdict,
    _parse_json_from_llm,
)


def test_parse_json_strips_markdown_fences() -> None:
    parsed = _parse_json_from_llm(
        '```json\n{"passed": true, "overall_confidence": "HIGH", "claim_checks": []}\n```'
    )
    assert parsed["passed"] is True
    assert parsed["overall_confidence"] == "HIGH"


def test_normalize_verdict_flags_ungrounded_claim() -> None:
    verdict = _normalize_verdict(
        {
            "passed": True,
            "overall_confidence": "HIGH",
            "claim_checks": [
                {
                    "claim": "TSMC revenue grew 15%",
                    "grounded": False,
                    "source": None,
                    "confidence": "LOW",
                    "issue": "no revenue figure in sources",
                }
            ],
            "flags": ["unsupported revenue claim"],
            "summary": "One claim lacks source support.",
        }
    )

    assert verdict["passed"] is False
    assert verdict["overall_confidence"] == "HIGH"
    assert verdict["claim_checks"][0]["grounded"] is False
    assert "unsupported revenue claim" in verdict["flags"]


def test_guardian_handles_llm_garbage() -> None:
    agent = GuardianAgent()
    with patch("agents.guardian.agent.chat", return_value="not json at all"):
        verdict = agent.validate(
            query="TSMC risk",
            briefing={"summary": "Revenue grew 15%"},
            agent_results=[],
            sources=[],
        )

    assert verdict["passed"] is False
    assert verdict["overall_confidence"] == "LOW"
    assert verdict["flags"]
    assert verdict["claim_checks"][0]["grounded"] is False


def test_guardian_catches_unsourced_claim() -> None:
    agent = GuardianAgent()
    llm_payload = {
        "passed": False,
        "overall_confidence": "LOW",
        "claim_checks": [
            {
                "claim": "TSMC revenue grew 15%",
                "grounded": False,
                "source": None,
                "confidence": "LOW",
                "issue": "no revenue in sources",
            }
        ],
        "flags": ["unsupported revenue claim"],
        "summary": "Revenue claim is not grounded.",
    }
    with patch("agents.guardian.agent.chat", return_value=json.dumps(llm_payload)):
        verdict = agent.validate(
            query="TSMC revenue outlook",
            briefing={"summary": "TSMC revenue grew 15% year over year."},
            agent_results=[{"agent": "market", "analysis": "TSM price moved 1%"}],
            sources=[{"symbol": "TSM", "regular_market_price": 145.0}],
        )

    assert verdict["passed"] is False
    assert verdict["overall_confidence"] == "LOW"
    assert verdict["claim_checks"][0]["claim"] == "TSMC revenue grew 15%"
    assert verdict["claim_checks"][0]["grounded"] is False


def test_fallback_verdict_is_safe_default() -> None:
    verdict = _fallback_verdict("malformed response")
    assert verdict["passed"] is False
    assert verdict["overall_confidence"] == "LOW"
    assert verdict["flags"] == ["malformed response"]
