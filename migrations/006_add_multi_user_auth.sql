-- Stage 8: Multi-user authentication with passkeys

-- Organizations table (for family/team hosting)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Update users table for multi-user
ALTER TABLE users
ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS display_name TEXT,
ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'member',  -- owner, admin, member
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Allow NULL API tokens for passkey-first users
ALTER TABLE users
ALTER COLUMN api_token DROP NOT NULL;

-- Ensure existing users are linked to organizations
DO $$
DECLARE
    user_record RECORD;
    org_id UUID;
    org_name TEXT;
BEGIN
    FOR user_record IN SELECT id, email, display_name, organization_id FROM users LOOP
        IF user_record.organization_id IS NULL THEN
            org_name := COALESCE(user_record.display_name, user_record.email, 'Family Vault');
            INSERT INTO organizations (name)
            VALUES (org_name)
            RETURNING id INTO org_id;

            UPDATE users
            SET organization_id = org_id,
                role = COALESCE(role, 'owner'),
                display_name = COALESCE(display_name, split_part(email, '@', 1)),
                is_active = COALESCE(is_active, TRUE),
                updated_at = NOW()
            WHERE id = user_record.id;
        END IF;
    END LOOP;
END $$;

-- Passkey credentials (WebAuthn)
CREATE TABLE IF NOT EXISTS passkey_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_id TEXT NOT NULL UNIQUE,  -- WebAuthn credential ID (base64url)
    public_key TEXT NOT NULL,  -- Public key (base64 encoded)
    counter INTEGER NOT NULL DEFAULT 0,  -- Sign counter (prevents replay attacks)
    transports TEXT[],  -- usb, nfc, ble, internal
    device_name TEXT,  -- User-friendly name: "MacBook Pro Touch ID"
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TOTP secrets (for 2FA backup)
CREATE TABLE IF NOT EXISTS totp_secrets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    secret TEXT NOT NULL,  -- Base32 encoded secret
    enabled BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMPTZ,
    backup_codes TEXT[],  -- Array of hashed one-time backup codes
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions (replace API token with proper sessions)
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,  -- Secure random token
    device_name TEXT,
    device_type TEXT,  -- web, ios, android
    ip_address INET,
    user_agent TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log for auth events
CREATE TABLE IF NOT EXISTS auth_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    event_type TEXT NOT NULL,  -- login_success, login_failed, passkey_added, etc.
    ip_address INET,
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_passkey_creds_user ON passkey_credentials(user_id);
CREATE INDEX IF NOT EXISTS idx_totp_user ON totp_secrets(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_audit_user ON auth_audit_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
