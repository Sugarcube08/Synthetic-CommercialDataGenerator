import os
os.environ.setdefault("SYNTH_DATABASE_URI", "postgresql+asyncpg://synth_user:secretpass@localhost:5432/synth_data")

from datetime import date
import pytest
import numpy as np

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from synth_data_creator.generation.customers.engine import generate_profiles
from synth_data_creator.generation.customers.profiles import CustomerProfile

@pytest.fixture(scope="session")
def database_uri() -> str:
    """Use database URI from env if present, otherwise default test DB."""
    return os.getenv(
        "SYNTH_DATABASE_URI", 
        "postgresql+asyncpg://synth_user:secretpass@localhost:5432/synth_data"
    )


@pytest.fixture
async def engine(database_uri: str) -> AsyncEngine:
    """Create a fresh engine for each test."""
    eng = create_async_engine(database_uri)
    yield eng
    await eng.dispose()


@pytest.fixture
def seeded_rng() -> np.random.Generator:
    """Deterministic RNG for reproducible tests."""
    return np.random.default_rng(seed=12345)


@pytest.fixture
def sample_profiles(seeded_rng) -> list[CustomerProfile]:
    """Pre-generated set of customer profiles."""
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    return generate_profiles(num_customers=10, start_date=start, end_date=end, seed=12345)
