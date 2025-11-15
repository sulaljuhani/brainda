-- Stage 1: Tasks and Categories Schema
-- Migration: Add tasks table and category tables for tasks, events, and reminders

-- Task Categories Table
CREATE TABLE IF NOT EXISTS task_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT, -- Hex color code (e.g., #FF5733)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Event Categories Table
CREATE TABLE IF NOT EXISTS event_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT, -- Hex color code (e.g., #FF5733)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Reminder Categories Table
CREATE TABLE IF NOT EXISTS reminder_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT, -- Hex color code (e.g., #FF5733)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, name)
);

-- Tasks Table
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_task_id UUID REFERENCES tasks(id) ON DELETE CASCADE, -- For sub-tasks
    title TEXT NOT NULL,
    description TEXT,
    category_id UUID REFERENCES task_categories(id) ON DELETE SET NULL,

    -- Timing (optional - tasks can have schedules like events)
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    all_day BOOLEAN DEFAULT FALSE,
    timezone TEXT NOT NULL DEFAULT 'UTC',

    -- Recurrence (for recurring tasks)
    rrule TEXT,

    -- Status tracking
    status TEXT DEFAULT 'active', -- active, completed, cancelled
    completed_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alter calendar_events to add category
ALTER TABLE calendar_events
ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES event_categories(id) ON DELETE SET NULL;

-- Alter reminders to add category, task linking, and offset fields
ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES reminder_categories(id) ON DELETE SET NULL;

ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS task_id UUID REFERENCES tasks(id) ON DELETE CASCADE;

ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS offset_days INTEGER; -- Days before/after linked task/event

ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS offset_type TEXT; -- 'before' or 'after'

-- Indexes for task_categories
CREATE INDEX IF NOT EXISTS idx_task_categories_user ON task_categories(user_id);

-- Indexes for event_categories
CREATE INDEX IF NOT EXISTS idx_event_categories_user ON event_categories(user_id);

-- Indexes for reminder_categories
CREATE INDEX IF NOT EXISTS idx_reminder_categories_user ON reminder_categories(user_id);

-- Indexes for tasks
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id) WHERE parent_task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category_id) WHERE category_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_starts_at ON tasks(starts_at) WHERE starts_at IS NOT NULL;

-- Indexes for new reminder fields
CREATE INDEX IF NOT EXISTS idx_reminders_task ON reminders(task_id) WHERE task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reminders_category ON reminders(category_id) WHERE category_id IS NOT NULL;

-- Index for calendar_events category
CREATE INDEX IF NOT EXISTS idx_calendar_events_category ON calendar_events(category_id) WHERE category_id IS NOT NULL;
