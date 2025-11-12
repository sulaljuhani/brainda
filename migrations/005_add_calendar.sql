-- Stage 6: Calendar events

CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,

    -- Timing (both stored for DST handling like reminders)
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,
    timezone TEXT NOT NULL,

    -- Location (optional, can link to locations table)
    location_id UUID REFERENCES locations(id),
    location_text TEXT,

    -- Recurrence
    rrule TEXT,

    -- Sync metadata (for Stage 7 Google Calendar sync)
    source TEXT DEFAULT 'internal',
    google_event_id TEXT UNIQUE,
    google_calendar_id TEXT,

    -- Status
    status TEXT DEFAULT 'confirmed',

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS calendar_event_id UUID REFERENCES calendar_events(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS calendar_sync_state (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    google_calendar_id TEXT,
    sync_token TEXT,
    last_sync_at TIMESTAMPTZ,
    sync_enabled BOOLEAN DEFAULT FALSE,
    sync_direction TEXT DEFAULT 'one_way',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_user_starts ON calendar_events(user_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_calendar_events_source ON calendar_events(source);
CREATE INDEX IF NOT EXISTS idx_calendar_events_google_id ON calendar_events(google_event_id) WHERE google_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_calendar_events_status ON calendar_events(user_id, status) WHERE status != 'cancelled';

CREATE INDEX IF NOT EXISTS idx_reminders_event ON reminders(calendar_event_id) WHERE calendar_event_id IS NOT NULL;
