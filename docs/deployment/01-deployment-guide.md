# 01 — Deployment Guide

## 1.1 Local Development Setup

### Prerequisites

- Python ≥ 3.12
- PostgreSQL ≥ 14 (local or Docker)
- `uv` package manager (recommended) or `pip`

### Step-by-Step

```bash
# 1. Clone the repository
git clone <repo-url>
cd synth_data_creator

# 2. Install dependencies
uv sync                    # or: pip install -e ".[dev]"

# 3. Start PostgreSQL (if using Docker)
docker run -d \
  --name synth-pg \
  -e POSTGRES_USER=synth_user \
  -e POSTGRES_PASSWORD=secretpass \
  -e POSTGRES_DB=synth_data \
  -p 5432:5432 \
  postgres:16-alpine

# 4. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 5. Run the service
uvicorn synth_data_creator.api.app:app --reload --port 8000

# 6. Open API docs
# http://localhost:8000/docs
```

## 1.2 Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
RUN mkdir -p src/synth_data_creator && touch src/synth_data_creator/__init__.py
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .

# Create non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "synth_data_creator.api.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1"]
```

### docker-compose.yml

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: synth_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-secretpass}
      POSTGRES_DB: synth_data
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U synth_user -d synth_data"]
      interval: 5s
      timeout: 5s
      retries: 5

  synth-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      SYNTH_DATABASE_URI: postgresql+asyncpg://synth_user:${DB_PASSWORD:-secretpass}@postgres:5432/synth_data
      SYNTH_LOG_LEVEL: INFO
      SYNTH_LOG_FORMAT: json
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
```

### Running with Docker Compose

```bash
# Build and start
docker compose up -d --build

# Check logs
docker compose logs -f synth-api

# Trigger generation
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"num_customers": 1000, "seed": 42}'

# Tear down
docker compose down -v   # -v removes volumes
```

## 1.3 Environment File Template

```env
# .env.example

# ── Required ──────────────────────────────────
SYNTH_DATABASE_URI=postgresql+asyncpg://synth_user:secretpass@localhost:5432/synth_data

# ── Optional ──────────────────────────────────
SYNTH_DEFAULT_NUM_CUSTOMERS=500
SYNTH_DEFAULT_DATE_RANGE_MONTHS=24
SYNTH_DEFAULT_SEED=
SYNTH_BATCH_SIZE=5000
SYNTH_DB_POOL_SIZE=10
SYNTH_LOG_LEVEL=INFO
SYNTH_LOG_FORMAT=console
SYNTH_API_PORT=8000
```

## 1.4 Production Checklist

| # | Check | Status |
|---|-------|--------|
| 1 | PostgreSQL connection pooling configured (PgBouncer recommended for >10 workers) | ☐ |
| 2 | Database credentials stored in secrets manager (not .env) | ☐ |
| 3 | Log format set to `json` for log aggregation | ☐ |
| 4 | Health check endpoint monitored | ☐ |
| 5 | Resource limits set (CPU/Memory) | ☐ |
| 6 | Non-root container user configured | ☐ |
| 7 | TLS/HTTPS termination at load balancer | ☐ |
| 8 | Backup strategy for generated data | ☐ |
| 9 | Monitoring/alerting for generation failures | ☐ |

## 1.5 PostgreSQL Tuning

For large-scale generation (>1M records), tune these PostgreSQL parameters:

```conf
# postgresql.conf adjustments
shared_buffers = 256MB
work_mem = 64MB
maintenance_work_mem = 256MB
effective_cache_size = 1GB
max_connections = 100
checkpoint_completion_target = 0.9

# Disable fsync during bulk load (ONLY for synthetic data, NOT production)
# synchronous_commit = off
```
