# 03 — Technology Stack & Dependencies

## 3.1 Runtime Requirements

| Requirement | Specification |
|------------|---------------|
| Python | ≥ 3.12 |
| PostgreSQL | ≥ 14 |
| OS | Linux (primary), macOS, Windows (WSL) |
| Memory | ≥ 512 MB available for generation |

## 3.2 Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ≥ 0.115 | HTTP API framework |
| `uvicorn[standard]` | ≥ 0.34 | ASGI server |
| `sqlalchemy[asyncio]` | ≥ 2.0 | ORM + Core query builder |
| `asyncpg` | ≥ 0.30 | Async PostgreSQL driver |
| `numpy` | ≥ 1.26 | Statistical distributions |
| `faker` | ≥ 33.0 | Realistic customer metadata |
| `pydantic` | ≥ 2.10 | Data models, API contracts |
| `pydantic-settings` | ≥ 2.7 | Environment configuration |
| `structlog` | ≥ 24.4 | Structured logging |
| `rich` | ≥ 13.9 | Console progress bars |

## 3.3 Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ≥ 8.3 | Test runner |
| `pytest-asyncio` | ≥ 0.24 | Async test support |
| `pytest-cov` | ≥ 6.0 | Coverage reporting |
| `httpx` | ≥ 0.28 | Async HTTP test client |
| `ruff` | ≥ 0.8 | Linting + formatting |
| `mypy` | ≥ 1.13 | Static type checking |

## 3.4 pyproject.toml Specification

```toml
[project]
name = "synth-data-creator"
version = "0.1.0"
description = "Synthetic commercial data generation microservice"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "numpy>=1.26",
    "faker>=33.0",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "structlog>=24.4",
    "rich>=13.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "httpx>=0.28",
    "ruff>=0.8",
    "mypy>=1.13",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

## 3.5 Why Not Alternatives

| Alternative | Reason for Rejection |
|------------|---------------------|
| Django | Too heavy; synchronous ORM by default |
| Flask | No native async support |
| Pandas | Memory overhead; NumPy suffices for generation |
| psycopg3 | asyncpg has better bulk insert performance |
| MongoDB | Relational integrity is a core requirement |
| SQLite | Cannot scale to millions of records efficiently |
