from fastapi import APIRouter

from app.api.endpoints import contracts, health, search

api_router = APIRouter()

# Include routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
