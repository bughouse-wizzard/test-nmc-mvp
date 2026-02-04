#!/usr/bin/env python3
"""Test script to verify the API structure without database connection."""

import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_api_structure():
    """Test API structure and endpoints."""
    print("Testing API Structure...")
    
    # Get OpenAPI schema
    print("\n1. Checking OpenAPI schema")
    response = client.get("/api/v1/openapi.json")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        schema = response.json()
        print(f"   OpenAPI version: {schema.get('openapi')}")
        print(f"   Title: {schema.get('info', {}).get('title')}")
    
    # Check if search endpoints are defined
    print("\n2. Checking search endpoints in schema")
    response = client.get("/api/v1/openapi.json")
    schema = response.json()
    
    paths = schema.get("paths", {})
    search_paths = [path for path in paths.keys() if "/search" in path]
    
    print(f"   Found {len(search_paths)} search-related paths:")
    for path in sorted(search_paths):
        methods = list(paths[path].keys())
        print(f"   - {path} ({', '.join(methods)})")
    
    # Check if stream endpoints are defined
    print("\n3. Checking stream endpoints in schema")
    stream_paths = [path for path in paths.keys() if "/stream" in path]
    
    print(f"   Found {len(stream_paths)} stream-related paths:")
    for path in sorted(stream_paths):
        methods = list(paths[path].keys())
        print(f"   - {path} ({', '.join(methods)})")
    
    # Verify required endpoints exist
    required_endpoints = [
        ("POST", "/api/v1/search/"),
        ("GET", "/api/v1/search/"),
        ("GET", "/api/v1/search/{search_id}"),
        ("POST", "/api/v1/search/{search_id}/stop"),
        ("GET", "/api/v1/search/{search_id}/results"),
        ("GET", "/api/v1/stream/search/{search_id}/events"),
    ]
    
    print("\n4. Verifying required endpoints:")
    all_good = True
    for method, path in required_endpoints:
        if path in paths:
            if method.lower() in paths[path]:
                print(f"   ✓ {method} {path}")
            else:
                print(f"   ✗ {method} {path} (method not found)")
                all_good = False
        else:
            print(f"   ✗ {method} {path} (path not found)")
            all_good = False
    
    if all_good:
        print("\n✅ All required endpoints are defined in the API!")
    else:
        print("\n❌ Some endpoints are missing!")
    
    return all_good

if __name__ == "__main__":
    success = test_api_structure()
    sys.exit(0 if success else 1)