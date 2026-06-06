from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator

class GenerationOptions(BaseModel):
    """Fine-grained control over what to generate."""

    generate_sales: bool = Field(default=True, description="Generate raw_sales records")
    generate_payments: bool = Field(default=True, description="Generate raw_payments records")
    generate_returns: bool = Field(default=True, description="Generate raw_returns records")
    drop_existing: bool = Field(
        default=False,
        description="Drop and recreate all tables before generation"
    )
    validate_kpis: bool = Field(
        default=True,
        description="Run KPI validation after generation"
    )


class GenerationRequest(BaseModel):
    """Request body for POST /api/v1/generate."""

    num_customers: int = Field(
        default=500,
        ge=10,
        le=100_000,
        description="Number of customer records to generate"
    )
    date_range_start: date | None = Field(
        default=None,
        description="Start of transaction date range (default: 2 years ago)"
    )
    date_range_end: date | None = Field(
        default=None,
        description="End of transaction date range (default: today)"
    )
    seed: int | None = Field(
        default=None,
        ge=0,
        description="RNG seed for reproducible generation"
    )
    batch_size: int = Field(
        default=5000,
        ge=100,
        le=50_000,
        description="Batch size for database inserts"
    )
    database_uri: str | None = Field(
        default=None,
        description="Override database URI (default: from environment)"
    )
    options: GenerationOptions = Field(default_factory=GenerationOptions)

    @field_validator("database_uri")
    @classmethod
    def validate_database_uri(cls, v: str | None) -> str | None:
        if v is not None:
            if not v.startswith("postgresql+asyncpg://"):
                raise ValueError("Database URI must use the 'postgresql+asyncpg://' scheme")
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> "GenerationRequest":
        start = self.date_range_start
        end = self.date_range_end

        if start is not None and end is not None:
            if start >= end:
                raise ValueError("Start date must precede end date")
            if (end - start).days < 30:
                raise ValueError("Date range must span at least 30 days")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "num_customers": 500,
                    "date_range_start": "2023-01-01",
                    "date_range_end": "2024-12-31",
                    "seed": 42,
                    "options": {
                        "generate_sales": True,
                        "generate_payments": True,
                        "generate_returns": True,
                    }
                }
            ]
        }
    }
