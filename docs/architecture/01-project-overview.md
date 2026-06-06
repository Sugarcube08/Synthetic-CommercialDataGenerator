# 01 — Project Overview & Vision

## 1.1 Problem Statement

Organizations building analytics platforms, BI dashboards, ML credit-risk models, and forecasting pipelines frequently need realistic commercial transaction data for development, testing, and demonstration. Real production data is:

- Subject to privacy regulations (GDPR, CCPA, DPDP Act)
- Difficult to anonymize without destroying statistical properties
- Not available in early-stage projects
- Expensive to acquire and license

A purpose-built synthetic data generator that produces **internally consistent, behaviorally coherent, and statistically realistic** wholesale distribution data eliminates these blockers.

## 1.2 Vision

Build a **self-contained Python microservice** that:

1. Accepts a PostgreSQL connection URI
2. Auto-initializes the required schema
3. Generates a complete, realistic wholesale distributor database
4. Exposes a simple HTTP API for triggering and configuring generation
5. Produces data suitable for production-grade analytics without post-processing

The generated dataset should be **indistinguishable from a real wholesale company's operational database** to an analyst examining KPIs, distributions, and temporal patterns.

## 1.3 Scope

### In Scope

| Capability | Description |
|-----------|-------------|
| Schema auto-creation | DDL execution on first run |
| Customer generation | Diverse archetypes with persistent behavioral profiles |
| Sales generation | Realistic invoices with products, quantities, pricing, taxes |
| Payment generation | Partial, full, delayed, and overdue payments |
| Returns generation | Damage, delivery, dissatisfaction, excess inventory returns |
| HTTP API | REST endpoints for triggering and monitoring generation |
| Scalability | Hundreds to thousands of customers, millions of records |
| Statistical realism | Pareto distribution, realistic KPIs, temporal coherence |

### Out of Scope (v0.1)

| Exclusion | Rationale |
|----------|-----------|
| Real-time streaming generation | Batch generation is sufficient for v0.1 |
| Multi-tenant isolation | Single-database target per invocation |
| Web UI / dashboard | API-only; UI is a separate concern |
| Data export (CSV/Parquet) | Direct database population is the primary interface |
| Product catalog management | Products are generated internally, not managed externally |

## 1.4 Success Criteria

| Criterion | Measurement |
|----------|-------------|
| **Internal Consistency** | Every payment references a valid invoice; every return references a valid sale |
| **Behavioral Coherence** | A customer classified as "whale + fast payer + growing" exhibits those traits across all tables |
| **Statistical Realism** | Top 20% of customers produce ≥ 80% of revenue (Pareto) |
| **KPI Validity** | Generated DSO, CLV, collection efficiency fall within industry benchmarks |
| **Scalability** | 1M+ records generated in < 10 minutes on commodity hardware |
| **Idempotent Init** | Schema creation is safe to run multiple times without data loss |
| **API Reliability** | All endpoints respond within documented SLAs |

## 1.5 Stakeholders

| Role | Interest |
|------|---------|
| Data Engineers | Schema design, data pipeline compatibility |
| Data Scientists | Statistical validity, ML feature engineering |
| BI Analysts | KPI realism, dashboard-ready data |
| Backend Developers | API contracts, deployment, scalability |
| QA Engineers | Testability, reproducibility (seeded generation) |

## 1.6 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.12+ | Ecosystem maturity, data science alignment |
| Web Framework | FastAPI | Async support, auto-documentation, Pydantic integration |
| ORM | SQLAlchemy 2.0 (async) | Type-safe queries, migration ecosystem |
| Database | PostgreSQL | JSONB support, window functions, partitioning |
| Async Driver | asyncpg | Fastest Python PostgreSQL driver |
| Data Generation | NumPy + custom engines | Statistical control, reproducibility |
| Configuration | Pydantic Settings | Validation, env var binding, type safety |

→ See [03-technology-stack.md](03-technology-stack.md) for detailed dependency analysis.
