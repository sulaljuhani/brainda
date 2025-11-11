from fastapi import Depends, HTTPException, Header
import asyncpg
import os
import uuid
from functools import lru_cache

from common.db import connect_with_json_codec

DATABASE_URL = os.getenv("DATABASE_URL")
API_TOKEN = os.getenv("API_TOKEN", "default-token-change-me")

async def get_db():
    conn = await connect_with_json_codec(DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()

@lru_cache()
async def get_user_id_from_token(token: str, db: asyncpg.Connection) -> uuid.UUID:
    """Lookup or create a user record based on the API token."""
    user = await db.fetchrow("SELECT id FROM users WHERE api_token = $1", token)
    if user:
        return user["id"]
    
    placeholder_email = f"default+{token[:8]}@vib.local"
    new_user = await db.fetchrow(
        """
        INSERT INTO users (email, api_token)
        VALUES ($1, $2)
        ON CONFLICT (api_token) DO UPDATE
        SET email = EXCLUDED.email
        RETURNING id
        """,
        placeholder_email,
        token,
    )
    return new_user["id"]

async def get_current_user(
    authorization: str = Header(None), 
    db: asyncpg.Connection = Depends(get_db)
) -> uuid.UUID:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = authorization.split(" ")[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    return await get_user_id_from_token(token, db)

async def verify_token(authorization: str = Header(None)) -> str:
    """FastAPI dependency that validates API token and returns it."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = authorization.split(" ")[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token
