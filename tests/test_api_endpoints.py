"""
Test suite for FastAPI endpoints.
Tests the full lifecycle of search endpoints.
"""

import pytest
import json
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.db import get_db
from backend.models import SearchRequest, SearchStatus, ContractResult, SpecComparisonRow, MatchType, MatchStatus, InputSource


class TestSearchEndpoints:
    """Test suite for search API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_db_session(self, mocker):
        """Mock database session."""
        mock_session = mocker.Mock(spec=Session)
        mocker.patch('backend.app.api.endpoints.search.get_db', return_value=mock_session)
        return mock_session
    
    @pytest.fixture
    def sample_search_request_data(self):
        """Sample search request data for testing."""
        return {
            "object_name": "Test Procurement Object",
            "ktru_code": "1234567890",
            "okpd2_code": "12.34.56.789",
            "customer_region": "СЗФО",
            "law": "44-ФЗ",
            "date_from": "2024-01-01T00:00:00Z",
            "date_to": "2024-12-31T23:59:59Z",
            "execution_statuses": ["Исполнение завершено"],
            "limit_contracts": 30,
            "input_source": "MANUAL",
            "characteristics_text": "Test characteristics",
            "manufacturer": "Test Manufacturer"
        }
    
    @pytest.fixture
    def mock_search_request(self):
        """Create a mock search request object."""
        search_id = str(uuid4())
        return SearchRequest(
            id=search_id,
            object_name="Test Procurement Object",
            ktru_code="1234567890",
            okpd2_code="12.34.56.789",
            customer_region="СЗФО",
            law="44-ФЗ",
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 12, 31),
            execution_statuses=["Исполнение завершено"],
            limit_contracts=30,
            input_source=InputSource.MANUAL,
            status=SearchStatus.RUNNING,
            created_at=datetime.now(),
            processed_count=0
        )
    
    @pytest.fixture
    def mock_contract_result(self, mock_search_request):
        """Create a mock contract result object."""
        contract_id = str(uuid4())
        return ContractResult(
            id=contract_id,
            search_id=mock_search_request.id,
            reestr_number="123-456-789",
            contract_url="https://zakupki.gov.ru/contract/123",
            sign_date=datetime(2024, 6, 15),
            unit_price=1500.50,
            currency="RUB",
            match_type=MatchType.IDENTICAL,
            ai_score=95,
            manufacturer_target="Target Manufacturer",
            manufacturer_found="Found Manufacturer",
            manufacturer_match=True,
            is_2025_plus=False,
            accepted_for_nmc=True,
            raw_data_json={"key": "value"},
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def mock_spec_comparison(self, mock_contract_result):
        """Create a mock spec comparison object."""
        spec_id = str(uuid4())
        return SpecComparisonRow(
            id=spec_id,
            contract_result_id=mock_contract_result.id,
            name="Test Characteristic",
            target_value="Target Value",
            actual_value="Actual Value",
            match_status=MatchStatus.MATCH,
            weight=1
        )
    
    def test_create_search_endpoint(self, client, mock_db_session, sample_search_request_data):
        """Test POST /search endpoint."""
        # Mock the database session and query
        mock_search = Mock(spec=SearchRequest)
        mock_search.id = str(uuid4())
        mock_search.status = SearchStatus.RUNNING
        mock_search.created_at = datetime.now()
        mock_search.object_name = sample_search_request_data["object_name"]
        mock_search.ktru_code = sample_search_request_data["ktru_code"]
        mock_search.okpd2_code = sample_search_request_data["okpd2_code"]
        mock_search.customer_region = sample_search_request_data["customer_region"]
        mock_search.law = sample_search_request_data["law"]
        mock_search.date_from = datetime(2024, 1, 1)
        mock_search.date_to = datetime(2024, 12, 31)
        mock_search.execution_statuses = sample_search_request_data["execution_statuses"]
        mock_search.limit_contracts = sample_search_request_data["limit_contracts"]
        mock_search.input_source = InputSource.MANUAL
        mock_search.found_total = None
        mock_search.processed_count = 0
        mock_search.nmc_value = None
        mock_search.selected_contract_ids = []
        mock_search.runtime_ms = None
        mock_search.error_message = None
        
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_db_session.refresh = Mock(return_value=mock_search)
        
        # Mock the Celery task
        with patch('backend.app.api.endpoints.search.process_search.delay') as mock_process_search:
            mock_process_search.return_value = None
            
            # Mock event channel
            with patch('backend.app.api.endpoints.search.event_channel.initialize') as mock_init:
                mock_init.return_value = None
                
                # Make the request
                response = client.post("/api/search", json=sample_search_request_data)
                
                # Assertions
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == mock_search.id
                assert data["status"] == "RUNNING"
                assert data["object_name"] == sample_search_request_data["object_name"]
                assert data["ktru_code"] == sample_search_request_data["ktru_code"]
                
                # Verify database operations
                mock_db_session.add.assert_called_once()
                mock_db_session.commit.assert_called_once()
                mock_process_search.delay.assert_called_once_with(mock_search.id)
    
    def test_get_search_history_endpoint(self, client, mock_db_session, mock_search_request):
        """Test GET /search endpoint (history)."""
        # Mock the database query
        mock_db_session.query.return_value.count.return_value = 1
        mock_db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_search_request]
        
        # Make the request
        response = client.get("/api/search")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "searches" in data
        assert len(data["searches"]) == 1
        assert data["total"] == 1
        assert data["searches"][0]["id"] == mock_search_request.id
        assert data["searches"][0]["status"] == "RUNNING"
    
    def test_get_search_by_id_endpoint(self, client, mock_db_session, mock_search_request):
        """Test GET /search/{id} endpoint."""
        search_id = mock_search_request.id
        
        # Mock the database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_search_request
        
        # Make the request
        response = client.get(f"/api/search/{search_id}")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == search_id
        assert data["status"] == "RUNNING"
        assert data["object_name"] == mock_search_request.object_name
    
    def test_get_search_results_endpoint(self, client, mock_db_session, mock_search_request, mock_contract_result, mock_spec_comparison):
        """Test GET /search/{id}/results endpoint."""
        search_id = mock_search_request.id
        
        # Mock search request query
        mock_search_query = Mock()
        mock_search_query.filter.return_value.first.return_value = mock_search_request
        
        # Mock contract results query
        mock_contract_query = Mock()
        mock_contract_query.filter.return_value.count.return_value = 1
        mock_contract_query.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_contract_result]
        
        # Mock spec comparison query
        mock_spec_query = Mock()
        mock_spec_query.filter.return_value.all.return_value = [mock_spec_comparison]
        
        # Set up the mock query chain
        def query_side_effect(model):
            if model == SearchRequest:
                return mock_search_query
            elif model == ContractResult:
                return mock_contract_query
            elif model == SpecComparisonRow:
                return mock_spec_query
            return Mock()
        
        mock_db_session.query.side_effect = query_side_effect
        
        # Make the request
        response = client.get(f"/api/search/{search_id}/results")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["search_id"] == search_id
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["total"] == 1
        
        # Check that spec comparisons are included
        result = data["results"][0]
        assert "spec_comparisons" in result
        assert len(result["spec_comparisons"]) == 1
        assert result["spec_comparisons"][0]["name"] == "Test Characteristic"
    
    def test_stop_search_endpoint(self, client, mock_db_session, mock_search_request):
        """Test POST /search/{id}/stop endpoint."""
        search_id = mock_search_request.id
        
        # Mock the database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_search_request
        
        # Mock event channel
        with patch('backend.app.api.endpoints.search.event_channel.initialize') as mock_init:
            mock_init.return_value = None
            with patch('backend.app.api.endpoints.search.event_channel.publish') as mock_publish:
                mock_publish.return_value = None
                
                # Make the request
                response = client.post(f"/api/search/{search_id}/stop")
                
                # Assertions
                assert response.status_code == 200
                data = response.json()
                assert data["search_id"] == search_id
                assert data["status"] == "STOPPED"
                assert data["message"] == "Search stopped successfully"
                
                # Verify database update
                assert mock_search_request.status == SearchStatus.STOPPED
                mock_db_session.commit.assert_called_once()
    
    def test_stop_search_not_found(self, client, mock_db_session):
        """Test POST /search/{id}/stop when search not found."""
        search_id = str(uuid4())
        
        # Mock the database query to return None (not found)
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Make the request
        response = client.post(f"/api/search/{search_id}/stop")
        
        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
    
    def test_stop_search_not_running(self, client, mock_db_session, mock_search_request):
        """Test POST /search/{id}/stop when search is not running."""
        search_id = mock_search_request.id
        mock_search_request.status = SearchStatus.DONE  # Already done, not running
        
        # Mock the database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_search_request
        
        # Make the request
        response = client.post(f"/api/search/{search_id}/stop")
        
        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "not running" in data["detail"].lower()
    
    def test_get_search_report_endpoint(self, client, mock_db_session, mock_search_request):
        """Test GET /search/{id}/report endpoint."""
        search_id = mock_search_request.id
        mock_search_request.status = SearchStatus.DONE  # Report requires DONE status
        
        # Mock the database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_search_request
        
        # Mock report generator
        mock_report_bytes = b"mock excel file content"
        mock_report_generator = Mock()
        mock_report_generator.generate_search_report.return_value = mock_report_bytes
        
        with patch('backend.app.api.endpoints.search.ReportGenerator', return_value=mock_report_generator):
            # Make the request
            response = client.get(f"/api/search/{search_id}/report")
            
            # Assertions
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            assert "attachment" in response.headers["content-disposition"]
            assert search_id in response.headers["content-disposition"]
            
            # Verify report generation was called
            mock_report_generator.generate_search_report.assert_called_once_with(search_id)
    
    def test_get_search_report_not_done(self, client, mock_db_session, mock_search_request):
        """Test GET /search/{id}/report when search is not DONE."""
        search_id = mock_search_request.id
        mock_search_request.status = SearchStatus.RUNNING  # Not DONE
        
        # Mock the database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_search_request
        
        # Make the request
        response = client.get(f"/api/search/{search_id}/report")
        
        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "must be completed" in data["detail"].lower()
    
    def test_full_lifecycle(self, client, mock_db_session, sample_search_request_data):
        """Test full search lifecycle: Create -> Get List -> Stop -> Get Results."""
        # 1. Create a search
        mock_search = Mock(spec=SearchRequest)
        mock_search.id = str(uuid4())
        mock_search.status = SearchStatus.RUNNING
        mock_search.created_at = datetime.now()
        # Set all required attributes
        for key, value in sample_search_request_data.items():
            if hasattr(mock_search, key):
                setattr(mock_search, key, value)
        
        mock_db_session.add = Mock()
        mock_db_session.commit = Mock()
        mock_db_session.refresh = Mock(return_value=mock_search)
        
        with patch('backend.app.api.endpoints.search.process_search.delay') as mock_process_search:
            with patch('backend.app.api.endpoints.search.event_channel.initialize'):
                # Create search
                create_response = client.post("/api/search", json=sample_search_request_data)
                assert create_response.status_code == 200
                created_data = create_response.json()
                search_id = created_data["id"]
                
                # 2. Get search list
                mock_db_session.query.return_value.count.return_value = 1
                mock_db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_search]
                
                list_response = client.get("/api/search")
                assert list_response.status_code == 200
                list_data = list_response.json()
                assert list_data["total"] == 1
                assert list_data["searches"][0]["id"] == search_id
                
                # 3. Stop the search
                mock_db_session.query.return_value.filter.return_value.first.return_value = mock_search
                with patch('backend.app.api.endpoints.search.event_channel.publish'):
                    stop_response = client.post(f"/api/search/{search_id}/stop")
                    assert stop_response.status_code == 200
                    stop_data = stop_response.json()
                    assert stop_data["status"] == "STOPPED"
                
                # 4. Get search results (empty since no contracts)
                mock_search.status = SearchStatus.STOPPED
                mock_contract_query = Mock()
                mock_contract_query.filter.return_value.count.return_value = 0
                mock_contract_query.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
                
                def query_side_effect(model):
                    if model == SearchRequest:
                        return Mock(filter=Mock(return_value=Mock(first=Mock(return_value=mock_search))))
                    elif model == ContractResult:
                        return mock_contract_query
                    return Mock()
                
                mock_db_session.query.side_effect = query_side_effect
                
                results_response = client.get(f"/api/search/{search_id}/results")
                assert results_response.status_code == 200
                results_data = results_response.json()
                assert results_data["search_id"] == search_id
                assert results_data["total"] == 0
                assert len(results_data["results"]) == 0