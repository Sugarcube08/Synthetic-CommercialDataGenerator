import time
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from synth_data_creator.api.dependencies import get_db_engine
from synth_data_creator.api.models.responses import HealthResponse
from synth_data_creator.generation.orchestrator import jobs_status

logger = structlog.get_logger()
router = APIRouter(tags=["health"])

START_TIME = time.time()

@router.get("/health", response_model=HealthResponse)
async def check_health(engine: AsyncEngine = Depends(get_db_engine)) -> HealthResponse:
    """Liveness and readiness probe for the service."""
    uptime = time.time() - START_TIME
    
    # Count active jobs in memory
    active_jobs = sum(
        1 for job in jobs_status.values() if job.get("status") in ("accepted", "running")
    )

    db_status = "disconnected"
    db_error = None
    
    try:
        # Quick db ping
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        db_error = f"Database connection failed: {str(e)}"

    if db_status == "disconnected":
        return HealthResponse(
            status="unhealthy",
            version="0.1.0",
            database=db_status,
            uptime_seconds=round(uptime, 1),
            active_jobs=active_jobs,
            error=db_error,
        )

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        database=db_status,
        uptime_seconds=round(uptime, 1),
        active_jobs=active_jobs,
    )
