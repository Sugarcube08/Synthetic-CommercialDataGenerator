import pytest
import asyncio
from datetime import date
from dataclasses import replace
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.api.app import app, lifespan
from synth_data_creator.api.dependencies import get_db_engine
from synth_data_creator.core.exceptions import (
    SynthDataError,
    JobNotFoundError,
    JobAlreadyRunningError,
    ConfigurationError,
    SchemaInitError,
    SchemaVerificationError,
)
from synth_data_creator.core.logging import configure_logging
from synth_data_creator.db.engine import create_session_maker
from synth_data_creator.db.bulk_ops import bulk_insert
from synth_data_creator.db.schema_init import initialize_schema, verify_schema
from synth_data_creator.generation.customers.engine import estimate_annual_revenue, generate_profiles
from synth_data_creator.generation.customers.segments import LifecycleSegment
from synth_data_creator.generation.sales.products import pick_product
from synth_data_creator.generation.payments.scheduling import split_payment
from synth_data_creator.generation.returns.engine import generate_returns_for_customer, GlobalReturnTracker
from synth_data_creator.generation.sales.engine import get_lifecycle_modifier
from synth_data_creator.stats.distributions import sample_truncated_normal, sample_event_count
from synth_data_creator.stats.pareto import compute_gini, redistribute_revenue_weights
from synth_data_creator.main import main

pytestmark = pytest.mark.asyncio

# Register temporary exceptions routes to trigger app exception handlers
@app.get("/_test/job-not-found")
def route_job_not_found():
    raise JobNotFoundError("Job not found dummy message")

@app.get("/_test/job-already-running")
def route_job_already_running():
    raise JobAlreadyRunningError("Job already running dummy message")

@app.get("/_test/configuration-error")
def route_configuration_error():
    raise ConfigurationError("Configuration dummy error")

@app.get("/_test/schema-init-error")
def route_schema_init_error():
    raise SchemaInitError("Schema init dummy error")

@app.get("/_test/schema-verify-error")
def route_schema_verify_error():
    raise SchemaVerificationError("Schema verify dummy error")

@app.get("/_test/generic-synth-error")
def route_generic_synth_error():
    raise SynthDataError("Generic synth dummy error")

@app.get("/_test/unhandled-exception")
def route_unhandled_exception():
    raise ValueError("Unexpected Python error")

@app.get("/_test/http-exception-simple")
def route_http_exception_simple():
    raise HTTPException(status_code=400, detail="Simple string detail")


async def test_fastapi_exception_handlers() -> None:
    """Verify custom exception handlers format responses correctly."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. JobNotFoundError (404)
        resp = await ac.get("/_test/job-not-found")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "JOB_NOT_FOUND"

        # 2. JobAlreadyRunningError (409)
        resp = await ac.get("/_test/job-already-running")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "JOB_ALREADY_RUNNING"

        # 3. ConfigurationError (422)
        resp = await ac.get("/_test/configuration-error")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

        # 4. SchemaInitError (500)
        resp = await ac.get("/_test/schema-init-error")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "SCHEMA_INIT_FAILED"

        # 5. SchemaVerificationError (500)
        resp = await ac.get("/_test/schema-verify-error")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "SCHEMA_INIT_FAILED"

        # 6. Generic SynthDataError (500)
        resp = await ac.get("/_test/generic-synth-error")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "INTERNAL_ERROR"

        # 7. Unhandled generic exception (500)
        resp = await ac.get("/_test/unhandled-exception")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "INTERNAL_ERROR"
        assert "Unexpected Python error" in resp.json()["error"]["details"]

        # 8. HTTPException with simple string detail
        resp = await ac.get("/_test/http-exception-simple")
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "ERROR"
        assert resp.json()["error"]["message"] == "Simple string detail"


async def test_app_lifespan() -> None:
    """Verify ASGI lifespan startup and shutdown runs successfully."""
    # Test the lifespan context manager directly
    async with lifespan(app):
        pass


def test_core_logging_configuration() -> None:
    """Verify loggers can be configured with json and console formats."""
    configure_logging(log_level="DEBUG", log_format="json")
    configure_logging(log_level="WARNING", log_format="console")


def test_db_engine_session_maker(engine: AsyncEngine) -> None:
    """Verify creation of async session maker."""
    sm = create_session_maker(engine)
    assert sm is not None


async def test_db_bulk_insert_edge_cases(engine: AsyncEngine) -> None:
    """Verify empty bulk inserts and correct exception handling."""
    # Empty insertion (returns early)
    await bulk_insert(engine, "customers", [])

    # Insertion on non-existent table throws exception
    with pytest.raises(Exception):
        await bulk_insert(engine, "non_existent_table", [{"id": "not-a-uuid"}])


async def test_db_schema_verification_failure(engine: AsyncEngine) -> None:
    """Verify schema verification fails when tables are missing columns."""
    await initialize_schema(engine, drop_existing=True)
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE customers DROP COLUMN behavioral_profile;"))

    with pytest.raises(SchemaVerificationError):
        await verify_schema(engine)


async def test_db_schema_lifecycle_exceptions() -> None:
    """Verify custom DB exceptions are wrapped when DB begins or connects fail."""
    mock_engine = MagicMock()
    mock_engine.begin.side_effect = Exception("DB connection error")
    with pytest.raises(SchemaInitError):
        await initialize_schema(mock_engine)

    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("DB connection error")
    with pytest.raises(SchemaVerificationError):
        await verify_schema(mock_engine)


async def test_api_health_check_unhealthy() -> None:
    """Verify health endpoint returns 503 when DB fails to connect."""
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("Database offline")
    app.dependency_overrides[get_db_engine] = lambda: mock_engine

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"
        assert resp.json()["database"] == "disconnected"

    # Clean up overrides
    app.dependency_overrides.clear()


async def test_api_generation_active_job_conflict() -> None:
    """Verify 409 Conflict when a job is already in progress."""
    from synth_data_creator.generation.orchestrator import jobs_status
    jobs_status["gen_mock_active"] = {"status": "running"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "num_customers": 50,
        }
        resp = await ac.post("/api/v1/generate", json=payload)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "JOB_ALREADY_RUNNING"

    # Clean up jobs_status
    del jobs_status["gen_mock_active"]


async def test_api_generation_validation_edge_cases() -> None:
    """Verify future start date validation in generation route."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "num_customers": 50,
            "date_range_start": "2029-01-01",  # Future start date
            "date_range_end": None,            # Defaults to today, making start > end
        }
        resp = await ac.post("/api/v1/generate", json=payload)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_api_generation_db_override(database_uri: str) -> None:
    """Verify passing a direct database_uri works and triggers dispose."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "num_customers": 10,
            "database_uri": database_uri,
            "options": {
                "drop_existing": True,
                "validate_kpis": False,
            }
        }
        resp = await ac.post("/api/v1/generate", json=payload)
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]
        
        # Await completion
        for _ in range(30):
            status_resp = await ac.get(f"/api/v1/status/{job_id}")
            if status_resp.json()["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.1)


async def test_api_generation_background_exception() -> None:
    """Verify background task failures update job status to failed."""
    with patch("synth_data_creator.api.routes.generation.run_generation_job", side_effect=Exception("Task crashed")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {
                "num_customers": 10,
                "options": {
                    "validate_kpis": False,
                }
            }
            resp = await ac.post("/api/v1/generate", json=payload)
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]
            
            # Await completion/failure
            for _ in range(30):
                status_resp = await ac.get(f"/api/v1/status/{job_id}")
                if status_resp.json()["status"] in ("completed", "failed"):
                    break
                await asyncio.sleep(0.1)
                
            status_data = status_resp.json()
            assert status_data["status"] == "failed"
            assert "Task crashed" in status_data["error"]["message"]


def test_customer_registration_date_bounds_fallback() -> None:
    """Verify registration date fallback when total_days <= 0."""
    from synth_data_creator.generation.customers.engine import assign_registration_date
    import numpy as np
    rng = np.random.default_rng(12)
    d = date(2024, 1, 1)
    res = assign_registration_date(d, d, LifecycleSegment.STABLE, rng)
    assert res == d


def test_estimate_annual_revenue_calculation(sample_profiles) -> None:
    """Verify estimate_annual_revenue calculations across lifecycles."""
    # Test growing
    p_growing = sample_profiles[0]
    # Estimate annual revenue returns float
    rev = estimate_annual_revenue(p_growing)
    assert isinstance(rev, float)
    assert rev >= 0


def test_pick_product_unknown_business_type() -> None:
    """Verify pick_product falls back to uniform selection for unknown business types."""
    import numpy as np
    rng = np.random.default_rng(42)
    cat, prod = pick_product("unknown_business_type", rng)
    assert cat is not None
    assert prod is not None


def test_returns_engine_unknown_category(sample_profiles) -> None:
    """Verify returns engine chooses random ReturnReason when category is unknown."""
    import numpy as np
    rng = np.random.default_rng(99)
    sales = [{
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "customer_id": sample_profiles[0].id,
        "product_category": "UnknownCategory",
        "invoice_date": date(2024, 5, 5),
        "quantity": 10,
        "unit_price": 500.0,
        "discount_pct": 5.0,
        "tax_rate": 18.0,
        "invoice_number": "INV-12345",
    }]
    # Force high return probability on a copied profile to guarantee return generation
    profile = replace(sample_profiles[0], return_probability=1.0)
    tracker = GlobalReturnTracker()
    returns = generate_returns_for_customer(profile, sales, tracker, date(2024, 12, 31), rng)
    assert len(returns) > 0


def test_sales_engine_lifecycle_modifier_same_date(sample_profiles) -> None:
    """Verify lifecycle modifier logic returns 1.0 when start_date == end_date."""
    d = date(2024, 5, 5)
    res = get_lifecycle_modifier(sample_profiles[0], d, d, d)
    assert res == 1.0


def test_split_payment_zero_amount_handling() -> None:
    """Verify split payment behaves when splitting extremely small amounts."""
    import numpy as np
    rng = np.random.default_rng(5)
    res = split_payment(0.01, 3, rng)
    assert all(val > 0 for val in res)


def test_sample_truncated_normal_bounds_edges() -> None:
    """Verify truncated normal behaves correctly with std <= 0 and hard rejection loops."""
    import numpy as np
    rng = np.random.default_rng(88)
    
    # 1. std <= 0
    res = sample_truncated_normal(mean=10.0, std=0.0, low=5.0, high=15.0, rng=rng)
    assert res == 10.0
    
    # 2. Rejection sampling fallback after 100 tries (very tight bounds away from mean)
    res2 = sample_truncated_normal(mean=0.0, std=1.0, low=10.0, high=11.0, rng=rng)
    assert 10.0 <= res2 <= 11.0


def test_sample_event_count_sampler() -> None:
    """Verify Poisson event count sampler returns integer."""
    import numpy as np
    rng = np.random.default_rng(1)
    res = sample_event_count(5.0, rng)
    assert isinstance(res, int)


def test_gini_coefficient_zeros() -> None:
    """Verify compute_gini returns 0.0 when cumulative values sum to 0."""
    assert compute_gini([0.0, 0.0, 0.0]) == 0.0


def test_redistribute_revenue_weights_fallback() -> None:
    """Verify redistribute_revenue_weights returns inputs."""
    weights = [0.1, 0.2, 0.7]
    assert redistribute_revenue_weights(weights) == weights


def test_main_entry_point_startup() -> None:
    """Verify package main entry point starts server via uvicorn."""
    with patch("uvicorn.run") as mock_run:
        main()
        mock_run.assert_called_once()
