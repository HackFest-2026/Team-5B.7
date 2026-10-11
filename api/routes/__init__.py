"""Routes package."""
from .domains import router as domains_router
from .pricing import router as pricing_router
from .copilot import router as copilot_router
from .context import router as context_router
from .store import router as store_router
from .analytics import router as analytics_router

__all__ = [
    "domains_router",
    "pricing_router",
    "copilot_router",
    "context_router",
    "store_router",
    "analytics_router",
]
