-- Stage 1: Tasks and Categories
-- This migration adds support for tasks (separate from reminders) and categories for tasks/events/reminders

-- ============================================================================
-- TASK CATEGORIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS task_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT, -- hex color code (e.g., #3b82f6)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_task_category_per_user UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_task_categories_user ON task_categories(user_id);

-- ============================================================================
-- EVENT CATEGORIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS event_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT, -- hex color code
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_event_category_per_user UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_event_categories_user ON event_categories(user_id);

-- ============================================================================
-- REMINDER CATEGORIES TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS reminder_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT, -- hex color code
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_reminder_category_per_user UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_reminder_categories_user ON reminder_categories(user_id);

-- ============================================================================
-- TASKS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_task_id UUID REFERENCES tasks(id) ON DELETE CASCADE, -- for sub-tasks
    title TEXT NOT NULL,
    description TEXT,
    category_id UUID REFERENCES task_categories(id) ON DELETE SET NULL,

    -- Timing (optional - tasks can be without dates)
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    all_day BOOLEAN DEFAULT false,
    timezone TEXT DEFAULT 'UTC',

    -- Recurrence
    rrule TEXT, -- RRULE string for recurring tasks

    -- Status tracking
    status TEXT DEFAULT 'active', -- active, completed, cancelled
    completed_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CHECK (status IN ('active', 'completed', 'cancelled')),
    CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at)
);

-- Performance indexes for tasks
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id) WHERE parent_task_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category_id) WHERE category_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_starts_at ON tasks(starts_at) WHERE starts_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON tasks(user_id, created_at DESC);

-- ============================================================================
-- ALTER EXISTING TABLES - Add Category Support
-- ============================================================================

-- Add category to calendar_events
ALTER TABLE calendar_events
ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES event_categories(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_calendar_events_category ON calendar_events(category_id) WHERE category_id IS NOT NULL;

-- Add category to reminders
ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS category_id UUID REFERENCES reminder_categories(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_reminders_category ON reminders(category_id) WHERE category_id IS NOT NULL;

-- ============================================================================
-- ALTER REMINDERS TABLE - Add Task Linking Support
-- ============================================================================

-- Add task linking to reminders (in addition to existing calendar_event_id)
ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS task_id UUID REFERENCES tasks(id) ON DELETE CASCADE;

-- Add offset support for linking (X days before/after task or event)
ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS offset_days INTEGER;

ALTER TABLE reminders
ADD COLUMN IF NOT EXISTS offset_type TEXT;

-- Add constraint to ensure offset_type is valid
ALTER TABLE reminders
ADD CONSTRAINT IF NOT EXISTS check_offset_type
CHECK (offset_type IS NULL OR offset_type IN ('before', 'after'));

-- Add constraint to ensure offset fields are consistent
ALTER TABLE reminders
ADD CONSTRAINT IF NOT EXISTS check_offset_consistency
CHECK (
    (offset_days IS NULL AND offset_type IS NULL) OR
    (offset_days IS NOT NULL AND offset_type IS NOT NULL)
);

-- Add constraint to ensure reminder is linked to at most one entity
ALTER TABLE reminders
ADD CONSTRAINT IF NOT EXISTS check_single_link
CHECK (
    (task_id IS NULL AND calendar_event_id IS NULL) OR
    (task_id IS NOT NULL AND calendar_event_id IS NULL) OR
    (task_id IS NULL AND calendar_event_id IS NOT NULL)
);

-- Index for task linkage
CREATE INDEX IF NOT EXISTS idx_reminders_task ON reminders(task_id) WHERE task_id IS NOT NULL;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE tasks IS 'User tasks with optional hierarchy (parent/sub-tasks), dates, and recurrence';
COMMENT ON TABLE task_categories IS 'Categories for organizing tasks';
COMMENT ON TABLE event_categories IS 'Categories for organizing calendar events';
COMMENT ON TABLE reminder_categories IS 'Categories for organizing reminders';

COMMENT ON COLUMN tasks.parent_task_id IS 'Reference to parent task for sub-task hierarchy';
COMMENT ON COLUMN tasks.all_day IS 'Whether this is an all-day task';
COMMENT ON COLUMN tasks.rrule IS 'RRULE string for recurring tasks';
COMMENT ON COLUMN tasks.completed_at IS 'Timestamp when task was marked completed';

COMMENT ON COLUMN reminders.task_id IS 'Optional link to a task';
COMMENT ON COLUMN reminders.offset_days IS 'Number of days before/after linked task/event to fire reminder';
COMMENT ON COLUMN reminders.offset_type IS 'Whether offset is before or after the linked entity';
