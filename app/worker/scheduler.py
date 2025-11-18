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
    else:
        logger.warning(
            "reminder_not_scheduled_scheduler_unavailable",
            reminder_id=reminder_id,
            due_at=due_at.isoformat()
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


async def register_agent_schedules():
    """
    Register scheduled agents for autonomous assistance based on user settings.

    Agents are configured per-user from agent_settings table:
    - Morning briefing (configurable time)
    - Evening review (configurable time)
    - Weekly summary (configurable day/time)

    Each user can enable/disable agents and set custom times.
    """
    if not scheduler:
        logger.warning("agent_schedules_not_registered_scheduler_unavailable")
        return

    from api.services.agent_settings_service import AgentSettingsService

    settings_service = AgentSettingsService()
    users = await settings_service.get_all_users_with_enabled_agents()

    if not users:
        logger.info("no_users_with_enabled_agents")
        return

    import pytz
    from datetime import time as datetime_time

    for user in users:
        user_id = user["user_id"]
        user_tz = pytz.timezone(user["timezone"])

        for agent in user["enabled_agents"]:
            agent_name = agent["name"]

            try:
                if agent_name == "morning_briefing":
                    # Parse time
                    agent_time = agent["time"]
                    hour = agent_time.hour
                    minute = agent_time.minute

                    scheduler.add_job(
                        func="worker.agents.morning_briefing_agent",
                        trigger="cron",
                        hour=hour,
                        minute=minute,
                        timezone=user_tz,
                        args=[user_id],
                        id=f"morning_briefing_{user_id}",
                        replace_existing=True,
                    )
                    logger.info(
                        "agent_scheduled",
                        agent="morning_briefing",
                        user_id=user_id,
                        time=f"{hour:02d}:{minute:02d}",
                        timezone=user["timezone"],
                    )

                elif agent_name == "evening_review":
                    agent_time = agent["time"]
                    hour = agent_time.hour
                    minute = agent_time.minute

                    scheduler.add_job(
                        func="worker.agents.evening_review_agent",
                        trigger="cron",
                        hour=hour,
                        minute=minute,
                        timezone=user_tz,
                        args=[user_id],
                        id=f"evening_review_{user_id}",
                        replace_existing=True,
                    )
                    logger.info(
                        "agent_scheduled",
                        agent="evening_review",
                        user_id=user_id,
                        time=f"{hour:02d}:{minute:02d}",
                        timezone=user["timezone"],
                    )

                elif agent_name == "weekly_summary":
                    agent_time = agent["time"]
                    day_of_week = agent["day_of_week"]
                    hour = agent_time.hour
                    minute = agent_time.minute

                    # Map day_of_week to cron format (mon, tue, wed, thu, fri, sat, sun)
                    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                    day_str = days[day_of_week]

                    scheduler.add_job(
                        func="worker.agents.weekly_summary_agent",
                        trigger="cron",
                        day_of_week=day_str,
                        hour=hour,
                        minute=minute,
                        timezone=user_tz,
                        args=[user_id],
                        id=f"weekly_summary_{user_id}",
                        replace_existing=True,
                    )
                    logger.info(
                        "agent_scheduled",
                        agent="weekly_summary",
                        user_id=user_id,
                        day=day_str,
                        time=f"{hour:02d}:{minute:02d}",
                        timezone=user["timezone"],
                    )

            except Exception as exc:
                logger.error(
                    "failed_to_schedule_agent",
                    agent=agent_name,
                    user_id=user_id,
                    error=str(exc),
                )

    logger.info("agent_schedules_registered", user_count=len(users))


async def reconfigure_agent_schedules(user_id):
    """
    Reconfigure agent schedules for a specific user.
    Called when user updates their agent settings.

    Args:
        user_id: User UUID or string
    """
    if not scheduler:
        logger.warning("cannot_reconfigure_scheduler_unavailable")
        return

    from api.services.agent_settings_service import AgentSettingsService
    from uuid import UUID
    import pytz

    # Convert to UUID if string
    if isinstance(user_id, str):
        user_id = UUID(user_id)

    settings_service = AgentSettingsService()
    result = await settings_service.get_enabled_agents_for_user(user_id)

    if not result.get("success"):
        logger.error("failed_to_get_user_agent_settings", user_id=str(user_id))
        return

    data = result["data"]
    enabled_agents = data["enabled_agents"]
    user_tz = pytz.timezone(data["timezone"])

    # Remove all existing jobs for this user
    job_ids = [
        f"morning_briefing_{user_id}",
        f"evening_review_{user_id}",
        f"weekly_summary_{user_id}",
    ]

    for job_id in job_ids:
        try:
            scheduler.remove_job(job_id)
        except:
            pass  # Job doesn't exist, that's OK

    # Re-add jobs based on current settings
    for agent in enabled_agents:
        agent_name = agent["name"]

        try:
            if agent_name == "morning_briefing":
                schedule_time = agent["schedule"]
                parts = schedule_time.split(":")
                hour, minute = int(parts[0]), int(parts[1])

                scheduler.add_job(
                    func="worker.agents.morning_briefing_agent",
                    trigger="cron",
                    hour=hour,
                    minute=minute,
                    timezone=user_tz,
                    args=[str(user_id)],
                    id=f"morning_briefing_{user_id}",
                    replace_existing=True,
                )

            elif agent_name == "evening_review":
                schedule_time = agent["schedule"]
                parts = schedule_time.split(":")
                hour, minute = int(parts[0]), int(parts[1])

                scheduler.add_job(
                    func="worker.agents.evening_review_agent",
                    trigger="cron",
                    hour=hour,
                    minute=minute,
                    timezone=user_tz,
                    args=[str(user_id)],
                    id=f"evening_review_{user_id}",
                    replace_existing=True,
                )

            elif agent_name == "weekly_summary":
                schedule_info = agent["schedule"]
                day_of_week = schedule_info["day_of_week"]
                schedule_time = schedule_info["time"]
                parts = schedule_time.split(":")
                hour, minute = int(parts[0]), int(parts[1])

                days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                day_str = days[day_of_week]

                scheduler.add_job(
                    func="worker.agents.weekly_summary_agent",
                    trigger="cron",
                    day_of_week=day_str,
                    hour=hour,
                    minute=minute,
                    timezone=user_tz,
                    args=[str(user_id)],
                    id=f"weekly_summary_{user_id}",
                    replace_existing=True,
                )

        except Exception as exc:
            logger.error(
                "failed_to_reconfigure_agent",
                agent=agent_name,
                user_id=str(user_id),
                error=str(exc),
            )

    logger.info("agent_schedules_reconfigured", user_id=str(user_id))
