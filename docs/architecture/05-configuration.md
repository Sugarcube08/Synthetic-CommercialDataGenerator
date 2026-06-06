# 05 — Configuration & Environment

## 5.1 Configuration Schema

All configuration is managed through `pydantic-settings`, loading from environment variables with optional `.env` file support.

```python
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn

class Settings(BaseSettings):
    """Application configuration loaded from environment."""

    # ── Database ──────────────────────────────────────────
    database_uri: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URI",
        examples=["postgresql+asyncpg://user:pass@localhost:5432/synth_data"],
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    db_pool_timeout: int = Field(default=30, ge=5, le=300)

    # ── Generation Defaults ───────────────────────────────
    default_num_customers: int = Field(default=500, ge=10, le=100_000)
    default_date_range_months: int = Field(default=24, ge=1, le=120)
    default_seed: int | None = Field(default=None, description="RNG seed for reproducibility")

    # ── Batch Processing ──────────────────────────────────
    batch_size: int = Field(default=5000, ge=100, le=50_000)
    max_concurrent_writers: int = Field(default=4, ge=1, le=16)

    # ── API ───────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1024, le=65535)
    api_workers: int = Field(default=1, ge=1, le=8)

    # ── Logging ───────────────────────────────────────────
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = Field(default="json", pattern="^(json|console)$")

    model_config = {
        "env_prefix": "SYNTH_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
```

## 5.2 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SYNTH_DATABASE_URI` | **Yes** | — | PostgreSQL connection string |
| `SYNTH_DB_POOL_SIZE` | No | `10` | Connection pool size |
| `SYNTH_DB_MAX_OVERFLOW` | No | `20` | Max overflow connections |
| `SYNTH_DB_POOL_TIMEOUT` | No | `30` | Pool checkout timeout (seconds) |
| `SYNTH_DEFAULT_NUM_CUSTOMERS` | No | `500` | Default customer count |
| `SYNTH_DEFAULT_DATE_RANGE_MONTHS` | No | `24` | Default generation window |
| `SYNTH_DEFAULT_SEED` | No | `None` | RNG seed (null = random) |
| `SYNTH_BATCH_SIZE` | No | `5000` | DB insert batch size |
| `SYNTH_MAX_CONCURRENT_WRITERS` | No | `4` | Parallel DB writer count |
| `SYNTH_API_HOST` | No | `0.0.0.0` | API bind address |
| `SYNTH_API_PORT` | No | `8000` | API port |
| `SYNTH_LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `SYNTH_LOG_FORMAT` | No | `json` | Log output format |

## 5.3 Example `.env` File

```env
# Database
SYNTH_DATABASE_URI=postgresql+asyncpg://synth_user:secretpass@localhost:5432/synth_data

# Generation
SYNTH_DEFAULT_NUM_CUSTOMERS=1000
SYNTH_DEFAULT_DATE_RANGE_MONTHS=36
SYNTH_DEFAULT_SEED=42

# Performance
SYNTH_BATCH_SIZE=10000

# Logging
SYNTH_LOG_LEVEL=DEBUG
SYNTH_LOG_FORMAT=console
```

## 5.4 Configuration Validation Rules

1. `database_uri` MUST use the `postgresql+asyncpg://` scheme
2. `batch_size` SHOULD be tuned based on available memory (higher = faster, more memory)
3. `default_seed` when set ensures deterministic generation across runs
4. `db_pool_size` SHOULD be ≥ `max_concurrent_writers` to avoid pool starvation
5. All integer fields have explicit min/max bounds enforced by Pydantic

## 5.5 Configuration Loading Order

1. Environment variables (highest priority)
2. `.env` file in project root
3. Default values in Settings class (lowest priority)
