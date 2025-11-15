from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog
from dateutil.rrule import rrulestr

from api.models.calendar import CalendarEventCreate, CalendarEventUpdate

logger = structlog.get_logger()


class CalendarService:
    """Service layer for calendar event management."""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _serialize_event(record) -> dict:
        """Convert database record to JSON-serializable dict."""
        return {
            "id": str(record["id"]),
            "user_id": str(record["user_id"]),
            "title": record["title"],
            "description": record["description"],
            "starts_at": record["starts_at"].isoformat() if record["starts_at"] else None,
            "ends_at": record["ends_at"].isoformat() if record["ends_at"] else None,
            "timezone": record["timezone"],
            "location_text": record["location_text"],
            "rrule": record["rrule"],
            "status": record["status"],
            "source": record["source"],
            "category_id": str(record["category_id"]) if record.get("category_id") else None,
            "category_name": record.get("category_name"),
            "created_at": record["created_at"].isoformat() if record["created_at"] else None,
            "updated_at": record["updated_at"].isoformat() if record["updated_at"] else None,
        }

    async def create_event(self, user_id: UUID, data: CalendarEventCreate) -> dict:
        """Create a new calendar event for a user."""
        starts_at = data.starts_at
        ends_at = data.ends_at or (starts_at + timedelta(hours=1))

        if ends_at <= starts_at:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "End time must be after start time",
                },
            }

        # Validate category if provided
        if data.category_id:
            category = await self.db.fetchrow(
                "SELECT id, user_id FROM event_categories WHERE id = $1",
                data.category_id,
            )
            if not category or category["user_id"] != user_id:
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_CATEGORY",
                        "message": "Category not found for this user",
                    },
                }

        if data.rrule:
            try:
                # Validate recurrence does not explode
                rule = rrulestr(data.rrule, dtstart=starts_at)
                horizon = starts_at + timedelta(days=730)
                instances = list(rule.between(starts_at, horizon, inc=True))
                if len(instances) > 1000:
                    return {
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "RRULE would generate more than 1000 instances in two years",
                        },
                    }
            except Exception as exc:
                logger.warning("calendar_rrule_invalid", error=str(exc))
                return {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Invalid RRULE: {exc}",
                    },
                }

        record = await self.db.fetchrow(
            """
            INSERT INTO calendar_events (
                user_id, title, description, starts_at, ends_at, timezone,
                location_text, rrule, category_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *
            """,
            user_id,
            data.title,
            data.description,
            starts_at,
            ends_at,
            data.timezone,
            data.location_text,
            data.rrule,
            data.category_id,
        )

        logger.info(
            "calendar_event_created",
            user_id=str(user_id),
            event_id=str(record["id"]),
            title=data.title,
            starts_at=starts_at.isoformat(),
            rrule=data.rrule,
        )

        return {"success": True, "data": self._serialize_event(record)}

    async def get_event(self, event_id: UUID) -> Optional[dict]:
        record = await self.db.fetchrow(
            "SELECT * FROM calendar_events WHERE id = $1",
            event_id,
        )
        return dict(record) if record else None

    async def update_event(
        self,
        event_id: UUID,
        user_id: UUID,
        data: CalendarEventUpdate,
    ) -> dict:
        existing = await self.db.fetchrow(
            "SELECT * FROM calendar_events WHERE id = $1 AND user_id = $2",
            event_id,
            user_id,
        )
        if not existing:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Event not found",
                },
            }

        update_payload = data.dict(exclude_unset=True)
        update_payload.pop("schema_version", None)

        if not update_payload:
            return {"success": True, "data": self._serialize_event(existing)}

        starts_at = update_payload.get("starts_at", existing["starts_at"])
        ends_at = update_payload.get("ends_at", existing["ends_at"])

        if "status" in update_payload:
            if update_payload["status"] not in {"confirmed", "tentative", "cancelled"}:
                return {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Status must be confirmed, tentative, or cancelled",
                    },
                }

        # Validate category if being updated
        if "category_id" in update_payload and update_payload["category_id"] is not None:
            category = await self.db.fetchrow(
                "SELECT id, user_id FROM event_categories WHERE id = $1",
                update_payload["category_id"],
            )
            if not category or category["user_id"] != user_id:
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_CATEGORY",
                        "message": "Category not found for this user",
                    },
                }

        if ends_at is None and existing["ends_at"] is None:
            ends_at = starts_at + timedelta(hours=1)
            update_payload["ends_at"] = ends_at

        if ends_at is not None and ends_at <= starts_at:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "End time must be after start time",
                },
            }

        if "rrule" in update_payload:
            rrule_value = update_payload["rrule"]
            if not rrule_value:
                update_payload["rrule"] = None
            else:
                try:
                    rule = rrulestr(rrule_value, dtstart=starts_at)
                    horizon = starts_at + timedelta(days=730)
                    instances = list(rule.between(starts_at, horizon, inc=True))
                    if len(instances) > 1000:
                        return {
                            "success": False,
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "RRULE would generate more than 1000 instances in two years",
                            },
                        }
                except Exception as exc:
                    logger.warning("calendar_rrule_invalid", error=str(exc))
                    return {
                        "success": False,
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": f"Invalid RRULE: {exc}",
                        },
                    }

        fields = []
        values = []
        idx = 1
        for key, value in update_payload.items():
            fields.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
        fields.append(f"updated_at = NOW()")
        values.extend([event_id, user_id])

        query = f"""
            UPDATE calendar_events
            SET {', '.join(fields)}
            WHERE id = ${idx} AND user_id = ${idx + 1}
            RETURNING *
        """

        record = await self.db.fetchrow(query, *values)

        if record and record["status"] == "cancelled":
            await self.db.execute(
                "UPDATE reminders SET calendar_event_id = NULL WHERE calendar_event_id = $1",
                event_id,
            )

        logger.info(
            "calendar_event_updated",
            event_id=str(event_id),
            user_id=str(user_id),
            fields=list(update_payload.keys()),
        )

        return {"success": True, "data": self._serialize_event(record)}

    async def cancel_event(self, event_id: UUID, user_id: UUID) -> dict:
        result = await self.update_event(
            event_id,
            user_id,
            CalendarEventUpdate(status="cancelled"),
        )
        if result.get("success"):
            logger.info(
                "calendar_event_cancelled",
                event_id=str(event_id),
                user_id=str(user_id),
            )
        return result

    async def list_events(
        self,
        user_id: UUID,
        start: datetime,
        end: datetime,
        status: Optional[str] = None,
    ) -> dict:
        if start >= end:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Start must be before end",
                },
            }

        status_filter = ""
        params = [user_id, start, end]
        if status:
            if status not in {"confirmed", "tentative", "cancelled"}:
                return {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid status filter",
                    },
                }
            status_filter = "AND ce.status = $4"
            params.append(status)
        else:
            status_filter = "AND ce.status != 'cancelled'"

        query = f"""
            SELECT ce.*, ec.name as category_name
            FROM calendar_events ce
            LEFT JOIN event_categories ec ON ce.category_id = ec.id
            WHERE ce.user_id = $1
              {status_filter}
              AND (
                    ce.rrule IS NOT NULL
                    OR (
                        ce.starts_at <= $3
                        AND (ce.ends_at IS NULL OR ce.ends_at >= $2)
                    )
                )
            ORDER BY ce.starts_at ASC
        """

        records = await self.db.fetch(query, *params)

        events = []
        total_recurring_instances = 0
        for record in records:
            event = dict(record)
            if event.get("rrule"):
                try:
                    rule = rrulestr(event["rrule"], dtstart=event["starts_at"])
                    duration = (
                        (event["ends_at"] - event["starts_at"])
                        if event.get("ends_at")
                        else timedelta(hours=1)
                    )
                    occurrences = rule.between(start, end, inc=True)
                    if total_recurring_instances + len(occurrences) > 1000:
                        allowed = max(0, 1000 - total_recurring_instances)
                        if allowed < len(occurrences):
                            logger.warning(
                                "calendar_rrule_expansion_limited",
                                event_id=str(event["id"]),
                                requested=len(occurrences),
                                allowed=allowed,
                            )
                        occurrences = occurrences[:allowed]
                    total_recurring_instances += len(occurrences)
                    for occurrence in occurrences:
                        instance = dict(event)
                        instance["starts_at"] = occurrence
                        instance["ends_at"] = occurrence + duration
                        instance["is_recurring_instance"] = True
                        events.append(instance)
                except Exception as exc:
                    logger.error(
                        "calendar_rrule_expansion_failed",
                        event_id=str(event["id"]),
                        error=str(exc),
                    )
            else:
                events.append(event)

        events.sort(key=lambda evt: evt["starts_at"])

        return {
            "success": True,
            "data": {
                "events": events,
                "count": len(events),
            },
        }

    async def link_reminder_to_event(
        self,
        user_id: UUID,
        event_id: UUID,
        reminder_id: UUID,
    ) -> dict:
        event = await self.db.fetchrow(
            "SELECT id, user_id, status FROM calendar_events WHERE id = $1",
            event_id,
        )
        if not event or event["user_id"] != user_id:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Event not found",
                },
            }
        if event["status"] == "cancelled":
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Cannot link reminders to cancelled events",
                },
            }

        reminder = await self.db.fetchrow(
            "SELECT id, user_id FROM reminders WHERE id = $1",
            reminder_id,
        )
        if not reminder or reminder["user_id"] != user_id:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Reminder not found",
                },
            }

        await self.db.execute(
            "UPDATE reminders SET calendar_event_id = $1, updated_at = NOW() WHERE id = $2",
            event_id,
            reminder_id,
        )

        logger.info(
            "calendar_reminder_linked",
            event_id=str(event_id),
            reminder_id=str(reminder_id),
            user_id=str(user_id),
        )

        return {
            "success": True,
            "data": {
                "event_id": str(event_id),
                "reminder_id": str(reminder_id),
                "linked": True,
            },
        }

    async def unlink_reminder_from_event(
        self,
        user_id: UUID,
        event_id: UUID,
        reminder_id: UUID,
    ) -> dict:
        reminder = await self.db.fetchrow(
            "SELECT id, user_id, calendar_event_id FROM reminders WHERE id = $1",
            reminder_id,
        )
        if not reminder or reminder["user_id"] != user_id:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Reminder not found",
                },
            }
        if reminder["calendar_event_id"] != event_id:
            return {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Reminder is not linked to this event",
                },
            }

        await self.db.execute(
            "UPDATE reminders SET calendar_event_id = NULL, updated_at = NOW() WHERE id = $1",
            reminder_id,
        )

        logger.info(
            "calendar_reminder_unlinked",
            event_id=str(event_id),
            reminder_id=str(reminder_id),
            user_id=str(user_id),
        )

        return {
            "success": True,
            "data": {
                "event_id": str(event_id),
                "reminder_id": str(reminder_id),
                "linked": False,
            },
        }
