"""
FastAPI main application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api import router as api_router
from .core.config import settings
from .core.event_channel import event_channel


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    print("Initializing event channel...")
    await event_channel.initialize()
    
    yield
    
    # Shutdown
    print("Closing event channel...")
    await event_channel.close()


app = FastAPI(
    title="NMCK Calculation System API",
    description="API for automated NMCK calculation based on government procurement contracts",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api")

# Mount static files for frontend
# Note: This path assumes the backend is running from the project root
# In production, this would be handled by nginx
try:
    app.mount("/static", StaticFiles(directory="../../frontend"), name="static")
except RuntimeError:
    # If the path doesn't exist, don't mount it
    pass

@app.get("/")
async def root():
    """Root endpoint serving the frontend application."""
    return FileResponse("../../app/templates/front13.html")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "nmck-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )