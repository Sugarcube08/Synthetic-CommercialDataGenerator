from datetime import date
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.db.schema_init import initialize_schema, drop_all_tables
from synth_data_creator.db.bulk_ops import bulk_insert

pytestmark = pytest.mark.asyncio

async def check_db_connection(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def test_bulk_insert_ops(engine: AsyncEngine) -> None:
    """Verify customer profile bulk inserts and query count matches."""
    if not await check_db_connection(engine):
        pytest.skip("PostgreSQL test database not available")

    # Setup schema
    await initialize_schema(engine, drop_existing=True)

    records = [
        {
            "customer_code": f"CUST-B{i:04d}",
            "business_name": f"Bulk Business {i}",
            "registration_date": date(2024, 1, 1),
            "behavioral_profile": {"volume_segment": "small"},
            "credit_limit": 10000.0,
            "payment_terms_days": 30,
        }
        for i in range(10)
    ]

    # Run insert
    await bulk_insert(engine, "customers", records)

    # Verify counts
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT COUNT(*) FROM customers"))
        count = res.scalar()
        assert count == 10

    # Clean up
    await drop_all_tables(engine)
