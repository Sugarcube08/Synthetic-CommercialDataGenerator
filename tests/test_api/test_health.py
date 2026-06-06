import pytest
from httpx import AsyncClient, ASGITransport
from synth_data_creator.api.app import app

pytestmark = pytest.mark.asyncio

async def test_health_check_endpoint() -> None:
    """Verify health check returns standard keys and structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code in (200, 503)  # Might be unhealthy if db is offline
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "database" in data
        assert "uptime_seconds" in data
        assert "active_jobs" in data
