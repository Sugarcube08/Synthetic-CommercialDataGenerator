import time
from fastapi import APIRouter, HTTPException, status
from synth_data_creator.api.models.responses import StatusResponse
from synth_data_creator.generation.orchestrator import jobs_status

router = APIRouter(prefix="/status", tags=["generation"])

@router.get("/{job_id}", response_model=StatusResponse)
async def get_job_status(job_id: str) -> StatusResponse:
    """Poll the status of a specific data generation job."""
    job = jobs_status.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Job with ID '{job_id}' not found.",
                }
            }
        )

    # Calculate current elapsed time if still running
    if job["status"] in ("accepted", "running"):
        job["elapsed_seconds"] = round(time.time() - job["start_time"], 1)

        # Estimate remaining time if we have progress
        progress = job["total_progress"]
        if progress > 0.05:  # Require some minimal progress to avoid wildly inaccurate estimates
            elapsed = job["elapsed_seconds"]
            total_est = elapsed / progress
            job["estimated_remaining_seconds"] = round(max(0.0, total_est - elapsed), 1)
        else:
            job["estimated_remaining_seconds"] = None

    return StatusResponse(**job)
