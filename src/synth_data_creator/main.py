import uvicorn
from synth_data_creator.api.dependencies import get_settings

def main() -> None:
    """Start the FastAPI application via uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "synth_data_creator.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        workers=settings.api_workers,
    )


if __name__ == "__main__":
    main()
