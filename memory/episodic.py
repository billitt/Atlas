"""Episodic memory backed by SQLite + SQLModel."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Column, JSON
from sqlmodel import Field, Session, SQLModel, create_engine, select

DB_PATH = "data/sqlite/atlas_episodic.db"


class BriefingRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now, index=True)
    query: str = Field(index=True)
    plan: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    agent_results: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    final_briefing: str
    confidence: str = Field(index=True)
    sources: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    trace_id: str | None = Field(default=None, index=True)
    duration_seconds: float | None = None


class AlertRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now, index=True)
    trigger: str = Field(index=True)
    agent_chain: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    assessment: str
    severity: str = Field(index=True)


class AgentExecution(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now, index=True)
    agent_name: str = Field(index=True)
    task: str = Field(index=True)
    result: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: str = Field(index=True)
    duration_seconds: float | None = None


class EpisodicMemory:
    """Append-only memory of briefings, alerts, and agent executions."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.init_db()

    def init_db(self) -> None:
        SQLModel.metadata.create_all(self.engine)

    def log_briefing(self, run_data: dict[str, Any]) -> BriefingRecord:
        timestamp = _parse_timestamp(run_data.get("timestamp"))
        record = BriefingRecord(
            timestamp=timestamp,
            query=str(run_data.get("query", "")),
            plan=run_data.get("execution_plan") or run_data.get("plan") or {},
            agent_results=run_data.get("agent_results") or [],
            final_briefing=str(run_data.get("final_briefing", "")),
            confidence=str(run_data.get("confidence", "LOW")),
            sources=run_data.get("sources") or [],
            trace_id=run_data.get("trace_id"),
            duration_seconds=run_data.get("duration_seconds"),
        )
        with Session(self.engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
        return record

    def log_agent_execution(
        self,
        agent_name: str,
        task: str,
        result: dict[str, Any],
        confidence: str,
        duration: float | None,
    ) -> AgentExecution:
        record = AgentExecution(
            agent_name=agent_name,
            task=task,
            result=result,
            confidence=confidence,
            duration_seconds=duration,
        )
        with Session(self.engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
        return record

    def query_briefings(self, query: str, limit: int = 10) -> list[BriefingRecord]:
        terms = [term.strip() for term in query.split() if term.strip()]
        statement = select(BriefingRecord).order_by(BriefingRecord.timestamp.desc()).limit(limit)
        with Session(self.engine) as session:
            records = list(session.exec(statement))
        if not terms:
            return records

        lowered = [term.lower() for term in terms]
        return [
            record
            for record in records
            if any(term in record.query.lower() or term in record.final_briefing.lower() for term in lowered)
        ][:limit]

    def query_briefings_by_date(self, start: datetime, end: datetime) -> list[BriefingRecord]:
        statement = (
            select(BriefingRecord)
            .where(BriefingRecord.timestamp >= start)
            .where(BriefingRecord.timestamp <= end)
            .order_by(BriefingRecord.timestamp.desc())
        )
        with Session(self.engine) as session:
            return list(session.exec(statement))

    def get_confidence_history(self, topic: str, days: int = 90) -> list[dict[str, Any]]:
        start = datetime.now() - timedelta(days=days)
        statement = (
            select(BriefingRecord)
            .where(BriefingRecord.timestamp >= start)
            .order_by(BriefingRecord.timestamp.asc())
        )
        topic_lower = topic.lower()
        with Session(self.engine) as session:
            records = list(session.exec(statement))
        return [
            {
                "timestamp": record.timestamp.isoformat(),
                "query": record.query,
                "confidence": record.confidence,
            }
            for record in records
            if topic_lower in record.query.lower() or topic_lower in record.final_briefing.lower()
        ]

    def briefing_count(self) -> int:
        with Session(self.engine) as session:
            return len(list(session.exec(select(BriefingRecord.id))))


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now()
    return datetime.now()
