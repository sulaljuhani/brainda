-- Migration: Add agent_settings table for per-user agent configuration
-- Allows users to enable/disable agents and customize their schedules

CREATE TABLE IF NOT EXISTS agent_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- Agent enable/disable flags
    morning_briefing_enabled BOOLEAN NOT NULL DEFAULT false,
    evening_review_enabled BOOLEAN NOT NULL DEFAULT false,
    weekly_summary_enabled BOOLEAN NOT NULL DEFAULT false,
    smart_suggestions_enabled BOOLEAN NOT NULL DEFAULT false,

    -- Agent schedule times (stored as time without timezone, will be applied in user's timezone)
    morning_briefing_time TIME NOT NULL DEFAULT '07:00:00',  -- 7:00 AM
    evening_review_time TIME NOT NULL DEFAULT '20:00:00',     -- 8:00 PM
    weekly_summary_day_of_week INTEGER NOT NULL DEFAULT 6,    -- Sunday (0=Monday, 6=Sunday)
    weekly_summary_time TIME NOT NULL DEFAULT '18:00:00',     -- 6:00 PM

    -- User's timezone for agent firing
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_agent_settings_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_weekly_summary_day CHECK (weekly_summary_day_of_week >= 0 AND weekly_summary_day_of_week <= 6)
);

-- Index for efficient lookups
CREATE INDEX idx_agent_settings_user_id ON agent_settings(user_id);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_agent_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_agent_settings_updated_at
    BEFORE UPDATE ON agent_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_settings_updated_at();

-- Add comment
COMMENT ON TABLE agent_settings IS 'Per-user configuration for autonomous agent schedules and preferences';
COMMENT ON COLUMN agent_settings.weekly_summary_day_of_week IS '0=Monday, 1=Tuesday, ..., 6=Sunday';
