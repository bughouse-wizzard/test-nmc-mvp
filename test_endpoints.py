#!/usr/bin/env python3
"""Test script to verify the Search Management APIs."""

import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_search_endpoints():
    """Test search endpoints."""
    print("Testing Search Management APIs...")
    
    # Test 1: Create a search
    print("\n1. Testing POST /api/v1/search")
    search_data = {
        "object_name": "Бумага офисная A4",
        "ktru_code": "17.12.14.110",
        "okpd2_code": "17.12.14.110",
        "customer_region": "СЗФО",
        "law": "44",
        "date_from": "2025-01-01T00:00:00",
        "date_to": "2025-12-31T23:59:59",
        "execution_statuses": ["Исполнение завершено", "Исполнение прекращено"],
        "limit_contracts": 30,
        "input_source": "MANUAL"
    }
    
    response = client.post("/api/v1/search", json=search_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        search_result = response.json()
        search_id = search_result["id"]
        print(f"   Created search with ID: {search_id}")
        print(f"   Search status: {search_result['status']}")
    else:
        print(f"   Error: {response.text}")
        return
    
    # Test 2: List searches
    print("\n2. Testing GET /api/v1/search")
    response = client.get("/api/v1/search")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        searches = response.json()
        print(f"   Found {len(searches)} searches")
    
    # Test 3: Get specific search
    print(f"\n3. Testing GET /api/v1/search/{search_id}")
    response = client.get(f"/api/v1/search/{search_id}")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        search = response.json()
        print(f"   Search status: {search['status']}")
    
    # Test 4: Get search results (empty for new search)
    print(f"\n4. Testing GET /api/v1/search/{search_id}/results")
    response = client.get(f"/api/v1/search/{search_id}/results")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        results = response.json()
        print(f"   Found {results['total']} results")
    
    # Test 5: Stop search
    print(f"\n5. Testing POST /api/v1/search/{search_id}/stop")
    response = client.post(f"/api/v1/search/{search_id}/stop")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {response.json()}")
    
    # Test 6: Verify SSE endpoint exists
    print(f"\n6. Testing SSE endpoint GET /api/v1/stream/search/{search_id}/events")
    response = client.get(f"/api/v1/stream/search/{search_id}/events")
    print(f"   Status: {response.status_code}")
    print(f"   Content-Type: {response.headers.get('content-type')}")
    
    print("\n✅ All endpoint tests completed!")

if __name__ == "__main__":
    test_search_endpoints()