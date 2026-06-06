import pytest
from httpx import AsyncClient, ASGITransport
from synth_data_creator.api.app import app

pytestmark = pytest.mark.asyncio

async def test_invalid_date_range_validation() -> None:
    """Verify validation error formatting when start_date is after end_date."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "num_customers": 500,
            "date_range_start": "2024-12-31",
            "date_range_end": "2024-01-01",  # Invalid
        }
        response = await ac.post("/api/v1/generate", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"


async def test_invalid_database_uri_scheme() -> None:
    """Verify validation error formatting for non-asyncpg scheme."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "num_customers": 500,
            "database_uri": "postgresql://synth_user:secretpass@localhost:5432/synth_data",
        }
        response = await ac.post("/api/v1/generate", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "Database URI must use the 'postgresql+asyncpg://' scheme" in str(data["error"]["details"])


async def test_status_endpoint_not_found() -> None:
    """Verify status response for non-existent job ID is a 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/status/gen_nonexistent_123")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "JOB_NOT_FOUND"


async def test_full_generation_pipeline(database_uri: str) -> None:
    """Test complete generation from API request to database verification."""
    import asyncio
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Trigger generation
        response = await client.post("/api/v1/generate", json={
            "num_customers": 500,
            "seed": 42,
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-12-31",
            "options": {
                "drop_existing": True,
                "validate_kpis": True,
            }
        })
        assert response.status_code == 202
        res_data = response.json()
        job_id = res_data["job_id"]
        assert res_data["status"] == "accepted"
        assert "status_url" in res_data

        # Poll until complete
        status_data = {}
        for _ in range(60):
            status_resp = await client.get(f"/api/v1/status/{job_id}")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            if status_data["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(0.5)

        assert status_data["status"] == "completed", f"Job failed with: {status_data.get('error')}"

        # Verify record counts
        assert status_data["records"]["customers"]["written"] == 500
        assert status_data["records"]["sales"]["written"] > 0
        assert status_data["records"]["payments"]["written"] > 0

        # Verify KPIs
        kpi = status_data["kpi_report"]
        assert kpi is not None
        assert "dso" in kpi
        assert "collection_efficiency" in kpi
        assert "return_rate" in kpi
        assert "gini_coefficient" in kpi
        assert "all_passed" in kpi
        assert kpi["dso"] >= 0
