from datetime import date
from pydantic import BaseModel, Field

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
