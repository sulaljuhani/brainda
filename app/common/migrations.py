"""
Database migration runner.

Automatically applies SQL migrations from the migrations/ directory.
Ensures migrations are applied in order and only once.
"""

import asyncpg
import structlog
import asyncio
from pathlib import Path

logger = structlog.get_logger()


async def run_migrations(db_url: str, migrations_dir: str = "/app/migrations"):
    """
    Run all pending migrations in order.

    Creates a migrations_applied table to track which migrations have been run.
    Applies migrations in alphabetical order (001_, 002_, etc.)
    """
    conn = None
    try:
        # Retry database connection with exponential backoff
        max_retries = 5
        retry_delay = 1  # Start with 1 second

        for attempt in range(max_retries):
            try:
                logger.info("attempting_database_connection", attempt=attempt + 1, max_retries=max_retries)
                conn = await asyncpg.connect(db_url)
                logger.info("database_connection_successful")
                break
            except (asyncpg.exceptions.PostgresConnectionError, OSError, ConnectionRefusedError) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        "database_connection_failed_retrying",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        retry_delay=retry_delay,
                        error=str(e)
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("database_connection_failed_all_retries_exhausted", error=str(e))
                    raise

        # Create migrations tracking table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS migrations_applied (
                id SERIAL PRIMARY KEY,
                migration_name TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        logger.info("migrations_table_ready")

        # Get list of already applied migrations
        applied_migrations = set()
        rows = await conn.fetch("SELECT migration_name FROM migrations_applied")
        for row in rows:
            applied_migrations.add(row['migration_name'])

        logger.info("migrations_already_applied", count=len(applied_migrations))

        # Find all .sql files in migrations directory
        migrations_path = Path(migrations_dir)
        if not migrations_path.exists():
            logger.warning("migrations_directory_not_found", path=migrations_dir)
            return

        migration_files = sorted(migrations_path.glob("*.sql"))

        if not migration_files:
            logger.info("no_migration_files_found")
            return

        # Apply migrations in order
        applied_count = 0
        for migration_file in migration_files:
            migration_name = migration_file.name

            # Skip if already applied
            if migration_name in applied_migrations:
                logger.debug("migration_already_applied", name=migration_name)
                continue

            logger.info("applying_migration", name=migration_name)

            try:
                # Read and execute migration SQL
                sql = migration_file.read_text()

                # Execute in a transaction
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO migrations_applied (migration_name) VALUES ($1)",
                        migration_name
                    )

                applied_count += 1
                logger.info("migration_applied_successfully", name=migration_name)

            except Exception as e:
                logger.error(
                    "migration_failed",
                    name=migration_name,
                    error=str(e)
                )
                raise RuntimeError(f"Migration {migration_name} failed: {e}")

        if applied_count > 0:
            logger.info("migrations_completed", count=applied_count)
        else:
            logger.info("no_new_migrations_to_apply")

    except Exception as e:
        logger.error("migration_runner_failed", error=str(e))
        raise
    finally:
        if conn:
            await conn.close()
