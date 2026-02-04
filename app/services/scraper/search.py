"""
Zakupki.gov.ru search scraper implementation.

This module provides functionality to search for contracts on zakupki.gov.ru
based on specified criteria (44-FZ, Status=Executed, Region=SZFO, Date range, KTRU).
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
    
    # Default headers to mimic a real browser
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    
    # Region mapping for SZFO (Northwestern Federal District)
    SZFO_REGIONS = [
        "Архангельская область",
        "Вологодская область", 
        "Калининградская область",
        "Республика Карелия",
        "Республика Коми",
        "Ленинградская область",
        "Мурманская область",
        "Ненецкий автономный округ",
        "Новгородская область",
        "Псковская область",
        "г. Санкт-Петербург"
    ]
    
    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        """
        Initialize the scraper.
        
        Args:
            client: Optional httpx.AsyncClient instance
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff (seconds)
            timeout: Request timeout in seconds
        """
        self.client = client or httpx.AsyncClient(
            headers=self.DEFAULT_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    def build_search_url(
        self,
        ktru_code: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        law: str = "44",
        execution_status: str = "Исполнение завершено",
        region: str = "СЗФО",
        page: int = 1,
        page_size: int = 50,
    ) -> str:
        """
        Build search URL for zakupki.gov.ru based on parameters.
        
        Args:
            ktru_code: KTRU classification code
            date_from: Start date for search (default: 3 years ago)
            date_to: End date for search (default: today)
            law: Procurement law ("44" for 44-FZ, "223" for 223-FZ)
            execution_status: Contract execution status
            region: Region filter (default: СЗФО - Northwestern Federal District)
            page: Page number for pagination
            page_size: Number of results per page
            
        Returns:
            Complete search URL
        """
        # Set default dates if not provided
        if date_to is None:
            date_to = datetime.now()
        if date_from is None:
            date_from = date_to - timedelta(days=3*365)  # 3 years ago
            
        # Format dates for URL
        date_from_str = date_from.strftime("%d.%m.%Y")
        date_to_str = date_to.strftime("%d.%m.%Y")
        
        # Build query parameters
        params = {
            # Basic search parameters
            "searchString": ktru_code,
            "morphology": "on",
            "search-filter": date_from_str,
            "search-filter": date_to_str,
            
            # Law type (44-FZ)
            "fz44": "on" if law == "44" else "",
            "fz223": "on" if law == "223" else "",
            
            # Contract stage - executed contracts
            "contractStage": "1",  # 1 = Executed contracts
            
            # Price range (empty = any)
            "priceFrom": "",
            "priceTo": "",
            
            # Currency (RUB)
            "currencyIdGeneral": "-1",
            
            # Region filter
            "regionDeleted": "false",
            "sortBy": "UPDATE_DATE",
            "pageNumber": str(page),
            "sortDirection": "false",
            "recordsPerPage": "_" + str(page_size),
            "showLotsInfoHidden": "false",
            
            # Additional filters
            "customerPlace": "5277335",  # Russian Federation
            "customerPlaceCodes": "5277335",
        }
        
        # Add region-specific filters for SZFO
        if region == "СЗФО":
            # Add SZFO regions
            for i, region_name in enumerate(self.SZFO_REGIONS, 1):
                params[f"regions[{i}]"] = region_name
        
        # Build URL
        query_string = urlencode(params, doseq=True)
        url = urljoin(self.BASE_URL, self.SEARCH_PATH)
        return f"{url}?{query_string}"
    
    async def _make_request_with_retry(self, url: str) -> httpx.Response:
        """
        Make HTTP request with exponential backoff retry logic.
        
        Args:
            url: URL to request
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                
                # Check for rate limiting or blocking
                if response.status_code == 429:
                    wait_time = self.base_delay * (2 ** attempt)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{self.max_retries}")
                    await asyncio.sleep(wait_time)
                    continue
                    
                return response
                
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed after {self.max_retries + 1} attempts: {e}")
                    raise
                    
                wait_time = self.base_delay * (2 ** attempt)
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
    
    async def check_robots_txt(self) -> Optional[float]:
        """
        Check robots.txt for crawl delay.
        
        Returns:
            Crawl delay in seconds if specified, None otherwise
        """
        robots_url = urljoin(self.BASE_URL, "/robots.txt")
        try:
            response = await self.client.get(robots_url)
            if response.status_code == 200:
                robots_content = response.text
                for line in robots_content.split('\n'):
                    if line.lower().startswith('crawl-delay:'):
                        try:
                            return float(line.split(':')[1].strip())
                        except (ValueError, IndexError):
                            pass
        except Exception as e:
            logger.warning(f"Failed to check robots.txt: {e}")
        
        return None
    
    async def search_contracts(
        self,
        ktru_code: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        law: str = "44",
        execution_status: str = "Исполнение завершено",
        region: str = "СЗФО",
        max_pages: int = 10,
    ) -> Tuple[int, List[Dict]]:
        """
        Search for contracts on zakupki.gov.ru.
        
        Args:
            ktru_code: KTRU classification code
            date_from: Start date for search
            date_to: End date for search
            law: Procurement law
            execution_status: Contract execution status
            region: Region filter
            max_pages: Maximum number of pages to scrape
            
        Returns:
            Tuple of (total_found_count, list_of_contracts)
        """
        # Check robots.txt for crawl delay
        crawl_delay = await self.check_robots_txt()
        if crawl_delay:
            logger.info(f"Respecting robots.txt crawl delay: {crawl_delay}s")
            await asyncio.sleep(crawl_delay)
        
        contracts = []
        total_found = 0
        
        for page in range(1, max_pages + 1):
            # Build URL for current page
            url = self.build_search_url(
                ktru_code=ktru_code,
                date_from=date_from,
                date_to=date_to,
                law=law,
                execution_status=execution_status,
                region=region,
                page=page,
            )
            
            logger.info(f"Fetching page {page}: {url}")
            
            try:
                # Make request with retry logic
                response = await self._make_request_with_retry(url)
                html_content = response.text
                
                # Parse HTML
                page_contracts, page_total = self._parse_search_results(html_content)
                
                # Update total count (should be same for all pages)
                if page == 1:
                    total_found = page_total
                    logger.info(f"Total contracts found: {total_found}")
                
                # Add contracts from this page
                contracts.extend(page_contracts)
                logger.info(f"Found {len(page_contracts)} contracts on page {page}")
                
                # Stop if no more contracts or reached limit
                if not page_contracts:
                    logger.info(f"No more contracts on page {page}, stopping")
                    break
                    
                # Respect crawl delay between requests
                if crawl_delay:
                    await asyncio.sleep(crawl_delay)
                else:
                    # Default delay to be polite
                    await asyncio.sleep(1.0)
                    
            except Exception as e:
                logger.error(f"Failed to fetch page {page}: {e}")
                break
        
        return total_found, contracts
    
    def _parse_search_results(self, html_content: str) -> Tuple[List[Dict], int]:
        """
        Parse search results HTML to extract contract information.
        
        Args:
            html_content: HTML content of search results page
            
        Returns:
            Tuple of (list_of_contracts, total_found_count)
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        contracts = []
        
        # Extract total found count
        total_found = 0
        total_element = soup.find('div', class_='search-results__total')
        if total_element:
            total_text = total_element.get_text(strip=True)
            # Extract number from text like "Найдено: 1 234"
            import re
            numbers = re.findall(r'\d+', total_text.replace(' ', ''))
            if numbers:
                total_found = int(numbers[0])
        
        # Find contract blocks
        contract_blocks = soup.find_all('div', class_='search-registry-entry-block')
        
        for block in contract_blocks:
            try:
                contract_data = self._parse_contract_block(block)
                if contract_data:
                    contracts.append(contract_data)
            except Exception as e:
                logger.warning(f"Failed to parse contract block: {e}")
                continue
        
        return contracts, total_found
    
    def _parse_contract_block(self, block) -> Optional[Dict]:
        """
        Parse individual contract block.
        
        Args:
            block: BeautifulSoup element for contract block
            
        Returns:
            Dictionary with contract data or None if parsing fails
        """
        try:
            # Extract reestr number
            reestr_elem = block.find('div', class_='registry-entry__header-mid__number')
            reestr_number = ""
            if reestr_elem:
                reestr_text = reestr_elem.get_text(strip=True)
                # Extract just the number, remove "№" symbol and any extra text
                import re
                # Look for number patterns
                numbers = re.findall(r'\d+', reestr_text)
                if numbers:
                    reestr_number = numbers[0]
                    # If there are multiple numbers, join them (some numbers have format like 123/456)
                    if len(numbers) > 1:
                        reestr_number = '/'.join(numbers)
                else:
                    # Fallback to original text
                    reestr_number = reestr_text.replace('№', '').strip()
            
            # Extract contract link
            link_elem = block.find('a', class_='registry-entry__header-mid__number')
            contract_url = ""
            if link_elem and link_elem.get('href'):
                contract_url = urljoin(self.BASE_URL, link_elem['href'])
            
            # Extract date
            date_elem = block.find('div', class_='data-block__value')
            sign_date = ""
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # Try to parse date from various formats
                try:
                    # Common format: DD.MM.YYYY
                    from datetime import datetime
                    sign_date = datetime.strptime(date_text, "%d.%m.%Y").isoformat()
                except ValueError:
                    sign_date = date_text
            
            # Extract price
            price_elem = block.find('div', class_='price-block__value')
            price = 0.0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Remove non-numeric characters except dot, comma, and space
                import re
                # Remove currency symbol and text, keep numbers, spaces, commas, dots
                price_text = re.sub(r'[^\d\s,.]', '', price_text)
                # Remove spaces used as thousand separators (but be careful with decimal part)
                # Split by comma to handle decimal part separately
                if ',' in price_text:
                    parts = price_text.split(',')
                    integer_part = parts[0].replace(' ', '')
                    decimal_part = parts[1] if len(parts) > 1 else ''
                    price_text_clean = f"{integer_part}.{decimal_part}"
                else:
                    # No comma, just remove all spaces
                    price_text_clean = price_text.replace(' ', '')
                
                # Replace comma with dot if still present (fallback)
                price_text_clean = price_text_clean.replace(',', '.')
                
                try:
                    price = float(price_text_clean)
                except ValueError:
                    # Try alternative parsing if first attempt fails
                    try:
                        # Extract all numbers and join them
                        numbers = re.findall(r'\d+', price_text)
                        if numbers:
                            # Handle thousand separators: join all numbers
                            if len(numbers) > 1:
                                # Check if last part is decimal (2 digits)
                                if len(numbers[-1]) <= 2 and len(numbers) > 1:
                                    integer_part = ''.join(numbers[:-1])
                                    decimal_part = numbers[-1]
                                    price_text_clean = f"{integer_part}.{decimal_part}"
                                else:
                                    price_text_clean = ''.join(numbers)
                            else:
                                price_text_clean = numbers[0]
                            price = float(price_text_clean)
                    except (ValueError, IndexError):
                        logger.debug(f"Could not parse price from: {price_text}")
                        pass
            
            return {
                "reestr_number": reestr_number,
                "contract_url": contract_url,
                "sign_date": sign_date,
                "price": price,
                "currency": "RUB",  # Default currency
            }
            
        except Exception as e:
            logger.warning(f"Error parsing contract block: {e}")
            return None


# Convenience function for synchronous use
async def search_contracts_async(
    ktru_code: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    law: str = "44",
    execution_status: str = "Исполнение завершено",
    region: str = "СЗФО",
    max_pages: int = 10,
) -> Tuple[int, List[Dict]]:
    """
    Async convenience function to search for contracts.
    
    Args:
        ktru_code: KTRU classification code
        date_from: Start date for search
        date_to: End date for search
        law: Procurement law
        execution_status: Contract execution status
        region: Region filter
        max_pages: Maximum number of pages to scrape
        
    Returns:
        Tuple of (total_found_count, list_of_contracts)
    """
    async with ZakupkiSearchScraper() as scraper:
        return await scraper.search_contracts(
            ktru_code=ktru_code,
            date_from=date_from,
            date_to=date_to,
            law=law,
            execution_status=execution_status,
            region=region,
            max_pages=max_pages,
        )