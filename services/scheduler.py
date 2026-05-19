"""APScheduler integration for autonomous Atlas briefings."""

from __future__ import annotations

from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.briefing import BriefingEngine
from services.briefing_templates import format_summary_line

JsonDict = dict[str, Any]


class AtlasScheduler:
    """Schedule recurring briefing jobs on the current asyncio event loop."""

    def __init__(self, briefing_engine: BriefingEngine) -> None:
        self.briefing_engine = briefing_engine
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """Begin the scheduler event loop integration."""
        if not self.scheduler.running:
            self.scheduler.start()

    def schedule_daily_briefing(
        self,
        hour: int = 7,
        minute: int = 0,
        topics: list[str] | None = None,
    ) -> str:
        job = self.scheduler.add_job(
            self._run_briefing_job,
            CronTrigger(hour=hour, minute=minute),
            args=["daily", topics],
            id="daily_briefing",
            replace_existing=True,
        )
        return job.id

    def schedule_weekly_briefing(
        self,
        day_of_week: str = "mon",
        hour: int = 7,
        topics: list[str] | None = None,
    ) -> str:
        job = self.scheduler.add_job(
            self._run_briefing_job,
            CronTrigger(day_of_week=day_of_week, hour=hour, minute=0),
            args=["weekly", topics],
            id="weekly_briefing",
            replace_existing=True,
        )
        return job.id

    def schedule_custom(self, cron_expression: str, topics: list[str]) -> str:
        trigger = _cron_trigger_from_expression(cron_expression)
        job = self.scheduler.add_job(
            self._run_briefing_job,
            trigger,
            args=["custom", topics],
            id=f"custom_briefing_{abs(hash(cron_expression))}",
            replace_existing=True,
        )
        return job.id

    def stop(self) -> None:
        """Gracefully stop scheduled jobs."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def list_jobs(self) -> list[JsonDict]:
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in self.scheduler.get_jobs()
        ]

    async def _run_briefing_job(self, briefing_type: str, topics: list[str] | None) -> None:
        previous_type = self.briefing_engine.briefing_type
        self.briefing_engine.briefing_type = briefing_type
        try:
            briefing = await self.briefing_engine.generate_briefing(topics)
            print(f"[scheduler] {format_summary_line(briefing)}")
        finally:
            self.briefing_engine.briefing_type = previous_type


def _cron_trigger_from_expression(cron_expression: str) -> CronTrigger:
    parts = cron_expression.split()
    if len(parts) != 5:
        raise ValueError("cron_expression must have 5 fields: minute hour day month day_of_week")
    minute, hour, day, month, day_of_week = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )
