import os
import json
import asyncpg
from typing import Optional


async def setup_json_codecs(conn: asyncpg.Connection) -> None:
    """Ensure JSON/JSONB fields round-trip as Python dicts."""
    await conn.set_type_codec(
        "json",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )
    await conn.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        encoder=json.dumps,
        decoder=json.loads,
        format="text",
    )


async def connect_with_json_codec(
    database_url: Optional[str] = None,
) -> asyncpg.Connection:
    """Create an asyncpg connection with JSON codecs configured."""
    conn = await asyncpg.connect(database_url or os.getenv("DATABASE_URL"))
    await setup_json_codecs(conn)
    return conn
