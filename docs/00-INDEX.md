# Synthetic Commercial Data Generation Microservice — Documentation Library

> **Project Codename:** `synth_data_creator`
> **Version:** 0.1.0
> **Python Target:** ≥ 3.12
> **Last Updated:** 2026-06-06

---

## Document Index

This directory contains the complete planning, architecture, and specification documentation required to build the Synthetic Commercial Data Generation Microservice from the ground up. Every document is self-contained yet cross-referenced for navigability.

### Reading Order

For first-time readers, follow this sequence:

| # | Document | Path | Purpose |
|---|----------|------|---------|
| 1 | **Project Overview & Vision** | [`architecture/01-project-overview.md`](architecture/01-project-overview.md) | High-level goals, scope, and success criteria |
| 2 | **System Architecture** | [`architecture/02-system-architecture.md`](architecture/02-system-architecture.md) | Component decomposition, dependency graph, execution flow |
| 3 | **Technology Stack & Dependencies** | [`architecture/03-technology-stack.md`](architecture/03-technology-stack.md) | Library choices, version constraints, rationale |
| 4 | **Project Structure & Module Layout** | [`architecture/04-project-structure.md`](architecture/04-project-structure.md) | Directory tree, module responsibility map |
| 5 | **Configuration & Environment** | [`architecture/05-configuration.md`](architecture/05-configuration.md) | Env vars, config schema, validation rules |
| 6 | **Database Schema Design** | [`database/01-schema-design.md`](database/01-schema-design.md) | DDL, table specs, constraints, indexes |
| 7 | **Database Migration & Initialization** | [`database/02-migration-strategy.md`](database/02-migration-strategy.md) | Auto-init logic, idempotency, versioning |
| 8 | **Customer Segmentation Model** | [`data-generation/01-customer-segmentation.md`](data-generation/01-customer-segmentation.md) | Archetype taxonomy, behavioral dimensions, profile composition |
| 9 | **Customer Profile Generator** | [`data-generation/02-customer-profile-generator.md`](data-generation/02-customer-profile-generator.md) | Profile construction algorithm, distribution parameters |
| 10 | **Sales Data Generator** | [`data-generation/03-sales-data-generator.md`](data-generation/03-sales-data-generator.md) | Order simulation, pricing model, seasonality engine |
| 11 | **Payment Data Generator** | [`data-generation/04-payment-data-generator.md`](data-generation/04-payment-data-generator.md) | Payment scheduling, partial payment logic, aging simulation |
| 12 | **Returns Data Generator** | [`data-generation/05-returns-data-generator.md`](data-generation/05-returns-data-generator.md) | Return probability model, reason taxonomy, credit note logic |
| 13 | **Statistical Realism Engine** | [`data-generation/06-statistical-realism.md`](data-generation/06-statistical-realism.md) | Distribution enforcement, KPI targeting, Pareto calibration |
| 14 | **Scalability & Performance** | [`data-generation/07-scalability.md`](data-generation/07-scalability.md) | Batch processing, memory management, parallelism |
| 15 | **API Specification** | [`api/01-api-specification.md`](api/01-api-specification.md) | Endpoints, request/response contracts, error codes |
| 16 | **API Data Contracts** | [`api/02-data-contracts.md`](api/02-data-contracts.md) | Pydantic models, validation rules, serialization |
| 17 | **Deployment Guide** | [`deployment/01-deployment-guide.md`](deployment/01-deployment-guide.md) | Docker, docker-compose, production checklist |
| 18 | **Testing Strategy** | [`testing/01-testing-strategy.md`](testing/01-testing-strategy.md) | Test pyramid, fixtures, data validation tests |

---

## Quick Start (For Developers)

```bash
# 1. Clone and enter
cd synth_data_creator

# 2. Install dependencies
uv sync          # or: pip install -e ".[dev]"

# 3. Configure
export DATABASE_URI="postgresql+asyncpg://user:pass@localhost:5432/synth_data"

# 4. Run the microservice
uvicorn synth_data_creator.api.app:app --reload --port 8000

# 5. Trigger generation
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"num_customers": 500, "date_range_months": 24}'
```

---

## Conventions Used in This Library

| Convention | Meaning |
|-----------|---------|
| `MUST` | Absolute requirement |
| `SHOULD` | Strong recommendation |
| `MAY` | Optional but encouraged |
| `[TBD]` | To be decided during implementation |
| `→` | Navigational cross-reference |
| `⚠️` | Design decision with trade-offs |
