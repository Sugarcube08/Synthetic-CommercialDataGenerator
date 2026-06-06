import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.db.models import Base

logger = structlog.get_logger()

async def bulk_insert(
    engine: AsyncEngine,
    table_name: str,
    records: list[dict],
) -> None:
    """Optimized bulk insert using SQLAlchemy core insert with a list of dicts.

    This maps directly to PostgreSQL multi-row insert or executemany.
    """
    if not records:
        return

    try:
        async with engine.begin() as conn:
            table = Base.metadata.tables[table_name]
            await conn.execute(table.insert(), records)
        logger.debug("bulk_insert_success", table=table_name, count=len(records))
    except Exception as e:
        logger.error("bulk_insert_failed", table=table_name, error=str(e))
        raise
