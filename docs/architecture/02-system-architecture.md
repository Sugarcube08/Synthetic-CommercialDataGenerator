# 02 — System Architecture

## 2.1 Architecture Style

The system follows a **layered modular monolith** architecture deployed as a single microservice. Internal boundaries are enforced through Python package structure, not network calls.

```
┌─────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ /generate│  │ /status  │  │ /health              │   │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘   │
│       │              │                   │               │
├───────┴──────────────┴───────────────────┴───────────────┤
│                  Orchestration Layer                      │
│  ┌─────────────────────────────────────────────────────┐ │
│  │            GenerationOrchestrator                   │ │
│  │  - Coordinates generation phases                    │ │
│  │  - Manages transaction boundaries                   │ │
│  │  - Reports progress                                 │ │
│  └──────────────────────┬──────────────────────────────┘ │
│                         │                                │
├─────────────────────────┴────────────────────────────────┤
│                  Generation Engines                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ Customer │ │  Sales   │ │ Payment  │ │  Returns   │  │
│  │ Engine   │ │  Engine  │ │  Engine  │ │  Engine    │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬───────┘  │
│       │             │            │             │          │
├───────┴─────────────┴────────────┴─────────────┴─────────┤
│              Behavioral Profile System                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │         CustomerProfile (frozen dataclass)          │ │
│  │  - Segment assignments (6 dimensions)               │ │
│  │  - Derived parameters (purchase, payment, return)   │ │
│  │  - Temporal evolution rules                         │ │
│  └──────────────────────┬──────────────────────────────┘ │
│                         │                                │
├─────────────────────────┴────────────────────────────────┤
│                Statistical Realism Layer                  │
│  ┌──────────────┐ ┌────────────┐ ┌──────────────────┐   │
│  │ Distribution │ │ Pareto     │ │ KPI Calibration  │   │
│  │ Samplers     │ │ Enforcer   │ │ Engine           │   │
│  └──────────────┘ └────────────┘ └──────────────────┘   │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                  Data Access Layer                        │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  SQLAlchemy 2.0 Async  +  asyncpg                  │ │
│  │  - Session management                               │ │
│  │  - Bulk insert optimization                         │ │
│  │  - Schema auto-initialization                       │ │
│  └──────────────────────┬──────────────────────────────┘ │
│                         │                                │
│                    ┌────┴────┐                            │
│                    │ PostgreSQL                           │
│                    └─────────┘                            │
└──────────────────────────────────────────────────────────┘
```

## 2.2 Component Responsibility Matrix

| Component | Responsibility | Dependencies |
|-----------|---------------|--------------|
| **API Layer** | HTTP request handling, validation, response serialization | Orchestration Layer |
| **GenerationOrchestrator** | Phase sequencing, progress tracking, error recovery | All Engines, DAL |
| **CustomerEngine** | Profile generation, segment assignment, behavioral parameter derivation | Behavioral Profile System, Statistical Realism |
| **SalesEngine** | Invoice generation, product selection, pricing, temporal distribution | CustomerProfile, DAL |
| **PaymentEngine** | Payment scheduling, partial payment simulation, aging | CustomerProfile, Sales records, DAL |
| **ReturnsEngine** | Return event generation, reason assignment, credit calculation | CustomerProfile, Sales records, DAL |
| **Behavioral Profile System** | Segment taxonomy, parameter ranges, profile composition rules | Statistical Realism |
| **Statistical Realism Layer** | Distribution sampling, Pareto enforcement, KPI targeting | NumPy |
| **Data Access Layer** | Database connectivity, schema init, bulk operations | SQLAlchemy, asyncpg |

## 2.3 Execution Flow

```
Generation Request
       │
       ▼
┌──────────────────┐
│ Validate Config  │  ← Pydantic model validation
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Initialize Schema│  ← Idempotent DDL execution
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Phase 1:         │
│ Generate         │  ← Behavioral profiles created
│ Customers        │     Segments assigned
└────────┬─────────┘     Revenue distribution calibrated
         │
         ▼
┌──────────────────┐
│ Phase 2:         │
│ Generate Sales   │  ← Invoices per customer based on
└────────┬─────────┘     profile-driven frequency & volume
         │
         ▼
┌──────────────────┐
│ Phase 3:         │
│ Generate         │  ← Payments linked to invoices
│ Payments         │     Partial/full per profile behavior
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Phase 4:         │
│ Generate Returns │  ← Returns linked to sales
└────────┬─────────┘     Rate driven by profile
         │
         ▼
┌──────────────────┐
│ Phase 5:         │
│ Validate &       │  ← KPI spot-checks
│ Report           │     Consistency verification
└──────────────────┘
```

## 2.4 Data Flow Diagram

```
                    ┌─────────────┐
                    │  Customer   │
                    │  Profiles   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Sales   │ │ Payments │ │ Returns  │
        │ Records  │ │ Records  │ │ Records  │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             │      ┌─────┘            │
             │      │   ┌──────────────┘
             ▼      ▼   ▼
        ┌─────────────────────┐
        │     PostgreSQL      │
        │  ┌───────────────┐  │
        │  │   customers   │  │
        │  ├───────────────┤  │
        │  │   raw_sales   │◄─┼── FK: customer_id
        │  ├───────────────┤  │
        │  │  raw_payments │◄─┼── FK: invoice reference
        │  ├───────────────┤  │
        │  │  raw_returns  │◄─┼── FK: sale reference
        │  └───────────────┘  │
        └─────────────────────┘
```

## 2.5 Key Architectural Principles

### 2.5.1 Customer-Centric Generation

All transactional data flows from the customer profile. The profile is the **single source of truth** for behavioral parameters. Engines never generate random data independently — they always consult the customer's profile to determine:

- How many orders to create
- What order sizes to use
- When payments will arrive
- How likely a return is

### 2.5.2 Deterministic Reproducibility

Given the same seed and configuration, the system MUST produce identical output. This is achieved through:

- NumPy `Generator` instances seeded per-customer
- Deterministic ordering of generation phases
- No reliance on wall-clock time for data decisions

### 2.5.3 Phased Generation with Referential Integrity

Each phase builds on the outputs of previous phases:

1. **Customers** → standalone, no dependencies
2. **Sales** → depends on customer profiles
3. **Payments** → depends on sales invoices
4. **Returns** → depends on sales records

This ordering guarantees referential integrity without deferred constraint checks.

### 2.5.4 Batch-Optimized Database Operations

All database writes use bulk insert strategies:

- `executemany` with parameter batches
- Configurable batch sizes (default: 5,000 rows)
- Minimal round-trips to PostgreSQL

→ See [07-scalability.md](../data-generation/07-scalability.md) for performance targets.

## 2.6 Error Handling Strategy

| Error Type | Strategy |
|-----------|----------|
| Database connection failure | Retry with exponential backoff (3 attempts) |
| Schema init failure | Abort with clear error message |
| Generation phase failure | Roll back current phase, report progress |
| Constraint violation | Log conflicting record, skip and continue |
| Memory pressure | Reduce batch size dynamically |

## 2.7 Concurrency Model

The microservice uses Python's `asyncio` event loop:

- **API requests**: Handled asynchronously by FastAPI/Uvicorn
- **Database I/O**: Non-blocking via asyncpg
- **CPU-bound generation**: Offloaded to thread pool via `asyncio.to_thread()`
- **Batch writes**: Pipelined with generation using async producer-consumer pattern

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│  Generator   │────▶│  Async Queue │────▶│  DB Writer │
│  (thread)    │     │  (bounded)   │     │  (async)   │
└─────────────┘     └──────────────┘     └────────────┘
```

This ensures that generation and database writes happen concurrently without blocking the API.
