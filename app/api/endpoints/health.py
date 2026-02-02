from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/health")
async def health_alt():
    """Alternative health check endpoint for compatibility."""
    return {"status": "healthy"}
