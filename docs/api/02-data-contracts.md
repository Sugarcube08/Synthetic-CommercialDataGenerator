# 02 — API Data Contracts (Pydantic Models)

## 2.1 Request Models

```python
from datetime import date, datetime
from pydantic import BaseModel, Field, PostgresDsn
from uuid import UUID


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
    date_range_start: date = Field(
        default=None,
        description="Start of transaction date range (default: 2 years ago)"
    )
    date_range_end: date = Field(
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
    database_uri: PostgresDsn | None = Field(
        default=None,
        description="Override database URI (default: from environment)"
    )
    options: GenerationOptions = Field(default_factory=GenerationOptions)

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
```

## 2.2 Response Models

```python
class GenerationConfig(BaseModel):
    """Echoed configuration in generation response."""
    num_customers: int
    date_range_start: date
    date_range_end: date
    seed: int | None


class GenerationAccepted(BaseModel):
    """Response for accepted generation job."""
    job_id: str
    status: str = "accepted"
    message: str = "Generation job queued"
    config: GenerationConfig
    status_url: str


class RecordCounts(BaseModel):
    """Record counts for a single table."""
    generated: int = 0
    written: int = 0


class RecordsSummary(BaseModel):
    """Record counts across all tables."""
    customers: RecordCounts = Field(default_factory=RecordCounts)
    sales: RecordCounts = Field(default_factory=RecordCounts)
    payments: RecordCounts = Field(default_factory=RecordCounts)
    returns: RecordCounts = Field(default_factory=RecordCounts)


class KPIReport(BaseModel):
    """Post-generation KPI validation results."""
    dso: float = Field(description="Days Sales Outstanding")
    collection_efficiency: float = Field(description="Collection efficiency ratio")
    return_rate: float = Field(description="Return rate as fraction")
    gini_coefficient: float = Field(description="Revenue concentration Gini coefficient")
    revenue_top20_pct: float = Field(description="Revenue share of top 20% customers")
    repeat_purchase_rate: float = Field(description="Fraction of customers with 2+ orders")
    churn_rate: float = Field(description="Fraction of inactive customers")
    avg_payment_delay_days: float = Field(description="Average payment delay in days")
    outstanding_ratio: float = Field(description="Total outstanding / Total invoiced")
    all_passed: bool = Field(description="Whether all KPIs are within target ranges")


class ErrorDetail(BaseModel):
    """Structured error information."""
    code: str
    message: str
    details: str | dict | None = None


class StatusResponse(BaseModel):
    """Response for GET /api/v1/status/{job_id}."""
    job_id: str
    status: str  # "accepted" | "running" | "completed" | "failed"
    phase: str | None = None
    phase_progress: float = 0.0
    total_progress: float = 0.0
    records: RecordsSummary = Field(default_factory=RecordsSummary)
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float | None = None
    kpi_report: KPIReport | None = None
    error: ErrorDetail | None = None


class HealthResponse(BaseModel):
    """Response for GET /health."""
    status: str  # "healthy" | "unhealthy"
    version: str
    database: str  # "connected" | "disconnected"
    uptime_seconds: float
    active_jobs: int
    error: str | None = None
```

## 2.3 Validation Rules

| Field | Rule | Error Message |
|-------|------|--------------|
| `num_customers` | 10 ≤ value ≤ 100,000 | "Customer count must be between 10 and 100,000" |
| `date_range_start` | Must be before `date_range_end` | "Start date must precede end date" |
| `date_range_end − date_range_start` | ≥ 30 days | "Date range must span at least 30 days" |
| `batch_size` | 100 ≤ value ≤ 50,000 | "Batch size must be between 100 and 50,000" |
| `database_uri` | Must use `postgresql+asyncpg://` scheme | "Database URI must use asyncpg scheme" |
| `seed` | ≥ 0 if provided | "Seed must be a non-negative integer" |

## 2.4 Serialization Notes

- All dates use ISO 8601 format (`YYYY-MM-DD`)
- All timestamps use ISO 8601 with timezone (`YYYY-MM-DDTHH:MM:SS+00:00`)
- Monetary values are serialized as floats with 2 decimal places
- UUIDs are serialized as hyphenated strings
- Percentages are stored as decimals (0.0–1.0), not 0–100
