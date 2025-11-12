from datetime import datetime, timezone
from typing import Optional
import os
import uuid

import asyncpg
import redis.asyncio as redis_async
from fastapi import Depends, HTTPException, Header

from api.services.auth_service import AuthService
from common.db import connect_with_json_codec

DATABASE_URL = os.getenv("DATABASE_URL")
API_TOKEN = os.getenv("API_TOKEN", "default-token-change-me")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

_redis_client: Optional[redis_async.Redis] = None


async def get_db():
    conn = await connect_with_json_codec(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()


async def get_redis() -> redis_async.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_async.from_url(
            REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


# SECURITY: @lru_cache() removed - caching async functions with DB connections
# causes race conditions where users can access each other's data
async def get_user_id_from_token(token: str, db: asyncpg.Connection) -> uuid.UUID:
    """Lookup a user via session token first, falling back to legacy API tokens."""
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    auth_service = AuthService(db)

    session = await auth_service.get_session_by_token(token)
    now = datetime.now(timezone.utc)
    if session:
        expires_at: datetime = session["expires_at"]
        if expires_at <= now:
            await auth_service.delete_session(token)
            await auth_service.log_auth_event(
                "session_expired",
                user_id=session["user_id"],
            )
            raise HTTPException(status_code=401, detail="Session expired")

        await auth_service.touch_session(session["id"])
        return session["user_id"]

    # Legacy API token path (Stage 0-7)
    user = await db.fetchrow(
        "SELECT id FROM users WHERE api_token = $1",
        token,
    )
    if user:
        return user["id"]

    # Auto-provision a user for unexpected API tokens (backward compatibility)
    placeholder_email = f"default+{token[:8]}@vib.local"
    display_name = placeholder_email.split("@")[0]
    async with db.transaction():
        organization = await auth_service.create_organization(f"{display_name} family")
        new_user = await db.fetchrow(
            """
            INSERT INTO users (email, api_token, display_name, organization_id, role, is_active)
            VALUES ($1, $2, $3, $4, 'owner', TRUE)
            ON CONFLICT (api_token) DO UPDATE
            SET email = EXCLUDED.email,
                display_name = COALESCE(users.display_name, EXCLUDED.display_name),
                organization_id = COALESCE(users.organization_id, EXCLUDED.organization_id),
                role = COALESCE(users.role, 'owner'),
                is_active = TRUE,
                updated_at = NOW()
            RETURNING id
            """,
            placeholder_email,
            token,
            display_name,
            organization["id"],
        )
    return new_user["id"]


async def get_current_user(
    authorization: str = Header(None),
    db: asyncpg.Connection = Depends(get_db)
) -> uuid.UUID:
    token = await verify_token(authorization)
    return await get_user_id_from_token(token, db)


async def verify_token(authorization: str = Header(None)) -> str:
    """Extract the bearer token from the Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Allow legacy single-user token to short-circuit without session lookup
    if token == API_TOKEN:
        return token

    return token
