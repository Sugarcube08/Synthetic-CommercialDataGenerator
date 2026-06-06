import asyncio
from datetime import date, timedelta
import time
import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from synth_data_creator.api.dependencies import get_db_engine, get_settings
from synth_data_creator.api.models.requests import GenerationRequest
from synth_data_creator.api.models.responses import GenerationAccepted, GenerationConfig
from synth_data_creator.core.config import Settings
from synth_data_creator.db.engine import create_db_engine
from synth_data_creator.generation.orchestrator import run_generation_job, jobs_status

logger = structlog.get_logger()
router = APIRouter(prefix="/generate", tags=["generation"])

@router.post("", response_model=GenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
async def generate_data(
    req: GenerationRequest,
    settings: Settings = Depends(get_settings),
) -> GenerationAccepted:
    """Trigger a new synthetic transaction data generation job."""
    
    # 1. Enforce single active job constraint
    active_jobs = [
        job_id for job_id, job in jobs_status.items()
        if job["status"] in ("accepted", "running")
    ]
    if active_jobs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "JOB_ALREADY_RUNNING",
                    "message": f"A generation job is already active: {active_jobs[0]}. Only one job can run concurrently.",
                }
            }
        )

    # 2. Determine date range
    end = req.date_range_end or date.today()
    start = req.date_range_start or (end - timedelta(days=settings.default_date_range_months * 30))

    # Validate start/end sequence again (in case defaults were used)
    if start >= end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Start date must precede end date",
                }
            }
        )

    # 3. Create job ID
    job_id = f"gen_{uuid.uuid4().hex[:8]}"
    
    # 4. Handle DB engine override
    if req.database_uri:
        job_engine = create_db_engine(str(req.database_uri))
        should_dispose = True
    else:
        job_engine = get_db_engine()
        should_dispose = False

    # 5. Initialize job status store
    jobs_status[job_id] = {
        "job_id": job_id,
        "status": "accepted",
        "phase": "init",
        "phase_progress": 0.0,
        "total_progress": 0.0,
        "records": {
            "customers": {"generated": 0, "written": 0},
            "sales": {"generated": 0, "written": 0},
            "payments": {"generated": 0, "written": 0},
            "returns": {"generated": 0, "written": 0},
        },
        "elapsed_seconds": 0.0,
        "estimated_remaining_seconds": None,
        "kpi_report": None,
        "error": None,
        "start_time": time.time(),  # Keep track of CPU time/loop time
    }

    # 6. Define background runner wrapper to ensure resources are cleaned up
    async def run_in_background() -> None:
        jobs_status[job_id]["status"] = "running"
        jobs_status[job_id]["start_time"] = time.time()
        try:
            await run_generation_job(
                job_id=job_id,
                num_customers=req.num_customers,
                start_date=start,
                end_date=end,
                seed=req.seed,
                batch_size=req.batch_size,
                engine=job_engine,
                options=req.options.model_dump(),
            )
        except Exception as e:
            logger.exception("background_task_failed", job_id=job_id)
            jobs_status[job_id]["status"] = "failed"
            jobs_status[job_id]["error"] = {
                "code": "INTERNAL_ERROR",
                "message": f"Unexpected backend failure: {str(e)}",
                "details": str(e)
            }
        finally:
            if should_dispose:
                await job_engine.dispose()

    # 7. Spawn background task
    asyncio.create_task(run_in_background())

    status_url = f"/api/v1/status/{job_id}"

    config_echo = GenerationConfig(
        num_customers=req.num_customers,
        date_range_start=start,
        date_range_end=end,
        seed=req.seed,
    )

    return GenerationAccepted(
        job_id=job_id,
        status="accepted",
        message="Generation job queued",
        config=config_echo,
        status_url=status_url,
    )
