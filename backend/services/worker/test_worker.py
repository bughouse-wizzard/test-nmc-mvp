"""
Test for the search worker implementation.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from backend.services.worker.search_worker import SearchWorker, WorkerContext
from backend.models import SearchRequest, SearchStatus, InputSource


class TestSearchWorker:
    """Test cases for SearchWorker."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.db_session_factory = Mock()
        self.db_session = Mock()
        self.db_session_factory.return_value = self.db_session
        
        self.redis_client = Mock()
        self.search_worker = SearchWorker(
            db_session_factory=self.db_session_factory,
            redis_client=self.redis_client
        )
        
        # Mock services
        self.search_worker.search_parser = Mock()
        self.search_worker.contract_parser = Mock()
        self.search_worker.ai_client = Mock()
        self.search_worker.matcher_engine = Mock()
    
    def test_check_stop_signal_stop(self):
        """Test checking STOP signal when STOP is present."""
        self.redis_client.get.return_value = b"STOP"
        
        result = self.search_worker._check_stop_signal(self.redis_client, "test_key")
        
        assert result is True
        self.redis_client.get.assert_called_once_with("test_key")
    
    def test_check_stop_signal_no_stop(self):
        """Test checking STOP signal when STOP is not present."""
        self.redis_client.get.return_value = b"RUNNING"
        
        result = self.search_worker._check_stop_signal(self.redis_client, "test_key")
        
        assert result is False
    
    def test_check_stop_signal_error(self):
        """Test checking STOP signal when Redis error occurs."""
        self.redis_client.get.side_effect = Exception("Redis error")
        
        result = self.search_worker._check_stop_signal(self.redis_client, "test_key")
        
        assert result is False
    
    def test_publish_progress(self):
        """Test publishing progress via Redis PubSub."""
        progress_data = {"status": "RUNNING", "progress": 50}
        
        self.search_worker._publish_progress(
            self.redis_client,
            "test_channel",
            "test_search_id",
            progress_data
        )
        
        self.redis_client.publish.assert_called_once()
        call_args = self.redis_client.publish.call_args
        assert call_args[0][0] == "test_channel"
        published_data = call_args[0][1]
        assert "test_search_id" in published_data
        assert "progress" in published_data
    
    @pytest.mark.asyncio
    async def test_execute_search_engine(self):
        """Test executing search engine."""
        # Create mock search request
        search_request = Mock()
        search_request.ktru_code = "123456"
        search_request.customer_region = "СЗФО"
        search_request.law = "44-ФЗ"
        search_request.date_from = datetime.now() - timedelta(days=30)
        search_request.date_to = datetime.now()
        search_request.execution_statuses = ["Исполнение завершено"]
        search_request.limit_contracts = 30
        
        # Create worker context
        context = WorkerContext(
            search_id="test_id",
            db_session=self.db_session,
            redis_client=self.redis_client,
            search_parser=self.search_worker.search_parser,
            contract_parser=self.search_worker.contract_parser,
            ai_client=self.search_worker.ai_client,
            matcher_engine=self.search_worker.matcher_engine,
            stop_key="test_stop",
            progress_channel="test_progress"
        )
        
        # Mock search parser
        self.search_worker.search_parser.build_search_url.return_value = "http://test.url"
        
        # Execute search engine
        contracts = await self.search_worker._execute_search_engine(context, search_request)
        
        # Verify results
        assert isinstance(contracts, list)
        assert len(contracts) <= 10  # Mock returns max 10 contracts
        self.search_worker.search_parser.build_search_url.assert_called_once()
    
    def test_compare_manufacturers_match(self):
        """Test comparing manufacturers when they match."""
        result = self.search_worker._compare_manufacturers("Company A", "Company A")
        
        assert result is True
    
    def test_compare_manufacturers_no_match(self):
        """Test comparing manufacturers when they don't match."""
        result = self.search_worker._compare_manufacturers("Company A", "Company B")
        
        assert result is False
    
    def test_compare_manufacturers_case_insensitive(self):
        """Test comparing manufacturers with different cases."""
        result = self.search_worker._compare_manufacturers("COMPANY A", "company a")
        
        assert result is True
    
    def test_compare_manufacturers_none_target(self):
        """Test comparing manufacturers when target is None."""
        result = self.search_worker._compare_manufacturers(None, "Company A")
        
        assert result is None
    
    def test_compare_manufacturers_none_actual(self):
        """Test comparing manufacturers when actual is None."""
        result = self.search_worker._compare_manufacturers("Company A", None)
        
        assert result is None
    
    def test_compare_manufacturers_both_none(self):
        """Test comparing manufacturers when both are None."""
        result = self.search_worker._compare_manufacturers(None, None)
        
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])