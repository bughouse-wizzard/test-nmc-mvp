"""
Zakupki.gov.ru search scraper service.

This module provides functionality to search for contracts on zakupki.gov.ru
based on specified parameters (44-FZ, Status=Executed, Region=SZFO, Date range, KTRU).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ZakupkiSearchScraper:
    """Scraper for zakupki.gov.ru search functionality."""
    
    BASE_URL = "https://zakupki.gov.ru"
    SEARCH_PATH = "/epz/order/extendedsearch/results.html"
    
    # Default search parameters
    DEFAULT_PARAMS = {
        "searchString": "",  # Will be filled with KTRU code
        "morphology": "on",
        "search-filter": "Дате+размещения",
        "pageNumber": "1",
        "sortDirection": "false",
        "recordsPerPage": "_10",
        "showLotsInfoHidden": "false",
        "sortBy": "PUBLISH_DATE",
        "fz44": "on",  # 44-FZ
        "fz223": "on",
        "af": "on",
        "ca": "on",
        "pc": "on",
        "pa": "on",
        "currencyIdGeneral": "-1",
    }
    
    # Region mapping for SZFO (Северо-Западный федеральный округ)
    REGION_CODES = {
        "СЗФО": "78000000000",  # Северо-Западный федеральный округ
    }
    
    # Execution status mapping
    EXECUTION_STATUSES = {
        "Исполнение завершено": "EXECUTED",
        "Исполнение прекращено": "TERMINATED",
    }
    
    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        base_delay: float = 2.0,
        max_retries: int = 3,
    ):
        """
        Initialize the scraper.
        
        Args:
            client: Optional httpx.AsyncClient instance
            base_delay: Base delay between requests in seconds (for robots.txt compliance)
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
            }
        )
        self.base_delay = base_delay
        self.max_retries = max_retries
        self.last_request_time = 0
        
    async def _respect_robots_delay(self):
        """Respect robots.txt delay between requests."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.base_delay:
            wait_time = self.base_delay - time_since_last
            logger.debug(f"Respecting robots.txt delay: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    async def _make_request_with_retry(self, url: str, params: Dict = None) -> httpx.Response:
        """
        Make HTTP request with retry logic and backoff.
        
        Args:
            url: URL to request
            params: Query parameters
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: If all retry attempts fail
        """
        await self._respect_robots_delay()
        
        for attempt in range(self.max_retries):
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Request failed after {self.max_retries} attempts: {e}")
                    raise
                
                backoff_time = self.base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Request attempt {attempt + 1} failed: {e}. Retrying in {backoff_time}s")
                await asyncio.sleep(backoff_time)
        
        raise httpx.HTTPError("All retry attempts failed")
    
    def build_search_url(
        self,
        ktru_code: str,
        region: str = "СЗФО",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        execution_statuses: List[str] = None,
        page: int = 1,
    ) -> str:
        """
        Build search URL for zakupki.gov.ru based on parameters.
        
        Args:
            ktru_code: KTRU code to search for
            region: Region code (default: СЗФО)
            date_from: Start date in format YYYY-MM-DD (default: 3 years ago)
            date_to: End date in format YYYY-MM-DD (default: today)
            execution_statuses: List of execution statuses
            page: Page number
            
        Returns:
            Complete search URL
        """
        # Set default dates if not provided
        if date_to is None:
            date_to = datetime.now().strftime("%Y-%m-%d")
        
        if date_from is None:
            three_years_ago = datetime.now() - timedelta(days=3*365)
            date_from = three_years_ago.strftime("%Y-%m-%d")
        
        # Default execution statuses
        if execution_statuses is None:
            execution_statuses = ["Исполнение завершено", "Исполнение прекращено"]
        
        # Build parameters
        params = self.DEFAULT_PARAMS.copy()
        
        # Set search string (KTRU code)
        params["searchString"] = ktru_code
        
        # Set region
        region_code = self.REGION_CODES.get(region, "78000000000")
        params["regions"] = region_code
        
        # Set dates
        params["publishedDateFrom"] = date_from
        params["publishedDateTo"] = date_to
        
        # Set execution statuses
        for status in execution_statuses:
            status_key = self.EXECUTION_STATUSES.get(status)
            if status_key:
                params[status_key.lower()] = "on"
        
        # Set page number
        params["pageNumber"] = str(page)
        
        # Build URL
        url = urljoin(self.BASE_URL, self.SEARCH_PATH)
        query_string = urlencode(params, doseq=True)
        
        return f"{url}?{query_string}"
    
    def parse_search_results(self, html_content: str) -> Tuple[int, List[Dict]]:
        """
        Parse search results HTML to extract total count and contract list.
        
        Args:
            html_content: HTML content of search results page
            
        Returns:
            Tuple of (total_found_count, list_of_contracts)
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract total found count
        total_found = 0
        total_element = soup.find('div', class_='search-results__total')
        if total_element:
            total_text = total_element.get_text(strip=True)
            # Extract number from text like "Найдено: 1234"
            import re
            match = re.search(r'(\d+)', total_text.replace(',', '').replace(' ', ''))
            if match:
                total_found = int(match.group(1))
        
        # Extract contract list
        contracts = []
        contract_elements = soup.find_all('div', class_='search-registry-entry-block')
        
        for element in contract_elements:
            contract = self._parse_contract_element(element)
            if contract:
                contracts.append(contract)
        
        return total_found, contracts
    
    def _parse_contract_element(self, element) -> Optional[Dict]:
        """Parse individual contract element from search results."""
        try:
            # Extract reestr number
            reestr_elem = element.find('div', class_='registry-entry__header-mid__number')
            reestr_number = reestr_elem.get_text(strip=True) if reestr_elem else None
            
            # Extract link
            link_elem = element.find('a', class_='registry-entry__header-mid__number')
            link = urljoin(self.BASE_URL, link_elem['href']) if link_elem else None
            
            # Extract date
            date_elem = element.find('div', class_='data-block__value')
            date_str = date_elem.get_text(strip=True) if date_elem else None
            
            # Extract price
            price_elem = element.find('div', class_='price-block__value')
            price_text = price_elem.get_text(strip=True) if price_elem else None
            
            # Parse price string (e.g., "1 234 567,89 руб.")
            price = None
            if price_text:
                # Remove currency and spaces, replace comma with dot
                price_clean = price_text.replace('руб.', '').replace(' ', '').replace(',', '.')
                try:
                    price = float(price_clean)
                except ValueError:
                    pass
            
            if not all([reestr_number, link, date_str]):
                return None
            
            return {
                'reestr_number': reestr_number,
                'link': link,
                'date': date_str,
                'price': price,
                'currency': 'RUB' if price_text and 'руб.' in price_text else None,
            }
        except Exception as e:
            logger.warning(f"Failed to parse contract element: {e}")
            return None
    
    async def search_contracts(
        self,
        ktru_code: str,
        region: str = "СЗФО",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        execution_statuses: List[str] = None,
        max_pages: int = 1,
    ) -> Tuple[int, List[Dict]]:
        """
        Search for contracts with given parameters.
        
        Args:
            ktru_code: KTRU code to search for
            region: Region code
            date_from: Start date
            date_to: End date
            execution_statuses: List of execution statuses
            max_pages: Maximum number of pages to fetch
            
        Returns:
            Tuple of (total_found_count, list_of_contracts)
        """
        all_contracts = []
        total_found = 0
        
        for page in range(1, max_pages + 1):
            try:
                # Build URL for current page
                url = self.build_search_url(
                    ktru_code=ktru_code,
                    region=region,
                    date_from=date_from,
                    date_to=date_to,
                    execution_statuses=execution_statuses,
                    page=page,
                )
                
                logger.info(f"Fetching page {page}: {url}")
                
                # Make request
                response = await self._make_request_with_retry(url)
                
                # Parse results
                page_total, page_contracts = self.parse_search_results(response.text)
                
                # Set total found from first page
                if page == 1:
                    total_found = page_total
                
                # Add contracts from this page
                all_contracts.extend(page_contracts)
                
                # Stop if no more contracts or reached total
                if not page_contracts or len(all_contracts) >= total_found:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                if page == 1:
                    raise
                break
        
        return total_found, all_contracts
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Async context manager support
async def create_scraper(**kwargs) -> ZakupkiSearchScraper:
    """Create a scraper instance."""
    return ZakupkiSearchScraper(**kwargs)