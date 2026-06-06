from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

def create_db_engine(
    database_uri: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_timeout: int = 30,
) -> AsyncEngine:
    """Create a configured async database engine."""
    return create_async_engine(
        database_uri,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,      # Verify connections before use
        pool_recycle=3600,        # Recycle connections after 1 hour
        echo=False,               # Disable SQL logging in production
    )


def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a sessionmaker for producing async database sessions."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
