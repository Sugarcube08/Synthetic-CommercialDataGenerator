import structlog
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.core.exceptions import SchemaInitError, SchemaVerificationError
from synth_data_creator.db.models import Base

logger = structlog.get_logger()

REQUIRED_TABLES = ["customers", "raw_sales", "raw_payments", "raw_returns"]

EXPECTED_COLUMNS = {
    "customers": ["id", "customer_code", "business_name", "behavioral_profile"],
    "raw_sales": ["id", "customer_id", "invoice_number", "invoice_amount"],
    "raw_payments": ["id", "customer_id", "invoice_id", "payment_amount"],
    "raw_returns": ["id", "customer_id", "sale_id", "return_value"],
}

async def initialize_schema(engine: AsyncEngine, drop_existing: bool = False) -> None:
    """Create all required tables if they do not exist.

    This function is idempotent — safe to call on every startup.
    """
    try:
        async with engine.begin() as conn:
            # Check for uuid-ossp or pgcrypto extension for UUID gen
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
            
            if drop_existing:
                logger.info("schema_drop_requested")
                # Drop tables in reverse order to respect foreign keys
                await conn.run_sync(Base.metadata.drop_all)
                logger.info("schema_dropped")

            # Create tables
            # SQLAlchemy Base.metadata.create_all is idempotent and safe
            await conn.run_sync(Base.metadata.create_all)
            logger.info("schema_init_complete")

    except Exception as e:
        logger.error("schema_init_failed", error=str(e))
        raise SchemaInitError(f"Database schema initialization failed: {e}") from e


async def verify_schema(engine: AsyncEngine) -> bool:
    """Verify that the schema matches the expected structure."""
    try:
        async with engine.connect() as conn:
            for table in REQUIRED_TABLES:
                columns = await conn.run_sync(
                    lambda sync_conn: [
                        c["name"] for c in inspect(sync_conn).get_columns(table)
                    ]
                )
                expected = EXPECTED_COLUMNS[table]
                missing = set(expected) - set(columns)
                if missing:
                    raise SchemaVerificationError(
                        f"Table '{table}' missing columns: {missing}"
                    )
            logger.info("schema_verification_passed")
            return True
    except SchemaVerificationError:
        raise
    except Exception as e:
        logger.error("schema_verification_failed", error=str(e))
        raise SchemaVerificationError(f"Database schema verification failed: {e}") from e


async def drop_all_tables(engine: AsyncEngine) -> None:
    """Drop all tables. Used primarily for tests."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("all_tables_dropped")
