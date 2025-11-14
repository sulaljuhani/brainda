from datetime import datetime, time, timedelta
from typing import Optional, Any
from uuid import UUID
import structlog

from api.models.reminder import ReminderCreate
from api.services.reminder_service import ReminderService

logger = structlog.get_logger()

# Tool schemas for LLM
REMINDER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a time-based reminder. Always infer a reasonable time if user doesn't specify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Reminder title (what to do)"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional additional details"
                    },
                    "due_at_utc": {
                        "type": "string",
                        "description": "When to fire reminder (ISO 8601 UTC)"
                    },
                    "due_at_local": {
                        "type": "string",
                        "description": "Local time HH:MM:SS"
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone (e.g. America/New_York)"
                    },
                    "repeat_rrule": {
                        "type": "string",
                        "description": "RRULE string for recurring reminders (optional)"
                    }
                },
                "required": ["title", "due_at_utc", "due_at_local", "timezone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "List user's reminders, optionally filtered by status",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "snoozed", "done", "cancelled"],
                        "description": "Filter by status (optional)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "snooze_reminder",
            "description": "Snooze a reminder by a duration",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {
                        "type": "string",
                        "description": "UUID of reminder to snooze"
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "enum": [15, 60, 1440],
                        "description": "How long to snooze (15min, 1hr, 1day)"
                    }
                },
                "required": ["reminder_id", "duration_minutes"]
            }
        }
    }
]

def smart_time_default(now: datetime, prompt: str) -> datetime:
    """
    Infer reasonable default time based on current time and user prompt.
    
    Examples:
    - "remind me to call the bank" -> later today (e.g. 5pm)
    - "remind me to take out the trash" -> in the evening (e.g. 8pm)
    - "remind me tomorrow" -> tomorrow at 9am
    """
    
    # Simple keyword matching for now
    if "tomorrow" in prompt.lower():
        return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    
    if "evening" in prompt.lower() or "tonight" in prompt.lower():
        return now.replace(hour=20, minute=0, second=0, microsecond=0)

    # Default to later today
    if now.hour < 17:
        return now.replace(hour=17, minute=0, second=0, microsecond=0)
    else:
        return now + timedelta(hours=1)


async def execute_reminder_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: UUID,
    db,
) -> dict:
    """Execute reminder tool functions used by the chat orchestration layer."""
    service = ReminderService(db)

    try:
        if tool_name == "create_reminder":
            # Parse the datetime
            due_at_utc = datetime.fromisoformat(arguments["due_at_utc"].replace("Z", "+00:00"))

            # Create the reminder request
            payload = ReminderCreate(
                title=arguments["title"],
                body=arguments.get("body"),
                due_at_utc=due_at_utc,
                due_at_local=arguments.get("due_at_local"),
                timezone=arguments.get("timezone", "UTC"),
                repeat_rrule=arguments.get("repeat_rrule"),
            )

            result = await service.create_reminder(user_id, payload)
            return result

        if tool_name == "list_reminders":
            status_filter = arguments.get("status")
            reminders = await service.list_reminders(user_id, status=status_filter)
            return {
                "success": True,
                "data": reminders,
                "total": len(reminders),
            }

        if tool_name == "snooze_reminder":
            reminder_id = UUID(arguments["reminder_id"])
            duration_minutes = int(arguments["duration_minutes"])
            result = await service.snooze_reminder(reminder_id, user_id, duration_minutes)
            return result

        logger.warning("reminder_tool_not_found", tool=tool_name)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_TOOL",
                "message": f"Tool {tool_name} not implemented",
            },
        }

    except Exception as exc:
        logger.error("reminder_tool_failed", tool=tool_name, error=str(exc))
        return {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
            },
        }
