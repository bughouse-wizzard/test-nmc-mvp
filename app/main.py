import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import api_router
from app.core.config import settings
from app.core.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("Starting up...")
    await init_db()
    yield
    # Shutdown
    print("Shutting down...")


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Set up CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files (from incoming branch)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_application()


@app.get("/")
async def root():
    """Root endpoint - serve index.html for frontend."""
    # Serve the main HTML file (from incoming branch)
    return FileResponse("index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": "2026-02-02T10:30:00Z"}


@app.get("/api/search")
async def get_searches():
    """Mock endpoint for getting search history (from incoming branch)."""
    return {
        "searches": [
            {
                "id": 101,
                "date": "2026-01-21",
                "name": "Бумага офисная A4",
                "ktru": "17.12.14.110",
                "status": "Завершен",
                "found": 45,
                "avg": 420.50,
            },
            {
                "id": 102,
                "date": "2026-01-20",
                "name": "АРМ (Компьютеры)",
                "ktru": "26.20.15.000",
                "status": "Завершен",
                "found": 15,
                "avg": 54400.00,
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
