"""
Tests for search API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, date
from uuid import uuid4
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import app
from models import SearchStatus, InputSource

client = TestClient(app)


def test_create_search():
    """Test POST /api/search endpoint."""
    search_data = {
        "object_name": "Test Object",
        "ktru_code": "123456",
        "okpd2_code": "987654",
        "customer_region": "СЗФО",
        "law": "44-ФЗ",
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "execution_statuses": ["Исполнение завершено", "Исполнение прекращено"],
        "limit_contracts": 30,
        "input_source": "MANUAL"
    }
    
    response = client.post("/api/search", json=search_data)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "id" in data
    assert data["status"] == "RUNNING"
    assert data["object_name"] == "Test Object"
    assert data["ktru_code"] == "123456"
    assert data["okpd2_code"] == "987654"
    assert data["customer_region"] == "СЗФО"
    assert data["law"] == "44-ФЗ"
    assert data["input_source"] == "MANUAL"
    assert data["limit_contracts"] == 30
    assert data["processed_count"] == 0
    assert data["found_total"] is None or isinstance(data["found_total"], int)
    assert data["nmc_value"] is None or isinstance(data["nmc_value"], (int, float))
    
    return data["id"]


def test_get_search():
    """Test GET /api/search/{id} endpoint."""
    # First create a search
    search_data = {
        "object_name": "Test Object 2",
        "ktru_code": "654321",
        "customer_region": "СЗФО",
        "law": "44-ФЗ",
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "execution_statuses": ["Исполнение завершено"],
        "limit_contracts": 20,
        "input_source": "MANUAL"
    }
    
    create_response = client.post("/api/search", json=search_data)
    assert create_response.status_code == 200
    search_id = create_response.json()["id"]
    
    # Now get the search
    response = client.get(f"/api/search/{search_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == search_id
    assert data["status"] == "RUNNING"
    assert data["object_name"] == "Test Object 2"
    assert data["ktru_code"] == "654321"
    assert data["customer_region"] == "СЗФО"
    assert data["limit_contracts"] == 20


def test_get_nonexistent_search():
    """Test GET /api/search/{id} with non-existent ID."""
    non_existent_id = str(uuid4())
    response = client.get(f"/api/search/{non_existent_id}")
    
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()


def test_get_search_history():
    """Test GET /api/search/history endpoint."""
    response = client.get("/api/search/history")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "searches" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert isinstance(data["searches"], list)
    assert isinstance(data["total"], int)
    assert isinstance(data["page"], int)
    assert isinstance(data["limit"], int)


def test_get_search_history_with_filters():
    """Test GET /api/search/history with filters."""
    # Test with status filter
    response = client.get("/api/search/history?status=RUNNING")
    assert response.status_code == 200
    
    # Test with date filters
    response = client.get("/api/search/history?date_from=2024-01-01&date_to=2024-12-31")
    assert response.status_code == 200
    
    # Test with pagination
    response = client.get("/api/search/history?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10


def test_stop_search():
    """Test POST /api/search/{id}/stop endpoint."""
    # First create a search
    search_data = {
        "object_name": "Test Object to Stop",
        "ktru_code": "999999",
        "customer_region": "СЗФО",
        "law": "44-ФЗ",
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "execution_statuses": ["Исполнение завершено"],
        "limit_contracts": 10,
        "input_source": "MANUAL"
    }
    
    create_response = client.post("/api/search", json=search_data)
    assert create_response.status_code == 200
    search_id = create_response.json()["id"]
    
    # Stop the search
    response = client.post(f"/api/search/{search_id}/stop")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["message"] == f"Search {search_id} stopped successfully"
    assert data["search_id"] == search_id
    assert data["status"] == "STOPPED"


def test_stop_nonexistent_search():
    """Test POST /api/search/{id}/stop with non-existent ID."""
    non_existent_id = str(uuid4())
    response = client.post(f"/api/search/{non_existent_id}/stop")
    
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()


def test_get_search_results():
    """Test GET /api/search/{id}/results endpoint."""
    # First create a search
    search_data = {
        "object_name": "Test Object for Results",
        "ktru_code": "777777",
        "customer_region": "СЗФО",
        "law": "44-ФЗ",
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "execution_statuses": ["Исполнение завершено"],
        "limit_contracts": 5,
        "input_source": "MANUAL"
    }
    
    create_response = client.post("/api/search", json=search_data)
    assert create_response.status_code == 200
    search_id = create_response.json()["id"]
    
    # Get results (should be empty since no contracts processed yet)
    response = client.get(f"/api/search/{search_id}/results")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert data["search_id"] == search_id
    assert "results" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert isinstance(data["results"], list)
    assert isinstance(data["total"], int)
    assert data["total"] >= 0


def test_get_search_results_with_pagination():
    """Test GET /api/search/{id}/results with pagination."""
    # First create a search
    search_data = {
        "object_name": "Test Object Pagination",
        "ktru_code": "888888",
        "customer_region": "СЗФО",
        "law": "44-ФЗ",
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "execution_statuses": ["Исполнение завершено"],
        "limit_contracts": 5,
        "input_source": "MANUAL"
    }
    
    create_response = client.post("/api/search", json=search_data)
    assert create_response.status_code == 200
    search_id = create_response.json()["id"]
    
    # Get results with pagination
    response = client.get(f"/api/search/{search_id}/results?skip=0&limit=5")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["limit"] == 5
    assert data["page"] == 1


def test_invalid_search_request():
    """Test POST /api/search with invalid data."""
    # Test with missing required field
    invalid_data = {
        "ktru_code": "123456",
        "customer_region": "СЗФО",
        # Missing object_name
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "execution_statuses": ["Исполнение завершено"],
        "limit_contracts": 30,
        "input_source": "MANUAL"
    }
    
    response = client.post("/api/search", json=invalid_data)
    assert response.status_code == 422  # Validation error
    
    # Test with invalid date range (date_to before date_from)
    invalid_dates = {
        "object_name": "Test Object",
        "ktru_code": "123456",
        "customer_region": "СЗФО",
        "law": "44-ФЗ",
        "date_from": "2024-12-31",
        "date_to": "2024-01-01",  # Invalid: before date_from
        "execution_statuses": ["Исполнение завершено"],
        "limit_contracts": 30,
        "input_source": "MANUAL"
    }
    
    response = client.post("/api/search", json=invalid_dates)
    assert response.status_code == 422  # Validation error