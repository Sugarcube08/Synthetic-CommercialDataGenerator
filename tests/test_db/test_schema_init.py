import pytest
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.db.schema_init import initialize_schema, verify_schema, drop_all_tables

pytestmark = pytest.mark.asyncio

async def check_db_connection(engine: AsyncEngine) -> bool:
    """Helper to check if DB is running and accessible."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def test_schema_lifecycle(engine: AsyncEngine) -> None:
    """Test full drop, initialize, verify schema cycle on a test DB."""
    if not await check_db_connection(engine):
        pytest.skip("PostgreSQL test database not available")

    # 1. Clean drop
    await drop_all_tables(engine)
    
    # Verify tables are gone
    async with engine.connect() as conn:
        tables = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
        assert not set(["customers", "raw_sales"]).intersection(set(tables))

    # 2. Idempotent initialization
    await initialize_schema(engine, drop_existing=True)
    
    # Run second time to test idempotency
    await initialize_schema(engine, drop_existing=False)

    # 3. Verify schema
    assert await verify_schema(engine) is True
    
    # Clean up
    await drop_all_tables(engine)
