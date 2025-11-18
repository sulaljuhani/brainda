"""Analysis tools - Generate summaries and insights from user data."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from api.metrics import tool_calls_total
from api.services.task_service import TaskService
from api.services.calendar_service import CalendarService

logger = structlog.get_logger()

ANALYSIS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_daily_summary",
            "description": "Generate a summary of today's tasks, events, and accomplishments",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to summarize (ISO format, default: today)"
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_productivity",
            "description": "Analyze productivity patterns and completion rates",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "enum": ["today", "this_week", "this_month"],
                        "description": "Time period to analyze"
                    },
                },
            },
        },
    },
]


async def execute_analysis_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: UUID,
    db,
) -> dict[str, Any]:
    """Execute analysis-related tools."""
    tool_calls_total.labels(tool_name=tool_name, status="pending").inc()

    try:
        if tool_name == "generate_daily_summary":
            result = await generate_daily_summary(user_id, arguments.get("date"), db)
            tool_calls_total.labels(tool_name=tool_name, status="success").inc()
            return result

        elif tool_name == "analyze_productivity":
            result = await analyze_productivity(user_id, arguments.get("period", "today"), db)
            tool_calls_total.labels(tool_name=tool_name, status="success").inc()
            return result

        else:
            tool_calls_total.labels(tool_name=tool_name, status="error").inc()
            return {
                "success": False,
                "error": {
                    "code": "UNKNOWN_TOOL",
                    "message": f"Unknown analysis tool: {tool_name}",
                },
            }

    except Exception as exc:
        logger.error("analysis_tool_failed", tool=tool_name, error=str(exc))
        tool_calls_total.labels(tool_name=tool_name, status="error").inc()
        return {
            "success": False,
            "error": {"code": "EXECUTION_ERROR", "message": str(exc)},
        }


async def generate_daily_summary(user_id: UUID, date_str: str | None, db) -> dict:
    """Generate a summary of tasks and events for a given date."""
    try:
        # Parse date or default to today
        if date_str:
            target_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            target_date = datetime.now()

        task_service = TaskService(db)
        calendar_service = CalendarService(db)

        # Get tasks for the day
        all_tasks = await task_service.list_tasks(user_id, limit=1000)

        # Filter tasks by date
        tasks_today = []
        completed_today = []
        for task in all_tasks:
            if task.get("starts_at"):
                task_date = task["starts_at"].date() if hasattr(task["starts_at"], "date") else task["starts_at"]
                target_date_only = target_date.date()
                if task_date == target_date_only:
                    tasks_today.append(task)
                    if task.get("status") == "completed":
                        completed_today.append(task)

        # Get events for the day
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        events_result = await calendar_service.list_events(user_id, start_of_day, end_of_day)
        events = events_result.get("data", []) if events_result.get("success") else []

        summary = {
            "date": target_date.date().isoformat(),
            "tasks": {
                "total": len(tasks_today),
                "completed": len(completed_today),
                "pending": len(tasks_today) - len(completed_today),
                "list": [
                    {
                        "title": t["title"],
                        "status": t["status"],
                        "category": t.get("category_name"),
                    }
                    for t in tasks_today[:10]  # Limit to 10 for brevity
                ],
            },
            "events": {
                "total": len(events),
                "list": [
                    {
                        "title": e.get("title"),
                        "starts_at": e.get("starts_at"),
                        "location": e.get("location_text"),
                    }
                    for e in events[:10]  # Limit to 10 for brevity
                ],
            },
        }

        return {"success": True, "data": summary}

    except Exception as exc:
        logger.error("generate_daily_summary_failed", error=str(exc))
        return {
            "success": False,
            "error": {"code": "SUMMARY_FAILED", "message": str(exc)},
        }


async def analyze_productivity(user_id: UUID, period: str, db) -> dict:
    """Analyze productivity patterns over a time period."""
    try:
        task_service = TaskService(db)

        # Determine time range
        now = datetime.now()
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == "this_week":
            # Start of week (Monday)
            start_date = now - timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == "this_month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        else:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now

        # Get all tasks
        all_tasks = await task_service.list_tasks(user_id, limit=1000)

        # Filter by time range and calculate stats
        tasks_in_period = []
        completed_in_period = []
        for task in all_tasks:
            task_created = task.get("created_at")
            if task_created and start_date <= task_created <= end_date:
                tasks_in_period.append(task)
                if task.get("status") == "completed":
                    completed_in_period.append(task)

        completion_rate = (
            len(completed_in_period) / len(tasks_in_period) * 100
            if tasks_in_period
            else 0
        )

        # Category breakdown
        category_stats = {}
        for task in tasks_in_period:
            cat = task.get("category_name", "Uncategorized")
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "completed": 0}
            category_stats[cat]["total"] += 1
            if task.get("status") == "completed":
                category_stats[cat]["completed"] += 1

        analysis = {
            "period": period,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "tasks_created": len(tasks_in_period),
            "tasks_completed": len(completed_in_period),
            "completion_rate": round(completion_rate, 1),
            "by_category": category_stats,
        }

        return {"success": True, "data": analysis}

    except Exception as exc:
        logger.error("analyze_productivity_failed", error=str(exc))
        return {
            "success": False,
            "error": {"code": "ANALYSIS_FAILED", "message": str(exc)},
        }
