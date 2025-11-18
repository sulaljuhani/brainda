"""Scheduled autonomous agents for proactive assistance."""
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog

from worker.tasks import celery_app
from api.services.orchestration_service import ToolOrchestrationService
from api.services.agent_notification_service import AgentNotificationService
from common.db import connect_with_json_codec

logger = structlog.get_logger()


# ============ MORNING BRIEFING AGENT ============

@celery_app.task(name="agents.morning_briefing")
def morning_briefing_agent(user_id: str):
    """
    Morning briefing agent - Runs at 7:00 AM daily.

    Provides:
    - Today's schedule (events, meetings)
    - High-priority tasks
    - Pending reminders
    - Motivational message
    """
    asyncio.run(_run_morning_briefing(UUID(user_id)))


async def _run_morning_briefing(user_id: UUID):
    """Generate and deliver morning briefing."""
    logger.info("morning_briefing_start", user_id=str(user_id))

    try:
        # Get database connection
        db = await connect_with_json_codec(os.getenv("DATABASE_URL"))

        try:
            # Create orchestration service
            orchestrator = ToolOrchestrationService(user_id, db)

            # Generate briefing using tools
            briefing_prompt = """
            Generate a morning briefing for the user. Include:
            1. Today's calendar events (use list_calendar_events)
            2. High-priority or overdue tasks (use list_tasks)
            3. Pending reminders (use list_reminders)
            4. A brief motivational message

            Format it clearly and concisely as a morning briefing.
            """

            result = await orchestrator.execute_user_request(briefing_prompt, max_iterations=3)

            # Send notification
            notification_service = AgentNotificationService()
            await notification_service.create_notification(
                user_id=user_id,
                title="☀️ Good morning! Here's your briefing",
                body=result.get("response", "Unable to generate briefing"),
                notification_type="morning_briefing",
                priority="high",
            )

            logger.info("morning_briefing_complete", user_id=str(user_id))

        finally:
            await db.close()

    except Exception as exc:
        logger.error("morning_briefing_failed", user_id=str(user_id), error=str(exc))


# ============ EVENING REVIEW AGENT ============

@celery_app.task(name="agents.evening_review")
def evening_review_agent(user_id: str):
    """
    Evening review agent - Runs at 8:00 PM daily.

    Provides:
    - Summary of today's accomplishments
    - Tasks completed vs planned
    - Tomorrow's preview
    - Suggestions for improvement
    """
    asyncio.run(_run_evening_review(UUID(user_id)))


async def _run_evening_review(user_id: UUID):
    """Generate and deliver evening review."""
    logger.info("evening_review_start", user_id=str(user_id))

    try:
        # Get database connection
        db = await connect_with_json_codec(os.getenv("DATABASE_URL"))

        try:
            # Create orchestration service
            orchestrator = ToolOrchestrationService(user_id, db)

            # Generate review using tools
            review_prompt = """
            Generate an evening review for the user. Include:
            1. Tasks completed today (use list_tasks with status="completed" and generate_daily_summary)
            2. Tasks that were postponed (no judgment, just awareness)
            3. Preview of tomorrow's important tasks and events
            4. One productivity tip or reflection

            Keep it positive and actionable.
            """

            result = await orchestrator.execute_user_request(review_prompt, max_iterations=3)

            # Send notification
            notification_service = AgentNotificationService()
            await notification_service.create_notification(
                user_id=user_id,
                title="🌙 Evening Review",
                body=result.get("response", "Unable to generate review"),
                notification_type="evening_review",
                priority="normal",
            )

            logger.info("evening_review_complete", user_id=str(user_id))

        finally:
            await db.close()

    except Exception as exc:
        logger.error("evening_review_failed", user_id=str(user_id), error=str(exc))


# ============ WEEKLY SUMMARY AGENT ============

@celery_app.task(name="agents.weekly_summary")
def weekly_summary_agent(user_id: str):
    """
    Weekly summary agent - Runs Sunday at 6:00 PM.

    Provides:
    - Week's accomplishments
    - Productivity metrics
    - Insights and patterns
    - Goals for next week
    """
    asyncio.run(_run_weekly_summary(UUID(user_id)))


async def _run_weekly_summary(user_id: UUID):
    """Generate weekly summary."""
    logger.info("weekly_summary_start", user_id=str(user_id))

    try:
        # Get database connection
        db = await connect_with_json_codec(os.getenv("DATABASE_URL"))

        try:
            # Create orchestration service
            orchestrator = ToolOrchestrationService(user_id, db)

            # Generate summary using tools
            summary_prompt = """
            Generate a comprehensive weekly summary. Use the analyze_productivity tool
            for insights. Include:

            1. Tasks completed this week (celebrate progress!)
            2. Key achievements and wins
            3. Productivity patterns (most productive days)
            4. Areas for improvement
            5. Suggested goals for next week

            Make it insightful and motivating.
            """

            result = await orchestrator.execute_user_request(summary_prompt, max_iterations=3)

            # Send notification
            notification_service = AgentNotificationService()
            await notification_service.create_notification(
                user_id=user_id,
                title="📊 Your Week in Review",
                body=result.get("response", "Unable to generate summary"),
                notification_type="weekly_summary",
                priority="normal",
            )

            logger.info("weekly_summary_complete", user_id=str(user_id))

        finally:
            await db.close()

    except Exception as exc:
        logger.error("weekly_summary_failed", user_id=str(user_id), error=str(exc))


# ============ SMART SUGGESTIONS AGENT ============

@celery_app.task(name="agents.smart_suggestions")
def smart_suggestions_agent(user_id: str, context: Optional[str] = None):
    """
    Smart suggestions agent - Runs when triggered by user activity.

    Analyzes user's notes and suggests:
    - Actionable tasks extracted from notes
    - Related notes to link
    - Knowledge gaps to fill
    """
    asyncio.run(_generate_smart_suggestions(UUID(user_id), context))


async def _generate_smart_suggestions(user_id: UUID, context: Optional[str] = None):
    """Generate smart suggestions from user activity."""
    logger.info("smart_suggestions_start", user_id=str(user_id))

    try:
        # Get database connection
        db = await connect_with_json_codec(os.getenv("DATABASE_URL"))

        try:
            # Create orchestration service
            orchestrator = ToolOrchestrationService(user_id, db)

            # Generate suggestions
            if context:
                suggestions_prompt = f"""
                Analyze this content and suggest actionable tasks or insights:

                {context}

                Provide 2-3 concrete, actionable suggestions based on the content.
                """
            else:
                suggestions_prompt = """
                Analyze the user's recent notes (use search_notes) and suggest:
                1. Actionable tasks that should be created
                2. Notes that could be linked together
                3. Knowledge gaps or topics to explore

                Provide 2-3 concrete suggestions.
                """

            result = await orchestrator.execute_user_request(suggestions_prompt, max_iterations=3)

            # Only send notification if there are actionable suggestions
            if result.get("tool_calls"):
                notification_service = AgentNotificationService()
                await notification_service.create_notification(
                    user_id=user_id,
                    title="💡 Smart Suggestions",
                    body=result.get("response", "No suggestions at this time"),
                    notification_type="smart_suggestions",
                    priority="low",
                )

            logger.info("smart_suggestions_complete", user_id=str(user_id))

        finally:
            await db.close()

    except Exception as exc:
        logger.error("smart_suggestions_failed", user_id=str(user_id), error=str(exc))


# ============ HELPER FUNCTIONS ============

async def get_all_active_users() -> list[dict]:
    """Get all active users for scheduling agents."""
    try:
        db = await connect_with_json_codec(os.getenv("DATABASE_URL"))
        try:
            # Get all users who have been active in the last 30 days
            users = await db.fetch(
                """
                SELECT DISTINCT u.id, u.username
                FROM users u
                WHERE u.created_at >= NOW() - INTERVAL '30 days'
                   OR EXISTS (
                       SELECT 1 FROM tasks t WHERE t.user_id = u.id AND t.created_at >= NOW() - INTERVAL '7 days'
                   )
                   OR EXISTS (
                       SELECT 1 FROM notes n WHERE n.user_id = u.id AND n.created_at >= NOW() - INTERVAL '7 days'
                   )
                """
            )
            return [{"id": row["id"], "username": row["username"]} for row in users]
        finally:
            await db.close()
    except Exception as exc:
        logger.error("get_active_users_failed", error=str(exc))
        return []
