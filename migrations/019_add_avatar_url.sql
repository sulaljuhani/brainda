-- Migration: Add avatar_url to users table
-- Date: 2025-11-15
-- Description: Add optional avatar_url field for user profile pictures

-- Add avatar_url column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- Add comment for documentation
COMMENT ON COLUMN users.avatar_url IS 'URL to user profile avatar image';
