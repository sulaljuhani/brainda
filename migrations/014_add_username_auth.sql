-- Migration: Add username field and simplify authentication to username + password only

-- Add username column to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS username TEXT;

-- Make email optional (was previously required)
ALTER TABLE users
ALTER COLUMN email DROP NOT NULL;

-- Add unique constraint on username
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username);

-- Migrate existing users to have usernames (use email prefix or display_name)
UPDATE users
SET username = COALESCE(
    NULLIF(TRIM(display_name), ''),
    SPLIT_PART(email, '@', 1),
    'user_' || SUBSTR(id::text, 1, 8)
)
WHERE username IS NULL;

-- Now make username NOT NULL after backfilling
ALTER TABLE users
ALTER COLUMN username SET NOT NULL;

-- Add index for faster username lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Comment for documentation
COMMENT ON COLUMN users.username IS 'Unique username for login (required)';
COMMENT ON COLUMN users.email IS 'Email address for notifications (optional)';
