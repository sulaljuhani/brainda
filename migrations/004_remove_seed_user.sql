-- Remove legacy seed user that conflicts with API-token scoped tests
DELETE FROM users WHERE api_token = 'default-token-change-me';
