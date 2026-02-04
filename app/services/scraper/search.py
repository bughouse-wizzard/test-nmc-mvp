"""
Zakupki.gov.ru search scraper implementation.

This module provides functionality to search for contracts on zakupki.gov.ru
based on various parameters including law type, region, date range, and KTRU codes.
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
    """Scraper for searching contracts on zakupki.gov.ru."""
    
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
    REGION_MAPPING = {
        "СЗФО": {
            "regions": [
                "78000000000",  # Санкт-Петербург
                "47000000000",  # Ленинградская область
                "29000000000",  # Архангельская область
                "83000000000",  # Ненецкий автономный округ
                "35000000000",  # Вологодская область
                "39000000000",  # Калининградская область
                "51000000000",  # Мурманская область
                "53000000000",  # Новгородская область
                "60000000000",  # Псковская область
                "86000000000",  # Республика Карелия
                "87000000000",  # Республика Коми
            ]
        }
    }
    
    # Execution status mapping
    EXECUTION_STATUS_MAPPING = {
        "Исполнение завершено": "EXECUTED",
        "Исполнение прекращено": "TERMINATED",
    }
    
    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        respect_robots_delay: bool = True,
    ):
        """
        Initialize the scraper.
        
        Args:
            client: Optional httpx.AsyncClient instance
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            respect_robots_delay: Whether to respect robots.txt delay (default: 1 second)
        """
        self.client = client or httpx.AsyncClient(
            headers=self.DEFAULT_HEADERS,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.respect_robots_delay = respect_robots_delay
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        
    def build_search_url(
        self,
        ktru_code: str,
        date_from: datetime,
        date_to: datetime,
        law: str = "44",
        customer_region: str = "СЗФО",
        execution_statuses: List[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> str:
        """
        Build search URL for zakupki.gov.ru based on parameters.
        
        Args:
            ktru_code: KTRU classification code
            date_from: Start date for search
            date_to: End date for search
            law: Law type (default: "44" for 44-FZ)
            customer_region: Customer region (default: "СЗФО")
            execution_statuses: List of execution statuses
            page: Page number (default: 1)
            page_size: Results per page (default: 50)
            
        Returns:
            Complete search URL
        """
        if execution_statuses is None:
            execution_statuses = ["Исполнение завершено", "Исполнение прекращено"]
            
        # Convert dates to string format expected by zakupki.gov.ru
        date_from_str = date_from.strftime("%d.%m.%Y")
        date_to_str = date_to.strftime("%d.%m.%Y")
        
        # Build query parameters
        params = {
            "searchString": ktru_code,
            "morphology": "on",
            "searchFilter": "",
            "sortBy": "UPDATE_DATE",
            "sortDirection": "false",
            "pageNumber": page,
            "recordsPerPage": "_" + str(page_size),
            "showLotsInfoHidden": "false",
            "fz44": "on" if law == "44" else "off",
            "fz223": "on" if law == "223" else "off",
            "af": "on",  # Advanced search
            "ca": "on",  # Contract awards
            "pc": "on",  # Price contracts
            "pa": "on",  # Price agreements
            "currencyId": "-1",
            "publishDateFrom": date_from_str,
            "publishDateTo": date_to_str,
            "applSubmissionCloseDateFrom": "",
            "applSubmissionCloseDateTo": "",
            "priceFrom": "",
            "priceTo": "",
        }
        
        # Add region filters for SZFO
        if customer_region in self.REGION_MAPPING:
            for i, region_code in enumerate(self.REGION_MAPPING[customer_region]["regions"], 1):
                params[f"regions[{i}]"] = region_code
                
        # Add execution status filters
        for i, status in enumerate(execution_statuses, 1):
            if status in self.EXECUTION_STATUS_MAPPING:
                params[f"executionStatus[{i}]"] = self.EXECUTION_STATUS_MAPPING[status]
                
        # Build URL
        query_string = urlencode(params, doseq=True)
        url = urljoin(self.BASE_URL, self.SEARCH_PATH)
        return f"{url}?{query_string}"
        
    async def search_contracts(
        self,
        ktru_code: str,
        date_from: datetime,
        date_to: datetime,
        law: str = "44",
        customer_region: str = "СЗФО",
        execution_statuses: List[str] = None,
        max_pages: int = 10,
    ) -> Dict:
        """
        Search for contracts on zakupki.gov.ru.
        
        Args:
            ktru_code: KTRU classification code
            date_from: Start date for search
            date_to: End date for search
            law: Law type (default: "44" for 44-FZ)
            customer_region: Customer region (default: "СЗФО")
            execution_statuses: List of execution statuses
            max_pages: Maximum number of pages to scrape
            
        Returns:
            Dictionary with search results including:
            - found_total: Total number of contracts found
            - contracts: List of contract dictionaries
            - search_url: URL used for search
        """
        if execution_statuses is None:
            execution_statuses = ["Исполнение завершено", "Исполнение прекращено"]
            
        # Build initial search URL
        search_url = self.build_search_url(
            ktru_code=ktru_code,
            date_from=date_from,
            date_to=date_to,
            law=law,
            customer_region=customer_region,
            execution_statuses=execution_statuses,
            page=1,
            page_size=50,
        )
        
        logger.info(f"Searching contracts with URL: {search_url}")
        
        # Fetch and parse the first page
        html_content = await self._fetch_with_retry(search_url)
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract total found count
        found_total = self._extract_total_count(soup)
        
        # Extract contracts from first page
        contracts = self._extract_contracts_from_page(soup)
        
        # If there are more pages and we haven't reached max_pages, fetch them
        if found_total > 50 and max_pages > 1:
            total_pages = min((found_total + 49) // 50, max_pages)
            
            for page_num in range(2, total_pages + 1):
                # Respect robots.txt delay if enabled
                if self.respect_robots_delay:
                    await asyncio.sleep(1.0)
                    
                page_url = self.build_search_url(
                    ktru_code=ktru_code,
                    date_from=date_from,
                    date_to=date_to,
                    law=law,
                    customer_region=customer_region,
                    execution_statuses=execution_statuses,
                    page=page_num,
                    page_size=50,
                )
                
                try:
                    page_html = await self._fetch_with_retry(page_url)
                    page_soup = BeautifulSoup(page_html, 'html.parser')
                    page_contracts = self._extract_contracts_from_page(page_soup)
                    contracts.extend(page_contracts)
                    
                    logger.info(f"Fetched page {page_num}/{total_pages}, found {len(page_contracts)} contracts")
                    
                except Exception as e:
                    logger.warning(f"Failed to fetch page {page_num}: {e}")
                    break
                    
        return {
            "found_total": found_total,
            "contracts": contracts,
            "search_url": search_url,
        }
        
    async def _fetch_with_retry(self, url: str) -> str:
        """
        Fetch URL with retry logic and exponential backoff.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                return response.text
                
            except httpx.HTTPError as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries + 1} failed for {url}: {e}")
                
                if attempt < self.max_retries:
                    # Exponential backoff
                    delay = self.base_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)
                    
        # If we get here, all retries failed
        raise last_exception or httpx.HTTPError(f"Failed to fetch {url} after {self.max_retries + 1} attempts")
        
    def _extract_total_count(self, soup: BeautifulSoup) -> int:
        """
        Extract total number of contracts found from search results page.
        
        Args:
            soup: BeautifulSoup object of the search results page
            
        Returns:
            Total number of contracts found
        """
        try:
            # Look for the element containing total count
            # This is a common pattern on zakupki.gov.ru
            count_element = soup.find('div', class_='search-results__total')
            if count_element:
                text = count_element.get_text(strip=True)
                # Extract numbers from text like "Найдено: 1234"
                import re
                numbers = re.findall(r'\d+', text.replace(' ', ''))
                if numbers:
                    return int(numbers[0])
                    
            # Alternative location
            count_element = soup.find('span', class_='search-results-count')
            if count_element:
                text = count_element.get_text(strip=True)
                import re
                numbers = re.findall(r'\d+', text.replace(' ', ''))
                if numbers:
                    return int(numbers[0])
                    
            # If no specific element found, try to find any element with "Найдено"
            for element in soup.find_all(['div', 'span', 'p']):
                text = element.get_text(strip=True)
                if 'Найдено' in text or 'найдено' in text:
                    import re
                    numbers = re.findall(r'\d+', text.replace(' ', ''))
                    if numbers:
                        return int(numbers[0])
                        
        except Exception as e:
            logger.warning(f"Failed to extract total count: {e}")
            
        # Default to 0 if cannot extract
        return 0
        
    def _extract_contracts_from_page(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract contract information from search results page.
        
        Args:
            soup: BeautifulSoup object of the search results page
            
        Returns:
            List of contract dictionaries with keys:
            - reestr_number: Registry number
            - date: Contract date
            - price: Contract price
            - link: Link to contract details
        """
        contracts = []
        
        try:
            # Find all contract rows - this selector may need adjustment
            # based on actual zakupki.gov.ru HTML structure
            contract_rows = soup.find_all('div', class_='registry-entry__body')
            
            for row in contract_rows:
                try:
                    contract_data = self._extract_contract_from_row(row)
                    if contract_data:
                        contracts.append(contract_data)
                except Exception as e:
                    logger.debug(f"Failed to extract contract from row: {e}")
                    continue
                    
            # Alternative selector if above doesn't work
            if not contracts:
                contract_rows = soup.find_all('tr', class_='search-results__item')
                for row in contract_rows:
                    try:
                        contract_data = self._extract_contract_from_row(row)
                        if contract_data:
                            contracts.append(contract_data)
                    except Exception as e:
                        logger.debug(f"Failed to extract contract from row (alt): {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Failed to extract contracts from page: {e}")
            
        return contracts
        
    def _extract_contract_from_row(self, row) -> Optional[Dict]:
        """
        Extract contract information from a single row.
        
        Args:
            row: BeautifulSoup element representing a contract row
            
        Returns:
            Dictionary with contract data or None if extraction fails
        """
        try:
            # Extract registry number
            reestr_number = None
            number_element = row.find('a', class_='registry-entry__header-mid__number')
            if number_element:
                reestr_number = number_element.get_text(strip=True)
            else:
                # Alternative selector
                number_element = row.find('div', class_='registry-entry__header-mid__number')
                if number_element:
                    reestr_number = number_element.get_text(strip=True)
                    
            # Extract date
            date = None
            date_element = row.find('div', class_='data-block__value')
            if date_element:
                date_text = date_element.get_text(strip=True)
                # Try to parse date
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(date_text, '%d.%m.%Y')
                    date = date_obj.strftime('%Y-%m-%d')
                except:
                    date = date_text
                    
            # Extract price
            price = None
            price_element = row.find('div', class_='price-block__value')
            if price_element:
                price_text = price_element.get_text(strip=True)
                # Clean price text (remove spaces, currency symbols)
                import re
                price_match = re.search(r'[\d\s,]+', price_text)
                if price_match:
                    price_str = price_match.group().replace(' ', '').replace(',', '.')
                    try:
                        price = float(price_str)
                    except:
                        pass
                        
            # Extract link
            link = None
            if number_element and number_element.get('href'):
                link = urljoin(self.BASE_URL, number_element['href'])
            else:
                # Try to find any link in the row
                link_element = row.find('a', href=True)
                if link_element:
                    link = urljoin(self.BASE_URL, link_element['href'])
                    
            # Only return if we have at least registry number
            if reestr_number:
                return {
                    'reestr_number': reestr_number,
                    'date': date,
                    'price': price,
                    'link': link,
                }
                
        except Exception as e:
            logger.debug(f"Error extracting contract from row: {e}")
            
        return None
        
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Convenience function for quick searches
async def search_contracts(
    ktru_code: str,
    date_from: datetime,
    date_to: datetime,
    law: str = "44",
    customer_region: str = "СЗФО",
    execution_statuses: List[str] = None,
    max_pages: int = 10,
) -> Dict:
    """
    Convenience function for quick contract searches.
    
    Args:
        ktru_code: KTRU classification code
        date_from: Start date for search
        date_to: End date for search
        law: Law type (default: "44" for 44-FZ)
        customer_region: Customer region (default: "СЗФО")
        execution_statuses: List of execution statuses
        max_pages: Maximum number of pages to scrape
        
    Returns:
        Dictionary with search results
    """
    async with ZakupkiSearchScraper() as scraper:
        return await scraper.search_contracts(
            ktru_code=ktru_code,
            date_from=date_from,
            date_to=date_to,
            law=law,
            customer_region=customer_region,
            execution_statuses=execution_statuses,
            max_pages=max_pages,
        )