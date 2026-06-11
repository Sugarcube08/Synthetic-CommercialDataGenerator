from typing import Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application configuration loaded from environment."""

    # ── Database ──────────────────────────────────────────
    database_uri: str = Field(
        ...,
        description="PostgreSQL connection URI",
        examples=["postgresql+asyncpg://user:pass@localhost:5432/synth_data"],
    )
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=200)
    db_pool_timeout: int = Field(default=30, ge=5, le=300)

    # ── Generation Defaults ───────────────────────────────
    default_num_customers: int = Field(default=500, ge=10, le=100_000)
    default_date_range_months: int = Field(default=120, ge=1, le=240)
    default_seed: int | None = Field(default=None, description="RNG seed for reproducibility")

    @field_validator("default_seed", mode="before")
    @classmethod
    def validate_default_seed(cls, v: Any) -> int | None:
        if v == "" or v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

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

    @field_validator("database_uri")
    @classmethod
    def validate_database_uri(cls, v: Any) -> str:
        if not isinstance(v, str):
            v = str(v)
        if not v or v.strip() == "":
            raise ValueError(
                "SYNTH_DATABASE_URI environment variable is required. Example: "
                "postgresql+asyncpg://user:password@host:5432/dbname"
            )
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("Database URI must use the 'postgresql+asyncpg://' scheme")
        return v

    model_config = {
        "env_prefix": "SYNTH_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
