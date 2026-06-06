# 01 — Testing Strategy

## 1.1 Test Pyramid

```
        ┌──────────┐
        │ E2E Tests│  ← 5% — Full generation pipeline
        │  (API)   │
        ├──────────┤
        │Integration│  ← 25% — DB operations, schema init
        │  Tests    │
        ├──────────┤
        │          │
        │   Unit   │  ← 70% — Engines, profiles, stats
        │  Tests   │
        │          │
        └──────────┘
```

## 1.2 Unit Tests

### Customer Generation (`tests/test_generation/test_customers.py`)

| Test | Description |
|------|-------------|
| `test_profile_segment_assignment` | Verify all 6 segments are assigned within valid enums |
| `test_profile_immutability` | Frozen dataclass cannot be mutated |
| `test_volume_segment_distribution` | 10K profiles match weight distribution (±5%) |
| `test_pareto_concentration` | Top 20% estimated revenue ≥ 75% of total |
| `test_correlation_constraints` | Growing + Churn-Risk never co-assigned |
| `test_registration_date_bounds` | All dates within configured range |
| `test_deterministic_seed` | Same seed → identical profiles |
| `test_customer_code_uniqueness` | No duplicate customer codes |

### Sales Generation (`tests/test_generation/test_sales.py`)

| Test | Description |
|------|-------------|
| `test_financial_integrity` | gross = qty × price; invoice = taxable + tax |
| `test_gst_intra_state` | CGST + SGST, zero IGST for same-state |
| `test_gst_inter_state` | IGST only, zero CGST/SGST for cross-state |
| `test_order_frequency` | Frequent buyers have shorter intervals than rare |
| `test_seasonality_peaks` | Seasonal buyers cluster in peak months |
| `test_lifecycle_growing` | Growing customers have increasing order values |
| `test_lifecycle_churn` | Churn-risk customers stop ordering after threshold |
| `test_invoice_number_sequence` | Sequential, year-prefixed, no gaps |
| `test_discount_tiers` | Whales get higher discounts than small |

### Payment Generation (`tests/test_generation/test_payments.py`)

| Test | Description |
|------|-------------|
| `test_payment_references_valid_invoice` | Every payment.invoice_id exists in sales |
| `test_total_paid_lte_invoice_amount` | No overpayment beyond invoice total |
| `test_hyper_payer_prepayment` | Hyper payers have negative or zero delay |
| `test_chronic_late_delay` | Chronic late payments average > 60 days |
| `test_partial_payment_sum` | Split payments sum to expected total |
| `test_payment_mode_distribution` | Large payments prefer RTGS/NEFT |
| `test_outstanding_balance_consistency` | balance_due = invoice_amount − amount_paid |

### Returns Generation (`tests/test_generation/test_returns.py`)

| Test | Description |
|------|-------------|
| `test_return_references_valid_sale` | Every return.sale_id exists in sales |
| `test_return_quantity_lte_original` | Returned qty ≤ original sold qty |
| `test_return_date_after_invoice` | Return date ≥ invoice date |
| `test_return_rate_by_discipline` | Undisciplined > Moderate > Disciplined |
| `test_reason_category_correlation` | Pharma has more "expired_product" reasons |
| `test_credit_note_generation` | Approved returns get credit notes |

### Statistical Realism (`tests/test_stats/`)

| Test | Description |
|------|-------------|
| `test_lognormal_sampling` | Values match expected μ and σ |
| `test_gini_coefficient` | Correct calculation for known inputs |
| `test_pareto_enforcement` | Redistribution achieves target Gini |
| `test_truncated_normal_bounds` | All samples within [low, high] |
| `test_kpi_ranges` | Generated KPIs fall within benchmarks |

## 1.3 Integration Tests

### Database (`tests/test_db/`)

| Test | Description |
|------|-------------|
| `test_schema_creation` | All 4 tables created from scratch |
| `test_schema_idempotency` | Double-init doesn't corrupt data |
| `test_bulk_insert_performance` | 10K rows inserted in < 2 seconds |
| `test_foreign_key_enforcement` | Invalid customer_id rejected |
| `test_check_constraint_enforcement` | Negative quantity rejected |
| `test_index_creation` | All expected indexes present |

### Fixtures

```python
# tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

@pytest.fixture(scope="session")
def database_uri() -> str:
    """Use a dedicated test database."""
    return "postgresql+asyncpg://synth_test:test@localhost:5432/synth_test"

@pytest.fixture
async def engine(database_uri: str) -> AsyncEngine:
    """Create a fresh engine for each test."""
    eng = create_async_engine(database_uri)
    yield eng
    await eng.dispose()

@pytest.fixture
async def initialized_db(engine: AsyncEngine) -> AsyncEngine:
    """Engine with schema initialized."""
    await initialize_schema(engine)
    yield engine
    await drop_all_tables(engine)

@pytest.fixture
def seeded_rng() -> numpy.random.Generator:
    """Deterministic RNG for reproducible tests."""
    return numpy.random.default_rng(seed=12345)

@pytest.fixture
def sample_profiles(seeded_rng) -> list[CustomerProfile]:
    """Pre-generated set of 50 customer profiles."""
    return generate_profiles(num=50, rng=seeded_rng)
```

## 1.4 End-to-End Tests

### Full Pipeline Test

```python
async def test_full_generation_pipeline(database_uri: str):
    """Test complete generation from API request to database verification."""

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Trigger generation
        response = await client.post("/api/v1/generate", json={
            "num_customers": 50,
            "seed": 42,
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-12-31",
        })
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        # Poll until complete
        for _ in range(60):
            status = await client.get(f"/api/v1/status/{job_id}")
            if status.json()["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(1)

        result = status.json()
        assert result["status"] == "completed"

        # Verify record counts
        assert result["records"]["customers"]["written"] == 50
        assert result["records"]["sales"]["written"] > 0
        assert result["records"]["payments"]["written"] > 0

        # Verify KPIs
        kpi = result["kpi_report"]
        assert kpi["all_passed"] is True
        assert 35 <= kpi["dso"] <= 75
```

## 1.5 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=synth_data_creator --cov-report=html

# Run specific test module
pytest tests/test_generation/test_customers.py -v

# Run only unit tests (fast)
pytest tests/test_generation tests/test_stats -v

# Run integration tests (requires database)
pytest tests/test_db -v

# Run E2E tests
pytest tests/test_api -v
```

## 1.6 CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: synth_test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: synth_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy src/
      - run: pytest --cov=synth_data_creator --cov-report=xml
        env:
          SYNTH_DATABASE_URI: postgresql+asyncpg://synth_test:test@localhost:5432/synth_test
```

## 1.7 Data Validation Test Suite

Beyond functional tests, a dedicated validation suite checks the **statistical properties** of generated data:

| Validation | Method |
|-----------|--------|
| Revenue follows Pareto | Lorenz curve + Gini coefficient |
| Payment delays match segments | KS test against configured distributions |
| Seasonal patterns visible | Autocorrelation analysis on monthly order counts |
| Lifecycle trends correct | Linear regression slope direction per lifecycle segment |
| Return rates within bounds | Chi-square test against expected proportions |

These tests run on a 1,000-customer dataset and verify distributional properties rather than exact values.
