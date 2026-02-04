from fastapi import APIRouter

from app.api.endpoints import search, contracts, health, stream

api_router = APIRouter()

# Include routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(contracts.router, prefix="/contracts", tags=["contracts"])
api_router.include_router(stream.router, prefix="/stream", tags=["stream"])