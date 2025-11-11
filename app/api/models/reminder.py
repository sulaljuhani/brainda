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

class ReminderUpdate(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    body: Optional[str] = None
    due_at_utc: Optional[datetime] = None
    due_at_local: Optional[time] = None
    timezone: Optional[str] = None
    repeat_rrule: Optional[str] = None
    status: Optional[str] = None

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
    created_at: datetime
    updated_at: datetime

class ReminderSnoozeRequest(BaseModel):
    duration_minutes: int = Field(..., gt=0, le=1440)
