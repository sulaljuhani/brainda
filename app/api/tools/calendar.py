from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog

from api.metrics import tool_calls_total
from api.models.calendar import CalendarEventCreate, CalendarEventUpdate
from api.services.calendar_service import CalendarService

logger = structlog.get_logger()

CALENDAR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a calendar event with optional recurrence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "starts_at": {"type": "string", "description": "ISO8601 UTC timestamp"},
                    "ends_at": {"type": "string", "description": "ISO8601 UTC timestamp"},
                    "timezone": {"type": "string"},
                    "location_text": {"type": "string"},
                    "rrule": {"type": "string"},
                },
                "required": ["title", "starts_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_calendar_event",
            "description": "Update fields on an existing calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "starts_at": {"type": "string"},
                    "ends_at": {"type": "string"},
                    "status": {"type": "string", "enum": ["confirmed", "tentative", "cancelled"]},
                    "timezone": {"type": "string"},
                    "location_text": {"type": "string"},
                    "rrule": {"type": "string"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Cancel a calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "List calendar events in a time window, expanding recurrences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "link_reminder_to_event",
            "description": "Associate an existing reminder with a calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string"},
                    "reminder_id": {"type": "string"},
                },
                "required": ["event_id", "reminder_id"],
            },
        },
    },
]


def _parse_datetime(value: Any) -> datetime:
    """Parse ISO8601 timestamps accepting trailing Z."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    raise ValueError("Unsupported datetime format")


async def execute_calendar_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: UUID,
    db,
) -> dict:
    """Execute calendar tool functions used by the chat orchestration layer."""
    service = CalendarService(db)
    status = "error"
    try:
        if tool_name == "create_calendar_event":
            payload = CalendarEventCreate(**arguments)
            result = await service.create_event(user_id, payload)
            status = "success" if result.get("success") else "error"
            return result

        if tool_name == "update_calendar_event":
            event_id = UUID(arguments["event_id"])
            update_payload = {k: v for k, v in arguments.items() if k != "event_id"}
            payload = CalendarEventUpdate(**update_payload)
            result = await service.update_event(event_id, user_id, payload)
            status = "success" if result.get("success") else "error"
            return result

        if tool_name == "delete_calendar_event":
            event_id = UUID(arguments["event_id"])
            result = await service.cancel_event(event_id, user_id)
            status = "success" if result.get("success") else "error"
            return result

        if tool_name == "list_calendar_events":
            start_date = _parse_datetime(arguments["start_date"])
            end_date = _parse_datetime(arguments["end_date"])
            status_filter: Optional[str] = arguments.get("status")
            result = await service.list_events(user_id, start_date, end_date, status_filter)
            status = "success" if result.get("success") else "error"
            return result

        if tool_name == "link_reminder_to_event":
            event_id = UUID(arguments["event_id"])
            reminder_id = UUID(arguments["reminder_id"])
            result = await service.link_reminder_to_event(user_id, event_id, reminder_id)
            status = "success" if result.get("success") else "error"
            return result

        logger.warning("calendar_tool_not_found", tool=tool_name)
        return {
            "success": False,
            "error": {
                "code": "UNKNOWN_TOOL",
                "message": f"Tool {tool_name} not implemented",
            },
        }

    except Exception as exc:  # pragma: no cover - defensive programming
        logger.error("calendar_tool_failed", tool=tool_name, error=str(exc))
        return {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
            },
        }
    finally:
        tool_calls_total.labels(tool_name=tool_name or "unknown", status=status).inc()
