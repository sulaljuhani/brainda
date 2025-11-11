-- Stage 2: Reminders, notifications, locations

DROP TABLE IF EXISTS notification_delivery;
DROP TABLE IF EXISTS reminders;
DROP TABLE IF EXISTS locations;
DROP TABLE IF EXISTS devices;

-- Reminders table
CREATE TABLE reminders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    note_id UUID REFERENCES notes(id), -- optional link
    title TEXT NOT NULL,
    body TEXT,
    due_at_utc TIMESTAMPTZ NOT NULL,
    due_at_local TIME NOT NULL,
    timezone TEXT NOT NULL,
    repeat_rrule TEXT, -- NULL or RRULE string
    status TEXT DEFAULT 'active', -- active, snoozed, done, cancelled
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Locations (for future geofencing - minimal for now)
CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    lat NUMERIC(10, 7),
    lon NUMERIC(10, 7),
    radius_m INTEGER DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notification delivery tracking
CREATE TABLE notification_delivery (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reminder_id UUID REFERENCES reminders(id),
    device_id UUID, -- Can't reference devices yet as it's not created
    sent_at TIMESTAMPTZ NOT NULL,
    delivered_at TIMESTAMPTZ,
    interacted_at TIMESTAMPTZ,
    action TEXT, -- snooze, done, open
    status TEXT DEFAULT 'sent', -- sent, delivered, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- CRITICAL: Deduplication constraint for reminders
CREATE UNIQUE INDEX idx_reminders_dedup ON reminders (
    user_id, 
    title, 
    due_at_utc
) WHERE status = 'active';

-- Performance indexes
CREATE INDEX idx_reminders_user_status ON reminders(user_id, status);
CREATE INDEX idx_reminders_due_at ON reminders(due_at_utc) WHERE status = 'active';
CREATE INDEX idx_notification_delivery_reminder ON notification_delivery(reminder_id);
CREATE INDEX idx_notification_delivery_device ON notification_delivery(device_id);

-- Devices table for push notifications
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL, -- web, ios, android
    push_token TEXT,
    push_endpoint TEXT,
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, platform, push_token)
);

-- Now add the foreign key constraint
ALTER TABLE notification_delivery 
ADD CONSTRAINT fk_device 
FOREIGN KEY (device_id) 
REFERENCES devices(id) ON DELETE SET NULL;
