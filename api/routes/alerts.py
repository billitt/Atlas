"""Alert rules and live check routes."""

from __future__ import annotations

from fastapi import APIRouter

from api.security import AuthDep, RateLimitDep
from cli.main import _build_alert_engine
from memory.episodic import AlertRecord, EpisodicMemory
from services.alert_defaults import default_alert_rules
from sqlmodel import Session, select

router = APIRouter()


@router.get("/alerts")
async def list_alerts(_auth: AuthDep) -> dict:
    """Default alert rules and recent triggered alerts."""
    episodic = EpisodicMemory()
    with Session(episodic.engine) as session:
        recent = list(
            session.exec(select(AlertRecord).order_by(AlertRecord.timestamp.desc()).limit(20))
        )

    return {
        "rules": [
            {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "severity": rule.severity,
                "watch_topic": rule.watch_topic,
                "cooldown_seconds": rule.cooldown_seconds,
            }
            for rule in default_alert_rules()
        ],
        "recent": [
            {
                "id": record.id,
                "timestamp": record.timestamp.isoformat(timespec="seconds"),
                "rule_id": record.rule_id,
                "rule_name": record.rule_name,
                "severity": record.severity,
                "summary": record.summary,
                "evidence": record.evidence,
                "context": record.context,
            }
            for record in recent
        ],
    }


@router.post("/alerts/check")
async def check_alerts(_auth: AuthDep, _rate: RateLimitDep) -> dict:
    """Evaluate all default alert rules once."""
    engine = _build_alert_engine()
    triggered = await engine.check_all_rules()
    return {
        "triggered": [
            {
                "rule_id": alert["rule_id"],
                "rule_name": alert["rule_name"],
                "severity": alert["severity"],
                "summary": alert["summary"],
                "triggered_at": alert["triggered_at"],
                "evidence": alert.get("evidence"),
                "context": alert.get("context"),
            }
            for alert in triggered
        ]
    }
