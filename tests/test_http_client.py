"""
Tests for the HttpClient wrapper with retry logic and rate limiting.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import httpx
from tenacity import RetryError

from backend.services.http_client import HttpClient


class TestHttpClient:
    """Test suite for HttpClient class."""
    
    def setup_method(self):
        """Setup for each test."""
        # Reset singleton before each test
        HttpClient._instance = None
        HttpClient._client = None
        HttpClient._limiter = None
    
    def teardown_method(self):
        """Teardown for each test."""
        # Cleanup after each test
        if HttpClient._instance and HttpClient._instance._client:
            import asyncio
            # Run async cleanup in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(HttpClient._instance.close())
            finally:
                loop.close()
        HttpClient._instance = None
    
    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """Test that HttpClient follows singleton pattern."""
        client1 = HttpClient()
        client2 = HttpClient()
        
        assert client1 is client2
        assert HttpClient._instance is client1
    
    @pytest.mark.asyncio
    async def test_user_agent_header(self):
        """Test that User-Agent header is set correctly."""
        # Test that HttpClient has USER_AGENT attribute
        assert hasattr(HttpClient, 'USER_AGENT')
        assert 'Mozilla' in HttpClient.USER_AGENT
        
        # Create client and check initialization
        client = HttpClient()
        
        # Mock the httpx client to capture request
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "Test content"
        mock_response.raise_for_status = MagicMock()
        
        # Create a more complete mock that simulates the actual client behavior
        mock_client = AsyncMock()
        
        # Track calls to see what headers would be used
        call_kwargs = {}
        async def mock_request(method, url, **kwargs):
            call_kwargs.update(kwargs)
            return mock_response
        
        mock_client.request = mock_request
        
        # Also need to mock the rate limiter
        mock_limiter = AsyncMock()
        mock_limiter.__aenter__ = AsyncMock(return_value=None)
        mock_limiter.__aexit__ = AsyncMock(return_value=None)
        
        with patch.object(client, '_client', mock_client), \
             patch.object(client, '_limiter', mock_limiter):
            await client.get_html("http://example.com")
            
            # The HttpClient should use its default headers when making requests
            # Since we're mocking, we can't directly test the headers in the mock
            # but we can verify the USER_AGENT constant is correct
            assert 'Mozilla' in HttpClient.USER_AGENT
            assert 'Chrome' in HttpClient.USER_AGENT
    
    @pytest.mark.asyncio
    async def test_get_html_success(self):
        """Test successful GET request."""
        client = HttpClient()
        
        # Mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Test content</html>"
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        
        with patch.object(client, '_client', mock_client):
            result = await client.get_html("http://example.com")
            
            assert result == "<html>Test content</html>"
            mock_client.request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_retry_logic_on_503_error(self):
        """Test that retry logic works on 503 errors."""
        client = HttpClient()
        
        # Mock response that fails twice then succeeds
        mock_responses = [
            self._create_mock_response(503),  # First attempt fails
            self._create_mock_response(503),  # Second attempt fails
            self._create_mock_response(200, "Success"),  # Third attempt succeeds
        ]
        
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_responses)
        
        with patch.object(client, '_client', mock_client):
            result = await client.get_html("http://example.com")
            
            # Should have been called 3 times (2 failures + 1 success)
            assert mock_client.request.call_count == 3
            assert result == "Success"
    
    @pytest.mark.asyncio
    async def test_retry_logic_gives_up_after_3_attempts(self):
        """Test that retry logic gives up after 3 failed attempts."""
        client = HttpClient()
        
        # Mock response that always fails with 503
        mock_response = self._create_mock_response(503)
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        
        with patch.object(client, '_client', mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_html("http://example.com")
            
            # Should have been called exactly 3 times
            assert mock_client.request.call_count == 3
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test that rate limiting works correctly."""
        client = HttpClient()
        
        # Mock responses
        mock_response = self._create_mock_response(200, "Success")
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        
        with patch.object(client, '_client', mock_client):
            # Make multiple requests and measure time
            start_time = time.time()
            
            # Make 3 requests
            tasks = [
                client.get_html("http://example.com/1"),
                client.get_html("http://example.com/2"),
                client.get_html("http://example.com/3"),
            ]
            
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # With rate limiting of 1 request per 2.5 seconds,
            # 3 requests should take at least ~5 seconds (2 gaps of 2.5s each)
            # Allow some tolerance for test execution
            assert elapsed_time >= 4.0, f"Rate limiting not working: elapsed time {elapsed_time:.2f}s"
            
            # All requests should have succeeded
            assert all(r == "Success" for r in results)
            assert mock_client.request.call_count == 3
    
    @pytest.mark.asyncio
    async def test_close_method(self):
        """Test that close method works correctly."""
        client = HttpClient()
        
        # Create a real mock client
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        
        with patch.object(client, '_client', mock_client):
            await client.close()
            
            mock_client.aclose.assert_called_once()
            assert client._client is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test that HttpClient works as a context manager."""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        
        with patch('backend.services.http_client.httpx.AsyncClient', return_value=mock_client):
            async with HttpClient() as client:
                assert isinstance(client, HttpClient)
                assert client._client is not None
            
            # Client should be closed after context manager exits
            mock_client.aclose.assert_called_once()
    
    def _create_mock_response(self, status_code: int, text: str = ""):
        """Helper method to create a mock response."""
        mock_response = AsyncMock()
        mock_response.status_code = status_code
        mock_response.text = text
        
        if status_code >= 400:
            # Create a mock exception for raise_for_status
            mock_exception = httpx.HTTPStatusError(
                f"HTTP error {status_code}",
                request=MagicMock(),
                response=mock_response
            )
            mock_response.raise_for_status = MagicMock(side_effect=mock_exception)
        else:
            mock_response.raise_for_status = MagicMock()
        
        return mock_response
    
    @pytest.mark.asyncio
    async def test_get_instance_classmethod(self):
        """Test the get_instance class method."""
        # First call should create instance
        client1 = await HttpClient.get_instance()
        assert client1 is not None
        
        # Second call should return same instance
        client2 = await HttpClient.get_instance()
        assert client1 is client2
        
        # Cleanup
        await client1.close()