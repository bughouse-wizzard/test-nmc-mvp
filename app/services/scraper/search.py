"""
Zakupki.gov.ru search scraper implementation.

This module provides functionality to search for contracts on zakupki.gov.ru
with specific parameters and extract contract information.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class ZakupkiSearchScraper:
    """Scraper for zakupki.gov.ru search functionality."""
    
    BASE_URL = "https://zakupki.gov.ru"
    SEARCH_PATH = "/epz/order/extendedsearch/results.html"
    
    # Default search parameters
    DEFAULT_PARAMS = {
        "searchString": "",  # Search query
        "morphology": "on",  # Morphology search
        "search-filter": "Дате+размещения",  # Sort by placement date
        "pageNumber": 1,  # Page number
        "sortDirection": "false",  # Sort direction (false = descending)
        "recordsPerPage": "_10",  # Records per page (10, 50, 100)
        "showLotsInfoHidden": "false",
        "sortBy": "UPDATE_DATE",  # Sort by update date
        "fz44": "on",  # 44-FZ
        "fz223": "on",  # 223-FZ
        "af": "on",  # Auction
        "ca": "on",  # Contest
        "pc": "on",  # Price contest
        "pa": "on",  # Purchase from single supplier
        "currencyIdGeneral": "-1",  # Currency (all)
    }
    
    # Region codes for SZFO (Northwestern Federal District)
    SZFO_REGIONS = [
        "5277335",  # Республика Карелия
        "5277337",  # Республика Коми
        "5277345",  # Архангельская область
        "5277347",  # Вологодская область
        "5277349",  # Калининградская область
        "5277351",  # Ленинградская область
        "5277353",  # Мурманская область
        "5277355",  # Новгородская область
        "5277357",  # Псковская область
        "5277359",  # г. Санкт-Петербург
        "5277361",  # Ненецкий автономный округ
    ]
    
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        """Initialize the scraper.
        
        Args:
            client: Optional httpx.AsyncClient instance. If not provided,
                   a new client will be created with default settings.
        """
        self.client = client or httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
            }
        )
        
    def build_search_url(self, search_params: Dict[str, Any]) -> str:
        """Build search URL for zakupki.gov.ru based on parameters.
        
        Args:
            search_params: Dictionary with search parameters including:
                - search_string: Search query (KTRU codes, keywords)
                - status: Contract status ("EXECUTED" for executed contracts)
                - region: Region code or "SZFO" for Northwestern Federal District
                - date_from: Start date for search (default: 3 years ago)
                - date_to: End date for search (default: today)
                - page_number: Page number (default: 1)
                
        Returns:
            Complete search URL
        """
        params = self.DEFAULT_PARAMS.copy()
        
        # Set search string (KTRU codes or keywords)
        if search_string := search_params.get("search_string"):
            params["searchString"] = search_string
        
        # Set status filter (EXECUTED)
        if search_params.get("status") == "EXECUTED":
            params["contractStage"] = "EXECUTED"
        
        # Set region filter (SZFO)
        if region := search_params.get("region"):
            if region.upper() == "SZFO":
                # Add all SZFO regions
                for i, region_code in enumerate(self.SZFO_REGIONS, 1):
                    params[f"regions[{i}]"] = region_code
            else:
                params["regions[1]"] = region
        
        # Set date range (last 3 years by default)
        date_from = search_params.get("date_from")
        date_to = search_params.get("date_to")
        
        if not date_from:
            date_from = (datetime.now() - timedelta(days=3*365)).strftime("%d.%m.%Y")
        if not date_to:
            date_to = datetime.now().strftime("%d.%m.%Y")
        
        params["publishDateFrom"] = date_from
        params["publishDateTo"] = date_to
        
        # Set page number
        if page_number := search_params.get("page_number"):
            params["pageNumber"] = page_number
        
        # Build URL
        query_string = urlencode(params, doseq=True)
        return urljoin(self.BASE_URL, f"{self.SEARCH_PATH}?{query_string}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying request after error: {retry_state.outcome.exception()}"
        )
    )
    async def fetch_page(self, url: str) -> str:
        """Fetch HTML page with retry logic and robots.txt compliance.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
            
        Raises:
            httpx.HTTPError: If request fails after retries
        """
        # Respect robots.txt delay (minimum 1 second between requests)
        await asyncio.sleep(1)
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for URL: {url}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for URL: {url} - {e}")
            raise
    
    def parse_search_results(self, html: str) -> Dict[str, Any]:
        """Parse search results HTML to extract contract information.
        
        Args:
            html: HTML content of search results page
            
        Returns:
            Dictionary with:
                - found_total: Total number of contracts found
                - contracts: List of contract dictionaries with:
                    - reestr_number: Registry number
                    - date: Publication date
                    - price: Contract price
                    - link: Link to contract details
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract total number of contracts found
        found_total = 0
        total_element = soup.find('div', class_='search-results__total')
        if total_element:
            total_text = total_element.get_text(strip=True)
            # Extract number from text like "Найдено: 1 234"
            import re
            numbers = re.findall(r'\d+', total_text.replace(' ', ''))
            if numbers:
                found_total = int(numbers[0])
        
        # Extract contract list
        contracts = []
        contract_rows = soup.find_all('div', class_='registry-entry__body')
        
        for row in contract_rows:
            contract = self._parse_contract_row(row)
            if contract:
                contracts.append(contract)
        
        return {
            "found_total": found_total,
            "contracts": contracts
        }
    
    def _parse_contract_row(self, row: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Parse individual contract row.
        
        Args:
            row: BeautifulSoup object for contract row
            
        Returns:
            Dictionary with contract information or None if parsing fails
        """
        try:
            # Extract registry number
            reestr_elem = row.find('div', class_='registry-entry__header-mid__number')
            reestr_number = reestr_elem.get_text(strip=True) if reestr_elem else ""
            
            # Extract date
            date_elem = row.find('div', class_='data-block__value')
            date = date_elem.get_text(strip=True) if date_elem else ""
            
            # Extract price
            price_elem = row.find('div', class_='price-block__value')
            price = price_elem.get_text(strip=True) if price_elem else ""
            
            # Extract link
            link_elem = row.find('a', class_='registry-entry__header-mid__number')
            link = urljoin(self.BASE_URL, link_elem['href']) if link_elem else ""
            
            if not all([reestr_number, date, price, link]):
                return None
            
            return {
                "reestr_number": reestr_number,
                "date": date,
                "price": price,
                "link": link
            }
            
        except (AttributeError, KeyError) as e:
            logger.warning(f"Failed to parse contract row: {e}")
            return None
    
    async def search_contracts(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Main method to search for contracts with given parameters.
        
        Args:
            search_params: Dictionary with search parameters
            
        Returns:
            Dictionary with search results including total count and contracts
        """
        # Build search URL
        url = self.build_search_url(search_params)
        logger.info(f"Searching contracts with URL: {url}")
        
        # Fetch and parse results
        html = await self.fetch_page(url)
        results = self.parse_search_results(html)
        
        logger.info(f"Found {results['found_total']} contracts")
        return results
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def example_usage():
    """Example usage of the ZakupkiSearchScraper."""
    scraper = ZakupkiSearchScraper()
    
    try:
        # Search for KTRU contracts in SZFO region, executed in last 3 years
        search_params = {
            "search_string": "КТРУ",  # KTRU codes
            "status": "EXECUTED",
            "region": "SZFO",
            "date_from": (datetime.now() - timedelta(days=3*365)).strftime("%d.%m.%Y"),
            "date_to": datetime.now().strftime("%d.%m.%Y"),
            "page_number": 1
        }
        
        results = await scraper.search_contracts(search_params)
        
        print(f"Total contracts found: {results['found_total']}")
        print(f"Contracts on page: {len(results['contracts'])}")
        
        for i, contract in enumerate(results['contracts'][:5], 1):
            print(f"\nContract {i}:")
            print(f"  Registry Number: {contract['reestr_number']}")
            print(f"  Date: {contract['date']}")
            print(f"  Price: {contract['price']}")
            print(f"  Link: {contract['link']}")
            
    finally:
        await scraper.close()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())