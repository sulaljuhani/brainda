from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
import structlog
import os
from datetime import datetime, timezone

from common.db import connect_with_json_codec
from api.metrics import reminder_fire_lag_seconds, reminders_fired_total

logger = structlog.get_logger()

scheduler = None


def start_scheduler():
    global scheduler
    jobstores = {
        "default": RedisJobStore(
            jobs_key="apscheduler.jobs",
            run_times_key="apscheduler.run_times",
            host="redis",
            port=6379,
        )
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores, timezone="UTC")
    scheduler.start()
    logger.info("scheduler_started")


def schedule_reminder(reminder_id: str, due_at: datetime):
    if scheduler:
        scheduler.add_job(
            fire_reminder,
            "date",
            run_date=due_at,
            args=[reminder_id],
            id=f"reminder_{reminder_id}",
            replace_existing=True,
        )
        logger.info(
            "reminder_scheduled", reminder_id=reminder_id, due_at=due_at.isoformat()
        )


async def fire_reminder(reminder_id: str):
    """
    Execute reminder firing workflow when scheduler triggers.
    """

    conn = await connect_with_json_codec(os.getenv("DATABASE_URL"))
    try:
        reminder = await conn.fetchrow(
            "SELECT * FROM reminders WHERE id = $1", reminder_id
        )
        if not reminder or reminder["status"] != "active":
            logger.warning("reminder_not_found_or_inactive", reminder_id=reminder_id)
            return

        scheduled_time = reminder["due_at_utc"]
        actual_time = datetime.now(timezone.utc)
        lag_seconds = (actual_time - scheduled_time).total_seconds()

        # Track SLO metric
        reminder_fire_lag_seconds.observe(lag_seconds)

        logger.info(
            "reminder_firing",
            reminder_id=reminder_id,
            lag_seconds=lag_seconds,
        )

        devices = await conn.fetch(
            "SELECT * FROM devices WHERE user_id = $1", reminder["user_id"]
        )

        from api.services.notification_service import send_reminder_notification

        for device in devices:
            await send_reminder_notification(dict(reminder), dict(device))

        # Handle recurring reminders
        if reminder["repeat_rrule"]:
            from dateutil.rrule import rrulestr
            from dateutil.parser import isoparse

            rule = rrulestr(reminder["repeat_rrule"], dtstart=reminder["due_at_utc"])
            next_occurrence = rule.after(datetime.now(timezone.utc))

            if next_occurrence:
                await conn.execute(
                    """
                    UPDATE reminders SET due_at_utc = $1 WHERE id = $2
                """,
                    next_occurrence,
                    reminder_id,
                )
                schedule_reminder(reminder_id, next_occurrence)
                logger.info(
                    "recurring_reminder_rescheduled",
                    reminder_id=reminder_id,
                    next_due=next_occurrence.isoformat(),
                )
            else:
                await conn.execute(
                    "UPDATE reminders SET status = 'done' WHERE id = $1", reminder_id
                )
        else:
            await conn.execute(
                "UPDATE reminders SET status = 'done' WHERE id = $1", reminder_id
            )

        reminders_fired_total.labels(user_id=str(reminder["user_id"])).inc()

    finally:
        await conn.close()


async def sync_scheduled_reminders():
    """
    On startup, sync active reminders from DB with the scheduler.
    This ensures no reminders are missed if the server restarts.
    """

    conn = await connect_with_json_codec(os.getenv("DATABASE_URL"))
    try:
        reminders = await conn.fetch(
            "SELECT id, due_at_utc FROM reminders WHERE status = 'active' AND due_at_utc > NOW()"
        )
        for r in reminders:
            schedule_reminder(str(r["id"]), r["due_at_utc"])
        logger.info("scheduled_reminders_synced", count=len(reminders))
    finally:
        await conn.close()
