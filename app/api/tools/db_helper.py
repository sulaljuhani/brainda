"""Database helper for tool execution."""
from contextlib import asynccontextmanager
import os
from common.db import connect_with_json_codec


@asynccontextmanager
async def get_db_connection():
    """Get a database connection for tool execution."""
    conn = await connect_with_json_codec(os.getenv("DATABASE_URL"))
    try:
        yield conn
    finally:
        await conn.close()
