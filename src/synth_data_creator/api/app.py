from contextlib import asynccontextmanager
from typing import AsyncGenerator
import structlog
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from synth_data_creator.api.dependencies import get_db_engine, get_settings
from synth_data_creator.api.routes import generation_router, health_router, status_router
from synth_data_creator.core.exceptions import SynthDataError
from synth_data_creator.core.logging import configure_logging

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events."""
    settings = get_settings()
    # 1. Configure logging
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("service_starting", port=settings.api_port, host=settings.api_host)
    
    # 2. Warm up db pool
    get_db_engine()
    
    yield
    
    # 3. Clean up connections
    logger.info("service_stopping")
    engine = get_db_engine()
    await engine.dispose()
    logger.info("service_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="Synthetic Commercial Data Generation Microservice",
        version="0.1.0",
        description="Generates behaviorally consistent, statistically realistic B2B commercial transaction data.",
        lifespan=lifespan,
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(generation_router, prefix="/api/v1")
    app.include_router(status_router, prefix="/api/v1")

    # Custom exception handler for HTTPException to match API spec format
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            content = exc.detail
        else:
            content = {
                "error": {
                    "code": "ERROR",
                    "message": str(exc.detail),
                }
            }
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )

    # Custom exception handler for validation errors to match API spec format
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.error("api_validation_error", errors=exc.errors())
        # Format validation error detail
        details = {}
        for err in exc.errors():
            loc = " -> ".join(str(part) for part in err["loc"][1:]) if len(err["loc"]) > 1 else str(err["loc"][0])
            details[loc] = err["msg"]

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed. Check request payload format.",
                    "details": details,
                }
            },
        )

    # Custom exception handler for application specific errors
    @app.exception_handler(SynthDataError)
    async def synth_data_exception_handler(request: Request, exc: SynthDataError) -> JSONResponse:
        logger.error("api_execution_error", error=str(exc))
        
        # Map exception classes to codes and statuses
        error_name = exc.__class__.__name__
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        if error_name == "JobNotFoundError":
            status_code = status.HTTP_404_NOT_FOUND
            code = "JOB_NOT_FOUND"
        elif error_name == "JobAlreadyRunningError":
            status_code = status.HTTP_409_CONFLICT
            code = "JOB_ALREADY_RUNNING"
        elif error_name == "ConfigurationError":
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            code = "VALIDATION_ERROR"
        elif error_name == "SchemaInitError":
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            code = "SCHEMA_INIT_FAILED"
        elif error_name == "SchemaVerificationError":
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            code = "SCHEMA_INIT_FAILED"
        else:
            code = "INTERNAL_ERROR"
            
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": str(exc),
                }
            },
        )

    # Catch-all exception handler for generic unhandled exceptions
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("api_unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected server error occurred.",
                    "details": str(exc),
                }
            },
        )

    return app

# Main app instance
app = create_app()
