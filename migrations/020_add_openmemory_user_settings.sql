-- Migration: Add OpenMemory user settings table
-- Date: 2025-11-15
-- Description: Create table to store per-user OpenMemory configuration

-- Create openmemory_user_settings table
CREATE TABLE IF NOT EXISTS openmemory_user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    enabled BOOLEAN DEFAULT false NOT NULL,
    server_url TEXT,
    api_key_encrypted TEXT,
    auto_store_conversations BOOLEAN DEFAULT true NOT NULL,
    retention_days INTEGER DEFAULT 90,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Add index for faster user lookups
CREATE INDEX IF NOT EXISTS idx_openmemory_user_settings_user_id ON openmemory_user_settings(user_id);

-- Add index for enabled flag (for filtering active users)
CREATE INDEX IF NOT EXISTS idx_openmemory_user_settings_enabled ON openmemory_user_settings(enabled) WHERE enabled = true;

-- Add trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_openmemory_user_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_openmemory_user_settings_updated_at
    BEFORE UPDATE ON openmemory_user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_openmemory_user_settings_updated_at();

-- Add comments for documentation
COMMENT ON TABLE openmemory_user_settings IS 'Per-user OpenMemory configuration and preferences';
COMMENT ON COLUMN openmemory_user_settings.enabled IS 'Whether OpenMemory integration is enabled for this user';
COMMENT ON COLUMN openmemory_user_settings.server_url IS 'Custom OpenMemory server URL (overrides global default)';
COMMENT ON COLUMN openmemory_user_settings.api_key_encrypted IS 'Encrypted API key for OpenMemory authentication (Fernet encrypted)';
COMMENT ON COLUMN openmemory_user_settings.auto_store_conversations IS 'Automatically store chat conversations in OpenMemory';
COMMENT ON COLUMN openmemory_user_settings.retention_days IS 'Number of days to retain memories (1-3650 days)';
