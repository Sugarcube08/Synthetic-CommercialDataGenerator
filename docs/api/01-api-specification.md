# 01 — API Specification

## 1.1 Overview

The microservice exposes a REST API via FastAPI with automatic OpenAPI documentation available at `/docs` (Swagger UI) and `/redoc`.

**Base URL:** `http://{host}:{port}/api/v1`

## 1.2 Endpoints

### POST `/api/v1/generate`

Triggers a new data generation job.

**Request Body:**

```json
{
  "num_customers": 500,
  "date_range_start": "2023-01-01",
  "date_range_end": "2024-12-31",
  "seed": 42,
  "batch_size": 5000,
  "database_uri": "postgresql+asyncpg://user:pass@host:5432/db",
  "options": {
    "generate_sales": true,
    "generate_payments": true,
    "generate_returns": true,
    "drop_existing": false,
    "validate_kpis": true
  }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `num_customers` | int | No | 500 | Number of customers to generate |
| `date_range_start` | date | No | 2 years ago | Start of transaction date range |
| `date_range_end` | date | No | today | End of transaction date range |
| `seed` | int | No | null | RNG seed for reproducibility |
| `batch_size` | int | No | 5000 | Database insert batch size |
| `database_uri` | string | No | env default | Override database connection |
| `options.generate_sales` | bool | No | true | Generate sales records |
| `options.generate_payments` | bool | No | true | Generate payment records |
| `options.generate_returns` | bool | No | true | Generate return records |
| `options.drop_existing` | bool | No | false | Drop and recreate tables |
| `options.validate_kpis` | bool | No | true | Run KPI validation after generation |

**Response (202 Accepted):**

```json
{
  "job_id": "gen_a1b2c3d4",
  "status": "accepted",
  "message": "Generation job queued",
  "config": {
    "num_customers": 500,
    "date_range_start": "2023-01-01",
    "date_range_end": "2024-12-31",
    "seed": 42
  },
  "status_url": "/api/v1/status/gen_a1b2c3d4"
}
```

---

### GET `/api/v1/status/{job_id}`

Poll the status of a generation job.

**Response (200 OK — In Progress):**

```json
{
  "job_id": "gen_a1b2c3d4",
  "status": "running",
  "phase": "sales",
  "phase_progress": 0.65,
  "total_progress": 0.45,
  "records": {
    "customers": {"generated": 500, "written": 500},
    "sales": {"generated": 42000, "written": 38000},
    "payments": {"generated": 0, "written": 0},
    "returns": {"generated": 0, "written": 0}
  },
  "elapsed_seconds": 35.2,
  "estimated_remaining_seconds": 42.8
}
```

**Response (200 OK — Completed):**

```json
{
  "job_id": "gen_a1b2c3d4",
  "status": "completed",
  "total_progress": 1.0,
  "records": {
    "customers": {"generated": 500, "written": 500},
    "sales": {"generated": 67432, "written": 67432},
    "payments": {"generated": 82156, "written": 82156},
    "returns": {"generated": 3201, "written": 3201}
  },
  "elapsed_seconds": 78.5,
  "kpi_report": {
    "dso": 42.3,
    "collection_efficiency": 0.847,
    "return_rate": 0.048,
    "gini_coefficient": 0.72,
    "revenue_top20_pct": 0.81,
    "all_passed": true
  }
}
```

**Response (200 OK — Failed):**

```json
{
  "job_id": "gen_a1b2c3d4",
  "status": "failed",
  "error": {
    "code": "DATABASE_CONNECTION_FAILED",
    "message": "Could not connect to PostgreSQL after 3 attempts",
    "details": "Connection refused: localhost:5432"
  },
  "elapsed_seconds": 9.2
}
```

---

### GET `/health`

Liveness and readiness probe.

**Response (200 OK):**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "connected",
  "uptime_seconds": 3600.5,
  "active_jobs": 1
}
```

**Response (503 Service Unavailable):**

```json
{
  "status": "unhealthy",
  "version": "0.1.0",
  "database": "disconnected",
  "error": "Connection pool exhausted"
}
```

---

## 1.3 Error Response Format

All errors follow a consistent structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": { ... }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|------------|-------------|
| `VALIDATION_ERROR` | 422 | Request body validation failed |
| `DATABASE_CONNECTION_FAILED` | 503 | Cannot connect to PostgreSQL |
| `SCHEMA_INIT_FAILED` | 500 | DDL execution failed |
| `GENERATION_FAILED` | 500 | Error during data generation |
| `JOB_NOT_FOUND` | 404 | Unknown job_id |
| `JOB_ALREADY_RUNNING` | 409 | A generation job is already active |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## 1.4 Rate Limiting

- Only 1 generation job can run concurrently (enforced server-side)
- Status polling has no rate limit
- Health endpoint has no rate limit

## 1.5 OpenAPI Tags

| Tag | Endpoints |
|-----|----------|
| `generation` | POST /generate, GET /status |
| `health` | GET /health |
