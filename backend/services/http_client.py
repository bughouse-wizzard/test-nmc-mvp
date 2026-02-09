"""
HTTP Client wrapper with retry logic and rate limiting.
Implements a singleton HttpClient using httpx.AsyncClient with:
- User-Agent header
- Retry logic using tenacity
- Rate limiting to avoid blocking
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result,
    before_sleep_log
)
from aiolimiter import AsyncLimiter

logger = logging.getLogger(__name__)


class HttpClient:
    """
    Singleton HTTP client with retry logic and rate limiting.
    """
    _instance: Optional["HttpClient"] = None
    _client: Optional[httpx.AsyncClient] = None
    _limiter: Optional[AsyncLimiter] = None
    
    # Standard browser User-Agent string
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # Rate limiting: max 1 request per 2.5 seconds (to be safe)
    REQUESTS_PER_SECOND = 0.4  # 1 request per 2.5 seconds
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HttpClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the HTTP client and rate limiter."""
        # Create rate limiter
        self._limiter = AsyncLimiter(1, 2.5)  # 1 request per 2.5 seconds
        
        # Create HTTP client with default headers
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        
        # Configure timeout settings
        timeout = httpx.Timeout(30.0, connect=10.0)
        
        # Create async client
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            max_redirects=10,
        )
        
        logger.info("HttpClient initialized with rate limiting (1 request per 2.5 seconds)")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError)
        ) | retry_if_exception_type(httpx.HTTPStatusError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Internal method to make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            **kwargs: Additional arguments for httpx request
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        # Apply rate limiting
        async with self._limiter:
            logger.debug(f"Making {method} request to {url} (attempt logged)")
            
            # Make the request
            response = await self._client.request(method, url, **kwargs)
            
            # Check for 5xx errors and raise HTTPStatusError to trigger retry
            if 500 <= response.status_code < 600:
                raise httpx.HTTPStatusError(
                    f"Server error {response.status_code}",
                    request=response.request,
                    response=response
                )
            
            # Raise for other status codes >= 400
            response.raise_for_status()
            
            return response
    
    async def get_html(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Make a GET request and return the response text.
        
        Args:
            url: Target URL
            params: Query parameters
            headers: Additional headers (will be merged with default headers)
            
        Returns:
            Response text content
            
        Raises:
            httpx.HTTPError: If request fails
        """
        # Merge headers if provided
        request_headers = {}
        if headers:
            request_headers.update(headers)
        
        try:
            response = await self._request_with_retry(
                "GET",
                url,
                params=params,
                headers=request_headers
            )
            
            # Get content with proper encoding
            content = response.text
            
            logger.debug(f"Successfully fetched {url} ({len(content)} bytes)")
            return content
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("HttpClient closed")
    
    @classmethod
    async def get_instance(cls) -> "HttpClient":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance