from pydantic import BaseModel, Field, validator
from datetime import datetime, time
from typing import Optional, Literal
from uuid import UUID

class ReminderCreate(BaseModel):
    """Schema v1.0 for creating reminders"""
    schema_version: Literal["1.0"] = "1.0"
    title: str = Field(..., min_length=1, max_length=200)
    body: Optional[str] = Field(None, max_length=2000)
    due_at_utc: datetime
    due_at_local: time
    timezone: str
    repeat_rrule: Optional[str] = None
    note_id: Optional[UUID] = None
    calendar_event_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    offset_days: Optional[int] = None
    offset_type: Optional[Literal["before", "after"]] = None

    @validator('timezone')
    def validate_timezone(cls, v):
        import pytz
        try:
            pytz.timezone(v)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Invalid timezone: {v}")
        return v

    @validator('repeat_rrule')
    def validate_rrule(cls, v):
        if v is None:
            return v
        from dateutil.rrule import rrulestr
        try:
            rrulestr(v)
        except:
            raise ValueError(f"Invalid RRULE: {v}")
        return v

    @validator('offset_type')
    def validate_offset_consistency(cls, v, values):
        """Ensure offset_days and offset_type are both set or both null"""
        offset_days = values.get('offset_days')
        if (offset_days is None) != (v is None):
            raise ValueError("offset_days and offset_type must both be set or both be null")
        return v

    @validator('task_id')
    def validate_single_link(cls, v, values):
        """Ensure reminder is linked to at most one entity (task OR event)"""
        calendar_event_id = values.get('calendar_event_id')
        if v and calendar_event_id:
            raise ValueError("Reminder cannot be linked to both a task and an event")
        return v

class ReminderUpdate(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    body: Optional[str] = None
    due_at_utc: Optional[datetime] = None
    due_at_local: Optional[time] = None
    timezone: Optional[str] = None
    repeat_rrule: Optional[str] = None
    status: Optional[str] = None
    calendar_event_id: Optional[UUID] = None
    category_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    offset_days: Optional[int] = None
    offset_type: Optional[Literal["before", "after"]] = None

class ReminderResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    body: Optional[str]
    due_at_utc: datetime
    due_at_local: time
    timezone: str
    repeat_rrule: Optional[str]
    status: str
    note_id: Optional[UUID]
    calendar_event_id: Optional[UUID]
    category_id: Optional[UUID]
    category_name: Optional[str]
    task_id: Optional[UUID]
    task_title: Optional[str]
    event_title: Optional[str]
    offset_days: Optional[int]
    offset_type: Optional[str]
    created_at: datetime
    updated_at: datetime

class ReminderSnoozeRequest(BaseModel):
    duration_minutes: int = Field(..., gt=0, le=1440)
