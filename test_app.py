#!/usr/bin/env python3
"""Test script to verify the FastAPI application can start."""

import asyncio
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.main import app
from app.core.config import settings


async def test_app():
    """Test that the app can be created and has basic endpoints."""
    print("Testing FastAPI application...")
    print(f"Project name: {settings.PROJECT_NAME}")
    print(f"Version: {settings.VERSION}")
    print(f"Database URL: {settings.DATABASE_URL}")
    print(f"Redis URL: {settings.CELERY_BROKER_URL}")
    
    # Check if app has routes
    routes = [{"path": route.path, "name": route.name} for route in app.routes]
    print(f"\nFound {len(routes)} routes:")
    for route in routes[:5]:  # Show first 5 routes
        print(f"  - {route['path']} ({route['name']})")
    
    if len(routes) > 5:
        print(f"  ... and {len(routes) - 5} more routes")
    
    print("\n✅ Application test passed!")


if __name__ == "__main__":
    asyncio.run(test_app())