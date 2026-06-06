from functools import lru_cache
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.core.config import Settings
from synth_data_creator.db.engine import create_db_engine

# Global cached engine
_db_engine: AsyncEngine | None = None

@lru_cache()
def get_settings() -> Settings:
    """Load and cache settings from environment."""
    return Settings()


def get_db_engine() -> AsyncEngine:
    """Get or create the global database engine based on cached settings."""
    global _db_engine
    if _db_engine is None:
        settings = get_settings()
        _db_engine = create_db_engine(
            database_uri=settings.database_uri,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
        )
    return _db_engine
