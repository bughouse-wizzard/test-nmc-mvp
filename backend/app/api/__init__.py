"""
API routers module.
"""
from fastapi import APIRouter

from .endpoints import search, contracts, health

router = APIRouter()

# Include all endpoint routers
router.include_router(health.router, tags=["health"])
router.include_router(search.router, prefix="/search", tags=["search"])
router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])