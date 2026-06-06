# 02 — Database Migration & Initialization Strategy

## 2.1 Auto-Initialization Approach

The microservice uses a **code-first auto-init** strategy rather than a migration framework for v0.1. On startup, the system:

1. Connects to the provided PostgreSQL URI
2. Checks for table existence
3. Creates missing tables with full DDL
4. Verifies schema integrity
5. Reports initialization status

### Why Not Alembic (v0.1)?

- The schema is brand new with no existing data to migrate
- Tables are created idempotently with `IF NOT EXISTS`
- Schema versioning complexity is premature for v0.1
- Alembic is included as a dependency for future migration support

## 2.2 Initialization Flow

```
Application Start
       │
       ▼
┌──────────────────┐
│ Parse DATABASE_URI│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Create Engine    │  ← asyncpg connection pool
│ & Test Connection│
└────────┬─────────┘
         │ Fail? → Retry (3x exponential backoff) → Abort
         │
         ▼
┌──────────────────┐
│ Check Table      │  ← SELECT FROM information_schema.tables
│ Existence        │
└────────┬─────────┘
         │
    ┌────┴────┐
    │All exist│
    │         │
    No       Yes
    │         │
    ▼         ▼
┌────────┐  ┌────────────┐
│ Create │  │ Verify     │
│ Missing│  │ Column     │
│ Tables │  │ Schema     │
└───┬────┘  └─────┬──────┘
    │             │
    └──────┬──────┘
           │
           ▼
    ┌──────────────┐
    │ Log Status   │
    │ Ready        │
    └──────────────┘
```

## 2.3 Implementation: `schema_init.py`

```python
"""Idempotent schema initialization for the synthetic data tables."""

import structlog
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger()

REQUIRED_TABLES = ["customers", "raw_sales", "raw_payments", "raw_returns"]

async def initialize_schema(engine: AsyncEngine) -> None:
    """Create all required tables if they do not exist.

    This function is idempotent — safe to call on every startup.
    """
    async with engine.begin() as conn:
        # Check existing tables
        existing = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

        missing = [t for t in REQUIRED_TABLES if t not in existing]

        if not missing:
            logger.info("schema_check_passed", existing_tables=REQUIRED_TABLES)
            return

        logger.info("schema_init_starting", missing_tables=missing)

        # Execute DDL for each missing table
        for table_name in missing:
            ddl = _get_table_ddl(table_name)
            await conn.execute(text(ddl))
            logger.info("table_created", table=table_name)

        logger.info("schema_init_complete")


def _get_table_ddl(table_name: str) -> str:
    """Return the CREATE TABLE DDL for the given table name."""
    # DDL strings defined in db/models.py or loaded from SQL files
    return DDL_REGISTRY[table_name]
```

## 2.4 Idempotency Guarantees

| Operation | Guarantee |
|-----------|-----------|
| `CREATE TABLE IF NOT EXISTS` | Safe to re-run |
| `CREATE INDEX IF NOT EXISTS` | Safe to re-run |
| Table already populated | No data modification |
| Partial init (crash mid-way) | Next startup completes remaining tables |

## 2.5 Schema Verification

After initialization, the system verifies:

1. All 4 tables exist
2. Expected columns are present (spot-check critical columns)
3. Foreign key constraints are in place
4. Required indexes exist

```python
async def verify_schema(engine: AsyncEngine) -> bool:
    """Verify that the schema matches expected structure."""
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
    return True
```

## 2.6 Future Migration Path

When schema evolution is needed (v0.2+):

1. Add Alembic with `alembic init`
2. Generate initial migration from current DDL: `alembic revision --autogenerate`
3. Stamp the current database: `alembic stamp head`
4. Replace auto-init with `alembic upgrade head` in startup

The auto-init code SHOULD be preserved as a fallback for fresh database targets.

## 2.7 Database Preparation SQL

For production environments, the database and role should be pre-created:

```sql
-- Run as PostgreSQL superuser
CREATE ROLE synth_user WITH LOGIN PASSWORD 'secure_password';
CREATE DATABASE synth_data OWNER synth_user;
GRANT ALL PRIVILEGES ON DATABASE synth_data TO synth_user;

-- Enable UUID extension (required for gen_random_uuid())
\c synth_data
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

The microservice handles everything after the database exists.
