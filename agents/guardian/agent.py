"""Guardian Agent: second-pass validation for synthesized briefings."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Literal, TypedDict

from services.llm import chat

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
JsonDict = dict[str, Any]


class ClaimCheck(TypedDict):
    claim: str
    grounded: bool
    source: str | None
    confidence: Confidence
    issue: str | None


class GuardianVerdict(TypedDict):
    passed: bool
    overall_confidence: Confidence
    claim_checks: list[ClaimCheck]
    flags: list[str]
    summary: str


class GuardianAgent:
    """Validate and annotate another agent's briefing without rewriting it."""

    def validate(
        self,
        query: str,
        briefing: JsonDict,
        agent_results: list[JsonDict],
        sources: list[JsonDict],
    ) -> GuardianVerdict:
        """Run one Granite validation pass and return a structured verdict."""
        prompt = f"""You are the Atlas Guardian Agent.
You are a second-pass validator, not a content generator. Do NOT fix or rewrite
the briefing. Validate it, flag problems, and assign confidence.

Current date: {datetime.now().date().isoformat()}
Data freshness rule: flag sources older than 7 days when a date is available.

User query:
{query}

Briefing to validate:
{json.dumps(briefing, indent=2)[:12000]}

Agent results:
{json.dumps(agent_results, indent=2)[:16000]}

Sources:
{json.dumps(sources, indent=2)[:12000]}

Validation tasks:
1. List every material claim in the briefing.
2. For each claim, decide whether it traces to a specific source in agent_results or sources.
3. Flag unsupported claims as hallucination risks.
4. Flag stale data older than 7 days when source dates are present.
5. Mark single-source assertions MEDIUM confidence at best.
6. Detect speculative language presented as fact.
7. Assign per-claim confidence and one overall confidence.

Confidence calibration:
- HIGH: directly supported by multiple fresh sources or a clearly cited authoritative source.
- MEDIUM: supported by one source, stale-but-still-relevant context, or reasonable synthesis across agents.
- LOW: unsupported, contradicted, stale for time-sensitive claims, or speculative language stated as fact.

Return ONLY valid JSON matching this schema:
{{
  "passed": true,
  "overall_confidence": "HIGH",
  "claim_checks": [
    {{
      "claim": "brief claim text",
      "grounded": true,
      "source": "agent/source identifier or null",
      "confidence": "HIGH",
      "issue": null
    }}
  ],
  "flags": [],
  "summary": "short validation summary"
}}
"""
        raw = chat(prompt)
        try:
            parsed = _parse_json_from_llm(raw)
        except json.JSONDecodeError:
            return _fallback_verdict(f"Guardian returned malformed JSON: {raw[:300]}")
        return _normalize_verdict(parsed)


def _parse_json_from_llm(text: str) -> JsonDict:
    """Extract a JSON object from model output (raw or ```json fenced)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(text[start : end + 1])
        else:
            raise
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Guardian JSON must be an object", text, 0)
    return parsed


def _normalize_verdict(parsed: JsonDict) -> GuardianVerdict:
    confidence = _normalize_confidence(parsed.get("overall_confidence"))
    checks = [_normalize_check(check) for check in parsed.get("claim_checks", []) if isinstance(check, dict)]
    flags = [str(flag) for flag in parsed.get("flags", []) if str(flag).strip()]
    passed = bool(parsed.get("passed", False)) and confidence != "LOW" and not flags
    return {
        "passed": passed,
        "overall_confidence": confidence,
        "claim_checks": checks,
        "flags": flags,
        "summary": str(parsed.get("summary", "")).strip() or "Guardian validation completed.",
    }


def _normalize_check(check: JsonDict) -> ClaimCheck:
    issue = check.get("issue")
    source = check.get("source")
    return {
        "claim": str(check.get("claim", "")).strip(),
        "grounded": bool(check.get("grounded", False)),
        "source": str(source).strip() if source is not None and str(source).strip() else None,
        "confidence": _normalize_confidence(check.get("confidence")),
        "issue": str(issue).strip() if issue is not None and str(issue).strip() else None,
    }


def _normalize_confidence(value: Any) -> Confidence:
    confidence = str(value or "LOW").upper()
    if confidence in {"HIGH", "MEDIUM", "LOW"}:
        return confidence  # type: ignore[return-value]
    return "LOW"


def _fallback_verdict(message: str) -> GuardianVerdict:
    return {
        "passed": False,
        "overall_confidence": "LOW",
        "claim_checks": [
            {
                "claim": "Guardian validation could not parse the model response.",
                "grounded": False,
                "source": None,
                "confidence": "LOW",
                "issue": message,
            }
        ],
        "flags": [message],
        "summary": "Guardian validation failed because the model response was not valid JSON.",
    }
