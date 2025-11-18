"""What's Next service - Intelligent suggestions for what to do next."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import UUID

import structlog

from api.tools.db_helper import get_db_connection
from api.services.task_service import TaskService
from api.services.calendar_service import CalendarService
from api.services.orchestration_service import ToolOrchestrationService

logger = structlog.get_logger()


class WhatsNextService:
    """Service for generating intelligent 'What's Next' suggestions."""

    async def get_whats_next(self, user_id: UUID, db) -> dict:
        """
        Generate intelligent suggestions for what to do next.

        Analyzes:
        - Overdue tasks
        - Upcoming events (next 2 hours)
        - High-priority tasks
        - Tasks due today
        - Pending reminders
        - Context-based suggestions

        Returns:
            dict with suggested next actions
        """
        try:
            task_service = TaskService(db)
            calendar_service = CalendarService(db)

            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            next_2_hours = now + timedelta(hours=2)

            # Get all active tasks
            all_tasks = await task_service.list_tasks(user_id, status="active", limit=1000)

            # Categorize tasks
            overdue_tasks = []
            due_today_tasks = []
            high_priority_tasks = []

            for task in all_tasks:
                # Check if overdue
                if task.get("ends_at"):
                    ends_at = task["ends_at"]
                    if isinstance(ends_at, str):
                        ends_at = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                    if ends_at < now:
                        overdue_tasks.append(task)
                        continue

                # Check if due today
                if task.get("ends_at"):
                    ends_at = task["ends_at"]
                    if isinstance(ends_at, str):
                        ends_at = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
                    if today_start <= ends_at < today_end:
                        due_today_tasks.append(task)

                # Check if high priority (you could extend this with a priority field)
                if task.get("category_name") in ["urgent", "important", "high-priority"]:
                    high_priority_tasks.append(task)

            # Get upcoming events (next 2 hours)
            events_result = await calendar_service.list_events(user_id, now, next_2_hours)
            upcoming_events = events_result.get("data", []) if events_result.get("success") else []

            # Get pending reminders
            async with get_db_connection() as conn:
                reminders = await conn.fetch(
                    """
                    SELECT id, title, body, due_at_utc
                    FROM reminders
                    WHERE user_id = $1
                      AND status = 'active'
                      AND due_at_utc > $2
                      AND due_at_utc < $3
                    ORDER BY due_at_utc ASC
                    LIMIT 5
                    """,
                    user_id,
                    now,
                    next_2_hours,
                )

            # Build suggestions
            suggestions = []
            priority_score = 0

            # 1. Most urgent: Overdue tasks
            if overdue_tasks:
                suggestions.append({
                    "type": "overdue_task",
                    "priority": "urgent",
                    "title": f"You have {len(overdue_tasks)} overdue task(s)",
                    "description": f"Focus on: {overdue_tasks[0]['title']}",
                    "action": {
                        "type": "view_task",
                        "task_id": str(overdue_tasks[0]["id"]),
                    },
                    "tasks": [
                        {
                            "id": str(t["id"]),
                            "title": t["title"],
                            "ends_at": t.get("ends_at"),
                        }
                        for t in overdue_tasks[:3]
                    ],
                })
                priority_score += 10

            # 2. Upcoming event (next 2 hours)
            if upcoming_events:
                next_event = upcoming_events[0]
                suggestions.append({
                    "type": "upcoming_event",
                    "priority": "high",
                    "title": "Upcoming event",
                    "description": f"{next_event.get('title')} at {next_event.get('starts_at')}",
                    "action": {
                        "type": "view_event",
                        "event_id": str(next_event.get("id")),
                    },
                    "event": {
                        "id": str(next_event.get("id")),
                        "title": next_event.get("title"),
                        "starts_at": next_event.get("starts_at"),
                        "location": next_event.get("location_text"),
                    },
                })
                priority_score += 8

            # 3. Pending reminders (next 2 hours)
            if reminders:
                next_reminder = reminders[0]
                suggestions.append({
                    "type": "pending_reminder",
                    "priority": "high",
                    "title": "Upcoming reminder",
                    "description": f"{next_reminder['title']} at {next_reminder['due_at_utc']}",
                    "action": {
                        "type": "view_reminder",
                        "reminder_id": str(next_reminder["id"]),
                    },
                })
                priority_score += 7

            # 4. Tasks due today
            if due_today_tasks:
                suggestions.append({
                    "type": "due_today",
                    "priority": "normal",
                    "title": f"{len(due_today_tasks)} task(s) due today",
                    "description": f"Start with: {due_today_tasks[0]['title']}",
                    "action": {
                        "type": "view_task",
                        "task_id": str(due_today_tasks[0]["id"]),
                    },
                    "tasks": [
                        {
                            "id": str(t["id"]),
                            "title": t["title"],
                            "ends_at": t.get("ends_at"),
                        }
                        for t in due_today_tasks[:5]
                    ],
                })
                priority_score += 5

            # 5. High-priority tasks
            if high_priority_tasks:
                suggestions.append({
                    "type": "high_priority",
                    "priority": "normal",
                    "title": f"{len(high_priority_tasks)} high-priority task(s)",
                    "description": f"Consider: {high_priority_tasks[0]['title']}",
                    "action": {
                        "type": "view_task",
                        "task_id": str(high_priority_tasks[0]["id"]),
                    },
                })
                priority_score += 4

            # 6. If nothing urgent, suggest reviewing notes or planning
            if not suggestions:
                suggestions.append({
                    "type": "no_urgency",
                    "priority": "low",
                    "title": "All caught up!",
                    "description": "Consider reviewing your notes or planning ahead",
                    "action": {
                        "type": "browse",
                        "url": "/notes",
                    },
                })

            # Generate AI-powered suggestion if available
            ai_suggestion = await self._generate_ai_suggestion(user_id, suggestions, db)

            return {
                "success": True,
                "data": {
                    "timestamp": now.isoformat(),
                    "priority_score": priority_score,
                    "suggestions": suggestions,
                    "ai_suggestion": ai_suggestion,
                    "summary": self._generate_summary(suggestions),
                },
            }

        except Exception as exc:
            logger.error("whats_next_failed", error=str(exc), user_id=str(user_id))
            return {
                "success": False,
                "error": {"code": "WHATS_NEXT_FAILED", "message": str(exc)},
            }

    async def _generate_ai_suggestion(self, user_id: UUID, suggestions: List[Dict], db) -> Optional[str]:
        """
        Generate AI-powered suggestion using orchestration service.

        This uses the tool orchestration to intelligently analyze the user's context
        and provide a personalized recommendation.
        """
        try:
            orchestrator = ToolOrchestrationService(user_id, db)

            # Build context from suggestions
            context_parts = []
            for suggestion in suggestions:
                context_parts.append(f"- {suggestion['title']}: {suggestion['description']}")

            context = "\n".join(context_parts) if context_parts else "No immediate tasks or events"

            prompt = f"""Based on the user's current situation, provide a brief, actionable recommendation
for what they should focus on next. Be concise (1-2 sentences).

Current situation:
{context}

Provide a friendly, motivating suggestion."""

            result = await orchestrator.execute_user_request(prompt, max_iterations=1)

            return result.get("response", "")

        except Exception as exc:
            logger.warning("ai_suggestion_failed", error=str(exc))
            return None

    def _generate_summary(self, suggestions: List[Dict]) -> str:
        """Generate a text summary of suggestions."""
        if not suggestions:
            return "You're all caught up! No urgent items."

        urgent_count = sum(1 for s in suggestions if s.get("priority") == "urgent")
        high_count = sum(1 for s in suggestions if s.get("priority") == "high")

        if urgent_count > 0:
            return f"⚠️ You have {urgent_count} urgent item(s) that need attention"
        elif high_count > 0:
            return f"📌 You have {high_count} high-priority item(s) coming up soon"
        else:
            return f"✅ You have {len(suggestions)} item(s) to consider"
