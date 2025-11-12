from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, validator
import pytz
from dateutil.rrule import rrulestr


class CalendarEventCreate(BaseModel):
    """Schema for creating a calendar event."""

    schema_version: Literal["1.0"] = "1.0"
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    starts_at: datetime
    ends_at: Optional[datetime] = None
    timezone: str = Field("UTC", min_length=2, max_length=64)
    location_text: Optional[str] = Field(None, max_length=512)
    rrule: Optional[str] = None

    @validator("timezone")
    def validate_timezone(cls, value: str) -> str:
        try:
            pytz.timezone(value)
        except pytz.UnknownTimeZoneError as exc:  # pragma: no cover - validation
            raise ValueError(f"Invalid timezone: {value}") from exc
        return value

    @validator("rrule")
    def validate_rrule(cls, value: Optional[str], values):
        if value is None or value == "":
            return None
        starts_at: datetime | None = values.get("starts_at")
        try:
            if starts_at is not None:
                rrulestr(value, dtstart=starts_at)
            else:
                rrulestr(value)
        except Exception as exc:  # pragma: no cover - validation
            raise ValueError(f"Invalid RRULE: {value}") from exc
        return value


class CalendarEventUpdate(BaseModel):
    """Schema for updating a calendar event."""

    schema_version: Literal["1.0"] = "1.0"
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    timezone: Optional[str] = Field(None, min_length=2, max_length=64)
    location_text: Optional[str] = Field(None, max_length=512)
    rrule: Optional[str] = None
    status: Optional[str] = Field(
        None,
        description="confirmed, tentative, cancelled",
    )

    @validator("timezone")
    def validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            pytz.timezone(value)
        except pytz.UnknownTimeZoneError as exc:  # pragma: no cover - validation
            raise ValueError(f"Invalid timezone: {value}") from exc
        return value

    @validator("rrule")
    def validate_rrule(cls, value: Optional[str], values):
        if value is None:
            return None
        starts_at: datetime | None = values.get("starts_at")
        try:
            if value:
                if starts_at is not None:
                    rrulestr(value, dtstart=starts_at)
                else:
                    rrulestr(value)
            else:
                return None
        except Exception as exc:  # pragma: no cover - validation
            raise ValueError(f"Invalid RRULE: {value}") from exc
        return value


class CalendarEventResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str]
    starts_at: datetime
    ends_at: Optional[datetime]
    timezone: str
    location_text: Optional[str]
    rrule: Optional[str]
    status: str
    source: str
    created_at: datetime
    updated_at: datetime


class CalendarEventInstance(CalendarEventResponse):
    is_recurring_instance: bool = False
