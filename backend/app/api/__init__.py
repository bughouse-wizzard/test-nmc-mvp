"""
API routers module.
"""
from fastapi import APIRouter

from .endpoints import search, contracts, health, stream

router = APIRouter()

# Include all endpoint routers
router.include_router(health.router, tags=["health"])
router.include_router(search.router, prefix="/search", tags=["search"])
router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
# Stream endpoints are included under /search prefix
router.include_router(stream.router, prefix="/search", tags=["stream"])