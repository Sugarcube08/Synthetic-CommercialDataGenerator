# 04 — Project Structure & Module Layout

## 4.1 Directory Tree

```
synth_data_creator/
├── docs/                              # This documentation library
├── src/
│   └── synth_data_creator/
│       ├── __init__.py
│       ├── main.py                    # Application entry point
│       │
│       ├── api/                       # API Layer
│       │   ├── __init__.py
│       │   ├── app.py                 # FastAPI app factory
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── generation.py      # /api/v1/generate endpoints
│       │   │   ├── status.py          # /api/v1/status endpoints
│       │   │   └── health.py          # /health endpoint
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── requests.py        # Request Pydantic models
│       │   │   └── responses.py       # Response Pydantic models
│       │   └── dependencies.py        # FastAPI dependency injection
│       │
│       ├── core/                      # Core Configuration
│       │   ├── __init__.py
│       │   ├── config.py              # Pydantic Settings
│       │   ├── logging.py             # Structlog configuration
│       │   └── exceptions.py          # Custom exception hierarchy
│       │
│       ├── db/                        # Data Access Layer
│       │   ├── __init__.py
│       │   ├── engine.py              # Engine/session factory
│       │   ├── models.py              # SQLAlchemy table models
│       │   ├── schema_init.py         # Auto-init DDL logic
│       │   └── bulk_ops.py            # Optimized bulk insert helpers
│       │
│       ├── generation/                # Data Generation Engines
│       │   ├── __init__.py
│       │   ├── orchestrator.py        # Phase coordination
│       │   ├── customers/
│       │   │   ├── __init__.py
│       │   │   ├── engine.py          # Customer generation engine
│       │   │   ├── profiles.py        # Behavioral profile dataclass
│       │   │   └── segments.py        # Segment enums & distributions
│       │   ├── sales/
│       │   │   ├── __init__.py
│       │   │   ├── engine.py          # Sales generation engine
│       │   │   ├── products.py        # Product catalog & pricing
│       │   │   └── pricing.py         # Discount & tax logic
│       │   ├── payments/
│       │   │   ├── __init__.py
│       │   │   ├── engine.py          # Payment generation engine
│       │   │   └── scheduling.py      # Payment timing logic
│       │   └── returns/
│       │       ├── __init__.py
│       │       ├── engine.py          # Returns generation engine
│       │       └── reasons.py         # Return reason taxonomy
│       │
│       └── stats/                     # Statistical Realism
│           ├── __init__.py
│           ├── distributions.py       # Custom distribution samplers
│           ├── pareto.py              # Pareto enforcement
│           └── kpi_calibration.py     # KPI targeting & validation
│
├── tests/
│   ├── conftest.py                    # Shared fixtures
│   ├── test_api/
│   │   ├── test_generation.py
│   │   ├── test_status.py
│   │   └── test_health.py
│   ├── test_generation/
│   │   ├── test_customers.py
│   │   ├── test_sales.py
│   │   ├── test_payments.py
│   │   └── test_returns.py
│   ├── test_db/
│   │   ├── test_schema_init.py
│   │   └── test_bulk_ops.py
│   └── test_stats/
│       ├── test_distributions.py
│       └── test_pareto.py
│
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## 4.2 Module Responsibility Map

### `api/` — HTTP Interface

| Module | Responsibility |
|--------|---------------|
| `app.py` | FastAPI app factory, lifespan management, middleware registration |
| `routes/generation.py` | POST `/api/v1/generate` — triggers data generation |
| `routes/status.py` | GET `/api/v1/status/{job_id}` — poll generation progress |
| `routes/health.py` | GET `/health` — liveness/readiness probe |
| `models/requests.py` | `GenerationRequest` Pydantic model |
| `models/responses.py` | `GenerationResponse`, `StatusResponse`, `HealthResponse` |
| `dependencies.py` | Database session provider, config injection |

### `core/` — Cross-Cutting Concerns

| Module | Responsibility |
|--------|---------------|
| `config.py` | `Settings` class — loads from env vars / `.env` file |
| `logging.py` | Structlog processor chain, JSON/console output |
| `exceptions.py` | `GenerationError`, `SchemaInitError`, `ConfigurationError` |

### `db/` — Database Abstraction

| Module | Responsibility |
|--------|---------------|
| `engine.py` | `create_async_engine`, `async_sessionmaker`, connection pool config |
| `models.py` | SQLAlchemy `Table` definitions for all 4 core tables |
| `schema_init.py` | Idempotent `CREATE TABLE IF NOT EXISTS` execution |
| `bulk_ops.py` | Batched `INSERT` with configurable chunk sizes |

### `generation/` — Data Engines

| Module | Responsibility |
|--------|---------------|
| `orchestrator.py` | Sequence phases, track progress, handle errors |
| `customers/engine.py` | Generate customer records with behavioral profiles |
| `customers/profiles.py` | `CustomerProfile` frozen dataclass |
| `customers/segments.py` | Segment enums, weighted random selection |
| `sales/engine.py` | Generate `raw_sales` records per customer profile |
| `sales/products.py` | Product catalog with categories, base prices |
| `sales/pricing.py` | Discount tiers, tax calculation logic |
| `payments/engine.py` | Generate `raw_payments` referencing invoices |
| `payments/scheduling.py` | Payment delay distributions per segment |
| `returns/engine.py` | Generate `raw_returns` linked to sales |
| `returns/reasons.py` | Return reason enum and probability weights |

### `stats/` — Statistical Realism

| Module | Responsibility |
|--------|---------------|
| `distributions.py` | Log-normal, beta, truncated normal samplers |
| `pareto.py` | Revenue concentration enforcement (80/20) |
| `kpi_calibration.py` | Post-generation KPI validation |

## 4.3 Import Rules

To maintain clean architecture boundaries:

1. `api/` MAY import from `core/`, `generation/`, `db/`
2. `generation/` MAY import from `core/`, `db/`, `stats/`
3. `db/` MAY import from `core/` only
4. `stats/` MAY import from `core/` only
5. `core/` MUST NOT import from any sibling package
6. No circular imports are permitted

```
api  →  generation  →  stats
 │          │             │
 └──→ db ←──┘             │
       │                  │
       └──── core ←───────┘
```
