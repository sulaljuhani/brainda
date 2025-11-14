-- Migration: Fix seed user function to include username field

CREATE OR REPLACE FUNCTION ensure_seed_user(api_token_value TEXT)
RETURNS UUID AS $$
DECLARE
    org_id UUID;
    user_id UUID;
    existing_user_id UUID;
BEGIN
    -- If no API token is provided, return NULL
    IF api_token_value IS NULL OR api_token_value = '' THEN
        RAISE NOTICE 'No API_TOKEN provided, skipping seed user creation';
        RETURN NULL;
    END IF;

    -- Check if a user with this API token already exists
    SELECT id INTO existing_user_id
    FROM users
    WHERE api_token = api_token_value
    LIMIT 1;

    IF existing_user_id IS NOT NULL THEN
        RAISE NOTICE 'Seed user with API token already exists (user_id: %)', existing_user_id;
        RETURN existing_user_id;
    END IF;

    -- Check if there's already an organization we can use
    SELECT id INTO org_id
    FROM organizations
    LIMIT 1;

    -- If no organization exists, create one
    IF org_id IS NULL THEN
        INSERT INTO organizations (name)
        VALUES ('Default Organization')
        RETURNING id INTO org_id;
    END IF;

    -- Create seed user with API token (now includes username)
    INSERT INTO users (username, email, api_token, organization_id, display_name, role, is_active)
    VALUES (
        'seed',
        'seed@localhost',
        api_token_value,
        org_id,
        'Seed User',
        'owner',
        true
    )
    RETURNING id INTO user_id;

    RAISE NOTICE 'Created seed user with API token (user_id: %)', user_id;
    RETURN user_id;
END;
$$ LANGUAGE plpgsql;
