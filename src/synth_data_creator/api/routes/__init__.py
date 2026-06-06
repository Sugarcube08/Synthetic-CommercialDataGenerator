from .generation import router as generation_router
from .status import router as status_router
from .health import router as health_router

__all__ = [
    "generation_router",
    "status_router",
    "health_router",
]
