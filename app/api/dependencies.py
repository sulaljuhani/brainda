from datetime import datetime, timezone
from typing import Optional
import os
import uuid

import asyncpg
import redis.asyncio as redis_async
from fastapi import Depends, HTTPException, Header, Request

from api.services.auth_service import AuthService
from common.db import connect_with_json_codec

DATABASE_URL = os.getenv("DATABASE_URL")
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
        # Ensure expires_at is timezone-aware for proper comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
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

    raise HTTPException(status_code=401, detail="Invalid or expired token")


async def verify_token(
    request: Request,
    authorization: str = Header(None),
    db: asyncpg.Connection = Depends(get_db),
) -> str:
    """Validate a bearer token and attach authentication context to the request."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = await get_user_id_from_token(token, db)
    request.state.authenticated_user_id = user_id
    request.state.authenticated_token = token
    return token


async def get_current_user(
    request: Request,
    token: str = Depends(verify_token),
) -> uuid.UUID:
    user_id = getattr(request.state, "authenticated_user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id
