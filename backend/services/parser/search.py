"""
Search parser for zakupki.gov.ru contract search.
Implements URL construction, HTTP client, and HTML parsing for contract search results.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin

import aiohttp
from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger(__name__)


class SearchParser:
    """Parser for zakupki.gov.ru contract search results."""
    
    def __init__(self):
        self.base_url = settings.ZAKUPKI_BASE_URL
        self.search_url = urljoin(self.base_url, "/epz/contract/search/results.html")
        self.timeout = settings.REQUEST_TIMEOUT
        self.max_retries = settings.MAX_RETRIES
        self.crawl_delay = settings.CRAWL_DELAY
        self.last_request_time = 0
        
        # Realistic browser headers to avoid blocking
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "DNT": "1",
        }
    
    def _build_search_params(
        self,
        ktru_code: str,
        customer_region: str,
        law: str,
        date_from: datetime,
        date_to: datetime,
        execution_statuses: List[str],
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, str]:
        """
        Build query parameters for zakupki.gov.ru search.
        
        Args:
            ktru_code: KTRU code for search
            customer_region: Customer region (e.g., "СЗФО")
            law: Procurement law (e.g., "44-ФЗ")
            date_from: Start date for search
            date_to: End date for search
            execution_statuses: List of execution statuses
            page: Page number (default: 1)
            page_size: Results per page (default: 50)
            
        Returns:
            Dictionary of query parameters
        """
        # Format dates to string in format DD.MM.YYYY
        date_from_str = date_from.strftime("%d.%m.%Y")
        date_to_str = date_to.strftime("%d.%m.%Y")
        
        # Map law to zakupki.gov.ru parameter
        law_mapping = {
            "44-ФЗ": "fz44",
            "223-ФЗ": "fz223",
            "94-ФЗ": "fz94",
        }
        law_param = law_mapping.get(law, "fz44")
        
        # Map region to code (simplified - in real implementation would need region mapping)
        # For now, using region name directly
        region_param = customer_region
        
        # Build parameters based on zakupki.gov.ru search form
        params = {
            "searchString": ktru_code,
            "morphology": "on",
            "search-filter": date_from_str,
            "search-filter-to": date_to_str,
            "priceFrom": "",
            "priceTo": "",
            "currencyId": -1,
            "selectedRegions": region_param,
            "selectedFz": law_param,
            "contractStage": "EXECUTION_COMPLETED",  # Исполнение завершено
            "sortBy": "UPDATE_DATE",  # Sort by update date
            "pageNumber": page,
            "recordsPerPage": _select_page_size(page_size),
            "showLotsInfoHidden": "false",
            "sortDirection": "false",  # false = descending (newest first)
            "contractsForOnePage": page_size,
        }
        
        # Add execution status filter
        if execution_statuses:
            # Map statuses to zakupki.gov.ru values
            status_mapping = {
                "Исполнение завершено": "EXECUTION_COMPLETED",
                "Исполняется": "EXECUTION_IN_PROGRESS",
                "Расторгнут": "TERMINATED",
            }
            status_params = []
            for status in execution_statuses:
                if status in status_mapping:
                    status_params.append(status_mapping[status])
            
            if status_params:
                params["contractStage"] = ",".join(status_params)
        
        return params
    
    def build_search_url(
        self,
        ktru_code: str,
        customer_region: str,
        law: str,
        date_from: datetime,
        date_to: datetime,
        execution_statuses: List[str],
        page: int = 1,
        page_size: int = 50,
    ) -> str:
        """
        Build complete search URL for zakupki.gov.ru.
        
        Args:
            ktru_code: KTRU code for search
            customer_region: Customer region (e.g., "СЗФО")
            law: Procurement law (e.g., "44-ФЗ")
            date_from: Start date for search
            date_to: End date for search
            execution_statuses: List of execution statuses
            page: Page number (default: 1)
            page_size: Results per page (default: 50)
            
        Returns:
            Complete search URL
        """
        params = self._build_search_params(
            ktru_code=ktru_code,
            customer_region=customer_region,
            law=law,
            date_from=date_from,
            date_to=date_to,
            execution_statuses=execution_statuses,
            page=page,
            page_size=page_size,
        )
        
        query_string = urlencode(params, doseq=True)
        return f"{self.search_url}?{query_string}"
    
    async def _respect_crawl_delay(self):
        """Respect crawl delay between requests."""
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.crawl_delay:
            wait_time = self.crawl_delay - time_since_last
            logger.debug(f"Respecting crawl delay: waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def _make_request_with_retry(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        Make HTTP request with retry logic, crawl-delay awareness, and proper error handling.
        
        Args:
            url: URL to request
            session: aiohttp ClientSession
            
        Returns:
            Response text or None if all retries failed
        """
        for attempt in range(self.max_retries):
            try:
                # Respect crawl delay between requests
                await self._respect_crawl_delay()
                
                logger.debug(f"Request attempt {attempt + 1}/{self.max_retries} for {url}")
                
                async with session.get(url, headers=self.headers, timeout=self.timeout) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.debug(f"Successfully fetched {url}, content length: {len(content)}")
                        return content
                    elif response.status == 429:  # Too Many Requests - rate limited
                        retry_after = response.headers.get('Retry-After', self.crawl_delay)
                        logger.warning(
                            f"Rate limited (429) for {url}, "
                            f"Retry-After: {retry_after}s, "
                            f"attempt {attempt + 1}/{self.max_retries}"
                        )
                        await asyncio.sleep(int(retry_after))
                    elif response.status == 403:  # Forbidden - might be blocked
                        logger.error(f"Access forbidden (403) for {url}, check User-Agent or IP")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.crawl_delay * 2)  # Longer delay for 403
                    elif 500 <= response.status < 600:  # Server errors
                        logger.warning(
                            f"Server error {response.status} for {url}, "
                            f"attempt {attempt + 1}/{self.max_retries}"
                        )
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        logger.error(
                            f"HTTP {response.status} for {url}, "
                            f"attempt {attempt + 1}/{self.max_retries}"
                        )
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
            except asyncio.TimeoutError:
                logger.error(f"Timeout for {url}, attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except aiohttp.ClientError as e:
                logger.error(f"Client error fetching {url}: {e}, attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}, attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(f"All {self.max_retries} attempts failed for {url}")
        return None
    
    def _parse_search_results(self, html: str) -> Tuple[int, List[Dict]]:
        """
        Parse HTML search results to extract total count and contract cards.
        
        Args:
            html: HTML content of search results page
            
        Returns:
            Tuple of (total_found_count, list_of_contracts)
        """
        soup = BeautifulSoup(html, "lxml")
        
        # Extract total found count - try multiple selectors
        total_found = 0
        total_selectors = [
            "div.search-results__total",
            "div.search-results-total",
            "div.total-results",
            "span.total-count",
            "div.results-count",
        ]
        
        for selector in total_selectors:
            total_element = soup.select_one(selector)
            if total_element:
                total_text = total_element.get_text(strip=True)
                # Extract number from text like "Найдено: 1 234" or "1 234 найденных записей"
                import re
                # Find all numbers in the text
                numbers = re.findall(r'\d[\d\s]*', total_text)
                if numbers:
                    # Take the largest number (in case there are multiple)
                    largest_number = max(numbers, key=lambda x: int(x.replace(" ", "")))
                    total_found = int(largest_number.replace(" ", ""))
                    logger.debug(f"Found total count: {total_found} using selector: {selector}")
                    break
        
        # Extract contract cards - try multiple selectors
        contracts = []
        card_selectors = [
            "div.search-registry-entry-block",
            "div.registry-entry",
            "div.contract-card",
            "div.search-result-item",
            "div.card-wrapper",
        ]
        
        card_elements = []
        for selector in card_selectors:
            elements = soup.select(selector)
            if elements:
                card_elements = elements
                logger.debug(f"Found {len(elements)} contract cards using selector: {selector}")
                break
        
        for card in card_elements:
            contract_data = self._parse_contract_card(card)
            if contract_data:
                contracts.append(contract_data)
        
        logger.info(f"Parsed {len(contracts)} contracts from page, total found: {total_found}")
        return total_found, contracts
    
    def _parse_contract_card(self, card) -> Optional[Dict]:
        """
        Parse individual contract card element.
        
        Args:
            card: BeautifulSoup element of contract card
            
        Returns:
            Dictionary with contract data or None if parsing fails
        """
        try:
            import re
            
            # Extract registry number - try multiple selectors
            registry_no = ""
            registry_selectors = [
                "a.registry-entry__header-mid__number",
                "div.registry-entry__header-mid__number",
                "span.contract-number",
                "div.contract-id",
                "a[href*='/contract/']",
                "a[href*='/epz/contract/']",
            ]
            
            for selector in registry_selectors:
                element = card.select_one(selector)
                if element:
                    registry_no = element.get_text(strip=True)
                    if registry_no:
                        break
            
            # Extract date - try multiple selectors and formats
            date_str = ""
            date_selectors = [
                "div.data-block__value",
                "span.contract-date",
                "div.publish-date",
                "time",
                "div.date-value",
            ]
            
            for selector in date_selectors:
                element = card.select_one(selector)
                if element:
                    date_text = element.get_text(strip=True)
                    # Try to find date in format DD.MM.YYYY or YYYY-MM-DD
                    date_patterns = [
                        r"(\d{2}\.\d{2}\.\d{4})",  # DD.MM.YYYY
                        r"(\d{4}-\d{2}-\d{2})",     # YYYY-MM-DD
                        r"(\d{2}/\d{2}/\d{4})",     # DD/MM/YYYY
                    ]
                    
                    for pattern in date_patterns:
                        match = re.search(pattern, date_text)
                        if match:
                            date_str = match.group(1)
                            break
                    
                    if date_str:
                        break
            
            # Extract price - try multiple selectors
            price = None
            price_selectors = [
                "div.price-block__value",
                "span.contract-price",
                "div.price-value",
                "div.amount",
                "span.amount-value",
            ]
            
            for selector in price_selectors:
                element = card.select_one(selector)
                if element:
                    price_text = element.get_text(strip=True)
                    # Extract numeric value from price text like "1 234 567,89 руб." or "1 234 567.89"
                    # Find all numbers with spaces, commas, or dots
                    price_matches = re.findall(r'[\d\s,\.]+', price_text)
                    if price_matches:
                        # Take the first match and clean it
                        price_str = price_matches[0]
                        # Remove spaces, replace comma with dot for decimal
                        price_str = price_str.replace(" ", "").replace(",", ".")
                        try:
                            price = float(price_str)
                            break
                        except ValueError:
                            continue
            
            # Extract URL - try multiple selectors
            url = ""
            url_selectors = [
                "a.registry-entry__header-mid__number[href]",
                "a[href*='/contract/'][href]",
                "a[href*='/epz/contract/'][href]",
                "a.card-link[href]",
            ]
            
            for selector in url_selectors:
                element = card.select_one(selector)
                if element and element.get("href"):
                    url = urljoin(self.base_url, element["href"])
                    break
            
            # Extract customer/organization (optional)
            customer = ""
            customer_selectors = [
                "div.registry-entry__body-href",
                "div.customer-name",
                "span.organization",
                "div.procuring-entity",
            ]
            
            for selector in customer_selectors:
                element = card.select_one(selector)
                if element:
                    customer = element.get_text(strip=True)
                    break
            
            # Extract status (optional)
            status = ""
            status_selectors = [
                "div.registry-entry__header-mid__title",
                "span.contract-status",
                "div.status-badge",
                "div.execution-status",
            ]
            
            for selector in status_selectors:
                element = card.select_one(selector)
                if element:
                    status = element.get_text(strip=True)
                    break
            
            # Only return if we have at least registry number or date
            if registry_no or date_str:
                return {
                    "registry_no": registry_no,
                    "date": date_str,
                    "price": price,
                    "url": url,
                    "customer": customer,
                    "status": status,
                }
            else:
                logger.debug(f"Skipping contract card - missing required fields: registry_no={registry_no}, date={date_str}")
                
        except Exception as e:
            logger.error(f"Error parsing contract card: {e}")
        
        return None
    
    async def search_contracts(
        self,
        ktru_code: str,
        customer_region: str,
        law: str,
        date_from: datetime,
        date_to: datetime,
        execution_statuses: List[str],
        limit_contracts: int = 30,
    ) -> Tuple[int, List[Dict]]:
        """
        Search for contracts on zakupki.gov.ru.
        
        Args:
            ktru_code: KTRU code for search
            customer_region: Customer region (e.g., "СЗФО")
            law: Procurement law (e.g., "44-ФЗ")
            date_from: Start date for search
            date_to: End date for search
            execution_statuses: List of execution statuses
            limit_contracts: Maximum number of contracts to return
            
        Returns:
            Tuple of (total_found_count, list_of_contracts)
        """
        logger.info(
            f"Searching contracts: KTRU={ktru_code}, region={customer_region}, "
            f"law={law}, date_from={date_from}, date_to={date_to}, limit={limit_contracts}"
        )
        
        all_contracts = []
        page = 1
        page_size = 50
        
        async with aiohttp.ClientSession() as session:
            while len(all_contracts) < limit_contracts:
                # Build URL for current page
                url = self.build_search_url(
                    ktru_code=ktru_code,
                    customer_region=customer_region,
                    law=law,
                    date_from=date_from,
                    date_to=date_to,
                    execution_statuses=execution_statuses,
                    page=page,
                    page_size=page_size,
                )
                
                logger.debug(f"Fetching page {page}: {url}")
                
                # Make request
                html = await self._make_request_with_retry(url, session)
                if not html:
                    break
                
                # Parse results
                total_found, page_contracts = self._parse_search_results(html)
                
                if not page_contracts:
                    break
                
                # Add contracts from this page
                all_contracts.extend(page_contracts)
                
                # Check if we need more pages
                if len(all_contracts) >= limit_contracts or len(page_contracts) < page_size:
                    break
                
                page += 1
        
        # Sort by date (newest first) and apply limit
        sorted_contracts = self._sort_and_limit_contracts(all_contracts, limit_contracts)
        
        # Get total found from first page if we have it
        total_found = len(all_contracts) if all_contracts else 0
        
        return total_found, sorted_contracts
    
    def _sort_and_limit_contracts(self, contracts: List[Dict], limit: int) -> List[Dict]:
        """
        Sort contracts by date (newest first) and apply limit.
        
        Args:
            contracts: List of contract dictionaries
            limit: Maximum number of contracts to return
            
        Returns:
            Sorted and limited list of contracts
        """
        if not contracts:
            return []
        
        # Helper function to parse dates from various formats
        def parse_date(date_str: str) -> datetime:
            """Parse date from string, handling multiple formats."""
            if not date_str:
                return datetime.min
            
            date_formats = [
                "%d.%m.%Y",    # DD.MM.YYYY
                "%Y-%m-%d",    # YYYY-MM-DD
                "%d/%m/%Y",    # DD/MM/YYYY
                "%Y.%m.%d",    # YYYY.MM.DD
            ]
            
            for date_format in date_formats:
                try:
                    return datetime.strptime(date_str, date_format)
                except ValueError:
                    continue
            
            # Try to extract date from string using regex
            import re
            date_patterns = [
                r"(\d{2})\.(\d{2})\.(\d{4})",  # DD.MM.YYYY
                r"(\d{4})-(\d{2})-(\d{2})",    # YYYY-MM-DD
                r"(\d{2})/(\d{2})/(\d{4})",    # DD/MM/YYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, date_str)
                if match:
                    try:
                        if pattern.startswith(r"(\d{4})"):  # YYYY-MM-DD
                            year, month, day = match.groups()
                        else:  # DD.MM.YYYY or DD/MM/YYYY
                            day, month, year = match.groups()
                        
                        return datetime(int(year), int(month), int(day))
                    except (ValueError, TypeError):
                        continue
            
            # If all parsing fails, return distant past
            return datetime.min
        
        # Sort by date (newest first)
        # Use a stable sort by adding a secondary key (registry number) for ties
        sorted_contracts = sorted(
            contracts,
            key=lambda x: (
                parse_date(x.get("date", "")),  # Primary: date
                x.get("registry_no", ""),       # Secondary: registry number for tie-breaking
            ),
            reverse=True  # Newest first
        )
        
        # Apply limit
        limited_contracts = sorted_contracts[:limit]
        
        logger.debug(f"Sorted {len(contracts)} contracts, returning {len(limited_contracts)} (limit: {limit})")
        return limited_contracts


def _select_page_size(desired_size: int) -> int:
    """Select appropriate page size from available options."""
    available_sizes = [10, 50, 100, 500]
    for size in available_sizes:
        if size >= desired_size:
            return size
    return available_sizes[-1]