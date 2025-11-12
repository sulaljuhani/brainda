# System Prompt: Stage 6 - Calendar + Weekly Views

## Context

You are implementing **Stage 6** of the VIB project. The previous stages are **already complete**:

- ✅ Stages 0-4: MVP (infrastructure, chat, notes, reminders, RAG, observability)
- ✅ Stage 5: Mobile app with full idempotency

## Your Mission: Stage 6

Build an **internal calendar system** with:
- Calendar events with RRULE support for recurrence
- Weekly calendar view (web + mobile)
- Ability to link reminders to calendar events
- Tools for creating/updating/deleting events via chat

## Why This Stage Matters

Users need to:
- **Visualize their schedule**: See all events and reminders in one weekly view
- **Organize reminders**: Link "Call bank" reminder to "Banking appointment" event
- **Plan recurring activities**: "Team standup every Monday at 9am" should create event + optional reminder
- **Reduce cognitive load**: Calendar view shows the week at a glance

This prepares for Stage 7 (Google Calendar sync) by establishing our internal calendar data model.

---

## Deliverables

### 1. Database Schema

Create `migrations/005_add_calendar.sql`:

```sql
-- Stage 6: Calendar events

CREATE TABLE calendar_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,

    -- Timing (both stored for DST handling like reminders)
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,  -- NULL for all-day or no end time
    timezone TEXT NOT NULL,  -- User's timezone

    -- Location (optional, can link to locations table)
    location_id UUID REFERENCES locations(id),
    location_text TEXT,  -- Free-form location ("123 Main St" or "Zoom link")

    -- Recurrence
    rrule TEXT,  -- NULL for one-time events, RRULE string for recurring

    -- Sync metadata (for Stage 7 Google Calendar sync)
    source TEXT DEFAULT 'internal',  -- internal, google
    google_event_id TEXT UNIQUE,  -- NULL for internal events
    google_calendar_id TEXT,  -- Which Google calendar this came from

    -- Status
    status TEXT DEFAULT 'confirmed',  -- confirmed, tentative, cancelled

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Link reminders to events (optional association)
ALTER TABLE reminders
ADD COLUMN calendar_event_id UUID REFERENCES calendar_events(id) ON DELETE SET NULL;

-- Sync state for Google Calendar (Stage 7, create table now for forward compatibility)
CREATE TABLE calendar_sync_state (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    google_calendar_id TEXT,  -- Primary calendar ID
    sync_token TEXT,  -- For incremental sync
    last_sync_at TIMESTAMPTZ,
    sync_enabled BOOLEAN DEFAULT FALSE,
    sync_direction TEXT DEFAULT 'one_way',  -- one_way, two_way
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_calendar_events_user_starts ON calendar_events(user_id, starts_at);
CREATE INDEX idx_calendar_events_source ON calendar_events(source);
CREATE INDEX idx_calendar_events_google_id ON calendar_events(google_event_id) WHERE google_event_id IS NOT NULL;
CREATE INDEX idx_calendar_events_status ON calendar_events(user_id, status) WHERE status != 'cancelled';

-- Index for reminder-event associations
CREATE INDEX idx_reminders_event ON reminders(calendar_event_id) WHERE calendar_event_id IS NOT NULL;
```

---

### 2. Backend API

#### A. Data Models

**File**: `app/api/models/calendar.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID

class CalendarEventCreate(BaseModel):
    schema_version: str = "1.0"
    title: str
    description: Optional[str] = None
    starts_at: datetime  # UTC timestamp
    ends_at: Optional[datetime] = None  # UTC timestamp
    timezone: str = "UTC"
    location_text: Optional[str] = None
    rrule: Optional[str] = None  # RRULE string or None

class CalendarEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    timezone: Optional[str] = None
    location_text: Optional[str] = None
    rrule: Optional[str] = None
    status: Optional[str] = None  # confirmed, tentative, cancelled

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
```

#### B. Tools for LLM

**File**: `app/api/tools/calendar.py`

```python
from app.api.tools.base import tool, tool_success, tool_error
from dateutil.rrule import rrulestr
from datetime import datetime, timedelta

@tool(schema_version="1.0")
async def create_calendar_event(
    title: str,
    starts_at: datetime,
    timezone: str,
    user_id: UUID,
    description: str = None,
    ends_at: datetime = None,
    location_text: str = None,
    rrule: str = None,
) -> dict:
    """
    Create a calendar event.

    Args:
        title: Event title
        starts_at: Start time (UTC)
        timezone: User's timezone
        description: Optional description
        ends_at: End time (UTC), defaults to starts_at + 1 hour
        location_text: Optional location
        rrule: Optional RRULE string for recurrence

    Returns:
        Standard tool response with event data
    """
    # Validate timezone
    if not is_valid_timezone(timezone):
        return tool_error("VALIDATION_ERROR", "Invalid timezone", "timezone")

    # Validate RRULE if provided
    if rrule:
        try:
            # Parse and validate
            rule = rrulestr(rrule, dtstart=starts_at)

            # Safety: limit recurrence to 2 years
            two_years = datetime.now() + timedelta(days=730)
            instances = list(rule.between(starts_at, two_years))
            if len(instances) > 1000:
                return tool_error("VALIDATION_ERROR", "RRULE generates too many instances (>1000 in 2 years)")
        except Exception as e:
            return tool_error("VALIDATION_ERROR", f"Invalid RRULE: {str(e)}", "rrule")

    # Default end time: 1 hour after start
    if not ends_at:
        ends_at = starts_at + timedelta(hours=1)

    # Validate end > start
    if ends_at <= starts_at:
        return tool_error("VALIDATION_ERROR", "End time must be after start time")

    # Create event
    event = await db.create_calendar_event(
        user_id=user_id,
        title=title,
        description=description,
        starts_at=starts_at,
        ends_at=ends_at,
        timezone=timezone,
        location_text=location_text,
        rrule=rrule,
        source="internal",
        status="confirmed",
    )

    # Log audit
    await audit_log.log(
        user_id=user_id,
        entity_type="calendar_event",
        entity_id=event.id,
        action="create",
        new_value=event.to_dict(),
    )

    return tool_success(event.to_dict())


@tool(schema_version="1.0")
async def update_calendar_event(
    event_id: UUID,
    user_id: UUID,
    title: str = None,
    starts_at: datetime = None,
    ends_at: datetime = None,
    status: str = None,
    rrule: str = None,
) -> dict:
    """Update an existing calendar event."""

    # Fetch event
    event = await db.get_calendar_event(event_id)
    if not event:
        return tool_error("NOT_FOUND", f"Event {event_id} not found")

    # Check ownership
    if event.user_id != user_id:
        return tool_error("PERMISSION_DENIED", "You don't own this event")

    # Validate status
    if status and status not in ["confirmed", "tentative", "cancelled"]:
        return tool_error("VALIDATION_ERROR", "Invalid status", "status")

    # Update fields
    update_data = {}
    if title: update_data["title"] = title
    if starts_at: update_data["starts_at"] = starts_at
    if ends_at: update_data["ends_at"] = ends_at
    if status: update_data["status"] = status
    if rrule is not None: update_data["rrule"] = rrule  # Allow clearing RRULE

    updated = await db.update_calendar_event(event_id, update_data)

    # Audit log
    await audit_log.log(
        user_id=user_id,
        entity_type="calendar_event",
        entity_id=event_id,
        action="update",
        old_value=event.to_dict(),
        new_value=updated.to_dict(),
    )

    return tool_success(updated.to_dict())


@tool(schema_version="1.0")
async def delete_calendar_event(event_id: UUID, user_id: UUID) -> dict:
    """Delete (cancel) a calendar event."""

    event = await db.get_calendar_event(event_id)
    if not event:
        return tool_error("NOT_FOUND", f"Event {event_id} not found")

    if event.user_id != user_id:
        return tool_error("PERMISSION_DENIED", "You don't own this event")

    # Soft delete: set status to cancelled
    updated = await db.update_calendar_event(event_id, {"status": "cancelled"})

    await audit_log.log(
        user_id=user_id,
        entity_type="calendar_event",
        entity_id=event_id,
        action="delete",
        old_value=event.to_dict(),
    )

    return tool_success({"id": event_id, "status": "cancelled"})


@tool(schema_version="1.0")
async def list_calendar_events(
    user_id: UUID,
    start_date: datetime,
    end_date: datetime,
    status: str = "confirmed",
) -> dict:
    """
    List calendar events in a date range (typically 1 week for weekly view).

    Returns both one-time events and expanded RRULE instances.
    """

    events = await db.list_calendar_events(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
    )

    # Expand recurring events
    expanded = []
    for event in events:
        if event.rrule:
            # Generate instances for this date range
            rule = rrulestr(event.rrule, dtstart=event.starts_at)
            instances = list(rule.between(start_date, end_date))

            for instance_start in instances:
                duration = event.ends_at - event.starts_at if event.ends_at else timedelta(hours=1)
                expanded.append({
                    **event.to_dict(),
                    "starts_at": instance_start,
                    "ends_at": instance_start + duration,
                    "is_recurring_instance": True,
                    "parent_event_id": event.id,
                })
        else:
            expanded.append(event.to_dict())

    return tool_success({
        "events": expanded,
        "count": len(expanded),
    })


@tool(schema_version="1.0")
async def link_reminder_to_event(
    reminder_id: UUID,
    event_id: UUID,
    user_id: UUID,
) -> dict:
    """Link an existing reminder to a calendar event."""

    # Validate reminder
    reminder = await db.get_reminder(reminder_id)
    if not reminder or reminder.user_id != user_id:
        return tool_error("NOT_FOUND", "Reminder not found")

    # Validate event
    event = await db.get_calendar_event(event_id)
    if not event or event.user_id != user_id:
        return tool_error("NOT_FOUND", "Event not found")

    # Link
    await db.update_reminder(reminder_id, {"calendar_event_id": event_id})

    return tool_success({
        "reminder_id": reminder_id,
        "event_id": event_id,
        "linked": True,
    })
```

#### C. REST API Endpoints

**File**: `app/api/routers/calendar.py`

```python
from fastapi import APIRouter, Depends, Query
from datetime import datetime, timedelta
from app.api.models.calendar import *
from app.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])

@router.get("/events", response_model=dict)
async def get_events(
    start: datetime = Query(..., description="Start of date range (UTC)"),
    end: datetime = Query(..., description="End of date range (UTC)"),
    current_user = Depends(get_current_user),
):
    """
    Get calendar events in date range with RRULE expansion.

    Example: GET /api/v1/calendar/events?start=2025-01-13T00:00:00Z&end=2025-01-20T00:00:00Z
    Returns all events in that week, with recurring events expanded.
    """
    result = await list_calendar_events(
        user_id=current_user.id,
        start_date=start,
        end_date=end,
    )
    return result


@router.post("/events", response_model=dict)
async def create_event(
    event: CalendarEventCreate,
    current_user = Depends(get_current_user),
):
    """Create a new calendar event."""
    return await create_calendar_event(
        user_id=current_user.id,
        **event.dict(),
    )


@router.patch("/events/{event_id}", response_model=dict)
async def update_event(
    event_id: UUID,
    update: CalendarEventUpdate,
    current_user = Depends(get_current_user),
):
    """Update an existing event."""
    return await update_calendar_event(
        event_id=event_id,
        user_id=current_user.id,
        **update.dict(exclude_none=True),
    )


@router.delete("/events/{event_id}", response_model=dict)
async def delete_event(
    event_id: UUID,
    current_user = Depends(get_current_user),
):
    """Delete (cancel) an event."""
    return await delete_calendar_event(event_id, current_user.id)
```

---

### 3. Frontend (Web + Mobile)

#### A. Web UI - Weekly Calendar View

**File**: `app/web/components/WeeklyCalendar.tsx`

```typescript
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { format, startOfWeek, endOfWeek, addWeeks, eachDayOfInterval } from 'date-fns';
import api from '@/lib/api';

export default function WeeklyCalendar() {
  const [currentWeek, setCurrentWeek] = useState(new Date());

  const weekStart = startOfWeek(currentWeek, { weekStartsOn: 1 }); // Monday
  const weekEnd = endOfWeek(currentWeek, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: weekStart, end: weekEnd });

  const { data, isLoading } = useQuery({
    queryKey: ['calendar-events', weekStart.toISOString(), weekEnd.toISOString()],
    queryFn: async () => {
      const response = await api.get('/calendar/events', {
        params: {
          start: weekStart.toISOString(),
          end: weekEnd.toISOString(),
        },
      });
      return response.data;
    },
  });

  if (isLoading) return <div>Loading calendar...</div>;

  const events = data?.data?.events || [];

  return (
    <div className="weekly-calendar">
      <div className="calendar-header">
        <button onClick={() => setCurrentWeek(addWeeks(currentWeek, -1))}>← Previous</button>
        <h2>{format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d, yyyy')}</h2>
        <button onClick={() => setCurrentWeek(addWeeks(currentWeek, 1))}>Next →</button>
      </div>

      <div className="calendar-grid">
        {days.map(day => (
          <div key={day.toISOString()} className="calendar-day">
            <div className="day-header">
              {format(day, 'EEE d')}
            </div>

            <div className="day-events">
              {events
                .filter(e => format(new Date(e.starts_at), 'yyyy-MM-dd') === format(day, 'yyyy-MM-dd'))
                .map(event => (
                  <div
                    key={event.id}
                    className={`event ${event.is_recurring_instance ? 'recurring' : ''}`}
                  >
                    <div className="event-time">
                      {format(new Date(event.starts_at), 'HH:mm')}
                    </div>
                    <div className="event-title">{event.title}</div>
                    {event.location_text && (
                      <div className="event-location">📍 {event.location_text}</div>
                    )}
                  </div>
                ))}
            </div>
          </div>
        ))}
      </div>

      <style jsx>{`
        .calendar-grid {
          display: grid;
          grid-template-columns: repeat(7, 1fr);
          gap: 1px;
          background: #e0e0e0;
        }

        .calendar-day {
          background: white;
          min-height: 200px;
          padding: 8px;
        }

        .day-header {
          font-weight: bold;
          margin-bottom: 8px;
        }

        .event {
          background: #e3f2fd;
          border-left: 3px solid #1976d2;
          padding: 4px 8px;
          margin-bottom: 4px;
          border-radius: 4px;
          font-size: 14px;
        }

        .event.recurring {
          background: #f3e5f5;
          border-left-color: #7b1fa2;
        }

        .event-time {
          font-weight: 600;
          color: #1976d2;
        }

        .event-title {
          margin-top: 2px;
        }

        .event-location {
          font-size: 12px;
          color: #666;
          margin-top: 2px;
        }
      `}</style>
    </div>
  );
}
```

#### B. Mobile UI - Weekly Calendar

**File**: `src/screens/CalendarScreen.tsx` (React Native)

```typescript
import React, { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { format, startOfWeek, endOfWeek, addWeeks, eachDayOfInterval } from 'date-fns';
import api from '../lib/api';

export default function CalendarScreen() {
  const [currentWeek, setCurrentWeek] = useState(new Date());

  const weekStart = startOfWeek(currentWeek, { weekStartsOn: 1 });
  const weekEnd = endOfWeek(currentWeek, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: weekStart, end: weekEnd });

  const { data, isLoading } = useQuery({
    queryKey: ['calendar-events', weekStart.toISOString()],
    queryFn: async () => {
      const response = await api.get('/calendar/events', {
        params: {
          start: weekStart.toISOString(),
          end: weekEnd.toISOString(),
        },
      });
      return response.data;
    },
  });

  if (isLoading) return <Text>Loading...</Text>;

  const events = data?.data?.events || [];

  return (
    <View style={{ flex: 1 }}>
      {/* Week navigation */}
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', padding: 16 }}>
        <TouchableOpacity onPress={() => setCurrentWeek(addWeeks(currentWeek, -1))}>
          <Text>← Previous</Text>
        </TouchableOpacity>
        <Text style={{ fontWeight: 'bold' }}>
          {format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d')}
        </Text>
        <TouchableOpacity onPress={() => setCurrentWeek(addWeeks(currentWeek, 1))}>
          <Text>Next →</Text>
        </TouchableOpacity>
      </View>

      {/* Days */}
      <ScrollView>
        {days.map(day => {
          const dayEvents = events.filter(
            e => format(new Date(e.starts_at), 'yyyy-MM-dd') === format(day, 'yyyy-MM-dd')
          );

          return (
            <View key={day.toISOString()} style={{ padding: 16, borderBottomWidth: 1 }}>
              <Text style={{ fontWeight: 'bold', marginBottom: 8 }}>
                {format(day, 'EEEE, MMM d')}
              </Text>

              {dayEvents.length === 0 ? (
                <Text style={{ color: '#999' }}>No events</Text>
              ) : (
                dayEvents.map(event => (
                  <View
                    key={event.id}
                    style={{
                      backgroundColor: event.is_recurring_instance ? '#f3e5f5' : '#e3f2fd',
                      padding: 12,
                      borderRadius: 8,
                      marginBottom: 8,
                    }}
                  >
                    <Text style={{ fontWeight: 'bold' }}>
                      {format(new Date(event.starts_at), 'HH:mm')} - {event.title}
                    </Text>
                    {event.location_text && (
                      <Text style={{ color: '#666' }}>📍 {event.location_text}</Text>
                    )}
                  </View>
                ))
              )}
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}
```

#### C. Event Creation Form

**File**: `app/web/components/CreateEventDialog.tsx`

```typescript
import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

export default function CreateEventDialog({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState('');
  const [startsAt, setStartsAt] = useState('');
  const [location, setLocation] = useState('');
  const [isRecurring, setIsRecurring] = useState(false);
  const [rrule, setRrule] = useState('');

  const queryClient = useQueryClient();

  const createEvent = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.post('/calendar/events', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar-events'] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    createEvent.mutate({
      title,
      starts_at: new Date(startsAt).toISOString(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      location_text: location || undefined,
      rrule: isRecurring ? rrule : undefined,
    });
  };

  return (
    <div className="dialog-overlay">
      <div className="dialog">
        <h2>Create Event</h2>

        <form onSubmit={handleSubmit}>
          <label>
            Title
            <input
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              required
            />
          </label>

          <label>
            Starts At
            <input
              type="datetime-local"
              value={startsAt}
              onChange={e => setStartsAt(e.target.value)}
              required
            />
          </label>

          <label>
            Location (optional)
            <input
              type="text"
              value={location}
              onChange={e => setLocation(e.target.value)}
            />
          </label>

          <label>
            <input
              type="checkbox"
              checked={isRecurring}
              onChange={e => setIsRecurring(e.target.checked)}
            />
            Recurring Event
          </label>

          {isRecurring && (
            <label>
              Recurrence Rule (RRULE)
              <input
                type="text"
                value={rrule}
                onChange={e => setRrule(e.target.value)}
                placeholder="FREQ=WEEKLY;BYDAY=MO"
              />
            </label>
          )}

          <div className="dialog-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" disabled={createEvent.isPending}>
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

---

## Acceptance Criteria

### Backend

- [ ] Calendar event CRUD tools working via chat:
  - "Create event 'Team Meeting' on Monday at 9am"
  - "Update the team meeting to 10am"
  - "Cancel the team meeting"
- [ ] RRULE validation prevents >1000 instances in 2 years
- [ ] Weekly list API returns expanded RRULE instances correctly
- [ ] Linking reminder to event works: "Link my 'call bank' reminder to the banking appointment"
- [ ] Events properly scoped by user_id (no data leakage)

### Frontend (Web)

- [ ] Weekly calendar view displays 7 days (Mon-Sun)
- [ ] One-time events show correctly on their day
- [ ] Recurring events show on all applicable days
- [ ] Visual distinction between recurring and one-time events
- [ ] Previous/Next week navigation works
- [ ] Create event dialog validates inputs
- [ ] Clicking event shows details (title, time, location)

### Frontend (Mobile)

- [ ] Weekly calendar view works on iOS and Android
- [ ] Scrollable daily view for small screens
- [ ] Events grouped by day
- [ ] Create event flow accessible via "+" button
- [ ] Performance: 100+ events in a week render smoothly (<2s)

### Integration

- [ ] Chat creates event → appears in calendar within 5s
- [ ] Web creates event → mobile fetches and displays
- [ ] Event with RRULE "FREQ=DAILY;COUNT=7" generates 7 instances
- [ ] Reminder linked to event: deleting event sets reminder.calendar_event_id to NULL

---

## Testing Strategy

### 1. RRULE Expansion Tests

```bash
#!/bin/bash
# test-rrule-expansion.sh

TOKEN=$(grep API_TOKEN .env | cut -d= -f2)

# Test 1: Create daily recurring event
echo "Test 1: Daily recurring event..."
curl -s -X POST http://localhost:8000/api/v1/calendar/events \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Daily Standup",
    "starts_at": "2025-01-13T09:00:00Z",
    "timezone": "UTC",
    "rrule": "FREQ=DAILY;COUNT=7"
  }' | jq '.data.id'

# Test 2: Fetch week view
echo "Test 2: Fetching week view..."
START="2025-01-13T00:00:00Z"
END="2025-01-20T00:00:00Z"

RESPONSE=$(curl -s "http://localhost:8000/api/v1/calendar/events?start=$START&end=$END" \
  -H "Authorization: Bearer $TOKEN")

COUNT=$(echo $RESPONSE | jq '.data.events | length')
echo "Events in week: $COUNT (should be 7)"

if [ "$COUNT" != "7" ]; then
  echo "✗ Expected 7 instances, got $COUNT"
  exit 1
fi

echo "✓ RRULE expansion working"

# Test 3: Weekly recurring event
echo "Test 3: Weekly recurring event..."
curl -s -X POST http://localhost:8000/api/v1/calendar/events \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Weekly Review",
    "starts_at": "2025-01-13T17:00:00Z",
    "timezone": "UTC",
    "rrule": "FREQ=WEEKLY;BYDAY=MO;COUNT=4"
  }' | jq '.data.id'

# Fetch 4 weeks
START="2025-01-13T00:00:00Z"
END="2025-02-10T00:00:00Z"

RESPONSE=$(curl -s "http://localhost:8000/api/v1/calendar/events?start=$START&end=$END" \
  -H "Authorization: Bearer $TOKEN")

WEEKLY_COUNT=$(echo $RESPONSE | jq '[.data.events[] | select(.title == "Weekly Review")] | length')
echo "Weekly instances: $WEEKLY_COUNT (should be 4)"

if [ "$WEEKLY_COUNT" != "4" ]; then
  echo "✗ Expected 4 weekly instances, got $WEEKLY_COUNT"
  exit 1
fi

echo "✓ Weekly RRULE working"
```

### 2. Manual Testing Scenarios

**Scenario 1: Create Recurring Event via Chat**

1. Open chat
2. Send: "Create a daily standup event at 9am every weekday"
3. Verify:
   - Event created with RRULE: `FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR`
   - Calendar shows event on all weekdays
   - Weekend days don't show the event

**Scenario 2: Link Reminder to Event**

1. Create event: "Dentist appointment on Friday at 2pm"
2. Create reminder: "Remind me 1 hour before dentist"
3. Link: "Link the dentist reminder to the dentist appointment"
4. Verify:
   - `reminders.calendar_event_id` set correctly
   - UI shows reminder associated with event

**Scenario 3: Complex RRULE**

1. Create event: "Monthly team meeting on the first Monday at 10am"
2. Use RRULE: `FREQ=MONTHLY;BYDAY=1MO`
3. View calendar across 3 months
4. Verify: Event appears on first Monday of each month only

---

## Performance Targets

- [ ] Weekly view query: <100ms for 50 events
- [ ] RRULE expansion: <50ms for 100 instances
- [ ] Calendar render (web): <500ms for 7 days with 100 events
- [ ] Mobile calendar scroll: 60 FPS with 100+ events

---

## Migration Guide

### For Existing Users (Stage 5 → Stage 6)

```bash
# Apply migration
docker exec vib-postgres psql -U vib -d vib -f /app/migrations/005_add_calendar.sql

# Restart services
docker-compose restart orchestrator worker

# Verify tables created
docker exec vib-postgres psql -U vib -d vib -c "\d calendar_events"
```

---

## Risk Checklist

- [ ] **RRULE complexity**: Start with simple patterns, defer complex (BYSETPOS, BYMONTHDAY)
- [ ] **Performance**: Index `starts_at`, limit expansion to 1000 instances
- [ ] **Timezone edge cases**: Test DST transitions (March/November)
- [ ] **UI clutter**: Don't show cancelled events by default
- [ ] **Reminder orphaning**: Handle event deletion gracefully (SET NULL)

---

## Success Metrics

After 1 week of usage:

- **Calendar adoption**: >70% of users view calendar at least once
- **Event creation**: Average 3-5 events created per user per week
- **Recurring events**: >50% of events use RRULE
- **Reminder linking**: >30% of reminders linked to events

---

## Next Steps After Stage 6

Once calendar is stable:

1. Use it for 2 weeks
2. Evaluate: Do you want Google Calendar sync?
3. If yes: Proceed to Stage 7
4. If no: Consider Stage 8 (Passkeys for multi-user) or Stage 10 (Advanced agents)

---

## References

- [iCalendar RRULE Spec (RFC 5545)](https://icalendar.org/iCalendar-RFC-5545/3-8-5-3-recurrence-rule.html)
- [python-dateutil RRULE](https://dateutil.readthedocs.io/en/stable/rrule.html)
- [Google Calendar API Events](https://developers.google.com/calendar/api/v3/reference/events)

---

## Remember

**Do NOT implement testing yet.** Focus on making the functionality work. Comprehensive tests will be written after all stages are complete.

Good luck! 🚀
