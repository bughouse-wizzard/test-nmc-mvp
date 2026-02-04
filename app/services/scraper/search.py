"""
Zakupki.gov.ru search scraper implementation.

This module provides functionality to search for contracts on zakupki.gov.ru
with specific parameters: 44-FZ, Status=Executed, Region=SZFO, Date=3 years, KTRU.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger(__name__)


class LawType(Enum):
    """Types of procurement laws."""
    FZ_44 = "44-FZ"  # Federal Law 44
    FZ_223 = "223-FZ"  # Federal Law 223


class ContractStatus(Enum):
    """Contract statuses."""
    EXECUTED = "EXECUTED"  # Исполнен
    ACTIVE = "ACTIVE"      # Активный
    COMPLETED = "COMPLETED"  # Завершен


class Region(Enum):
    """Russian federal districts."""
    SZFO = "SZFO"  # Северо-Западный федеральный округ
    TSFO = "TSFO"  # Центральный федеральный округ
    YUFO = "YUFO"  # Южный федеральный округ
    PFO = "PFO"    # Приволжский федеральный округ
    UFO = "UFO"    # Уральский федеральный округ
    SFO = "SFO"    # Сибирский федеральный округ
    DFO = "DFO"    # Дальневосточный федеральный округ
    SKFO = "SKFO"  # Северо-Кавказский федеральный округ


@dataclass
class Contract:
    """Contract data structure."""
    reestr_number: str
    contract_url: str
    sign_date: str
    price: float
    currency: str = "RUB"


@dataclass
class SearchResult:
    """Search result structure."""
    found_total: int
    contracts: List[Contract]


class ZakupkiSearchScraper:
    """Main scraper class for zakupki.gov.ru."""
    
    BASE_URL = "https://zakupki.gov.ru"
    SEARCH_PATH = "/epz/order/extendedsearch/results.html"
    
    # Default headers to mimic browser
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        """Initialize scraper with optional HTTP client."""
        self.client = client or httpx.AsyncClient(
            headers=self.DEFAULT_HEADERS,
            timeout=30.0,
            follow_redirects=True
        )
        self.robots_delay = 1.0  # Default delay between requests
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    def build_search_url(
        self,
        ktru_code: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        law: LawType = LawType.FZ_44,
        execution_status: ContractStatus = ContractStatus.EXECUTED,
        region: Region = Region.SZFO,
        page: int = 1,
        page_size: int = 50
    ) -> str:
        """
        Build search URL for zakupki.gov.ru.
        
        Args:
            ktru_code: KTRU classification code
            date_from: Start date in format DD.MM.YYYY
            date_to: End date in format DD.MM.YYYY
            law: Procurement law type
            execution_status: Contract execution status
            region: Federal district region
            page: Page number
            page_size: Results per page
            
        Returns:
            Complete search URL
        """
        # Set default date range (last 3 years)
        if not date_from:
            three_years_ago = datetime.now() - timedelta(days=3*365)
            date_from = three_years_ago.strftime("%d.%m.%Y")
        if not date_to:
            date_to = datetime.now().strftime("%d.%m.%Y")
        
        # Build query parameters
        params = {
            "searchString": ktru_code,
            "morphology": "on",
            "searchFilter": f"{law.value}",
            "sortBy": "UPDATE_DATE",
            "pageNumber": page,
            "sortDirection": "false",
            "recordsPerPage": "_" + str(page_size),
            "showLotsInfoHidden": "false",
            "fz44": "on" if law == LawType.FZ_44 else "off",
            "fz223": "on" if law == LawType.FZ_223 else "off",
            "contractStage": "1",  # Все этапы
            "contractStageList": "1,2,3",
            "contractPriceFrom": "",
            "contractPriceTo": "",
            "currencyId": "-1",
            "publishDateFrom": date_from,
            "publishDateTo": date_to,
            "regionDeleted": "false",
            "districtDeleted": "false",
            "okpd2Ids": "",
            "okpd2IdsCodes": "",
            "selectedOkpd2Ids": "",
            "selectedSubjectsRF": region.value,
            "executionStatus": execution_status.value,
        }
        
        # Build URL
        query_string = urlencode(params, doseq=True)
        return f"{self.BASE_URL}{self.SEARCH_PATH}?{query_string}"
    
    async def check_robots_txt(self) -> float:
        """
        Check robots.txt for crawl delay.
        
        Returns:
            Delay in seconds to wait between requests
        """
        try:
            robots_url = f"{self.BASE_URL}/robots.txt"
            response = await self.client.get(robots_url)
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    if line.lower().startswith('crawl-delay:'):
                        try:
                            delay = float(line.split(':')[1].strip())
                            logger.info(f"Found robots.txt crawl delay: {delay}s")
                            return delay
                        except (ValueError, IndexError):
                            pass
        except Exception as e:
            logger.warning(f"Failed to check robots.txt: {e}")
        
        return 1.0  # Default delay
    
    async def fetch_page(self, url: str, retries: int = 3) -> Optional[str]:
        """
        Fetch page with retry logic.
        
        Args:
            url: URL to fetch
            retries: Number of retry attempts
            
        Returns:
            Page HTML content or None if failed
        """
        for attempt in range(retries):
            try:
                logger.debug(f"Fetching {url} (attempt {attempt + 1}/{retries})")
                response = await self.client.get(url)
                response.raise_for_status()
                
                # Respect robots.txt delay
                await asyncio.sleep(self.robots_delay)
                
                return response.text
                
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error {e.response.status_code} for {url}")
                if e.response.status_code in [429, 503]:  # Rate limiting
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                elif attempt == retries - 1:
                    logger.error(f"Failed to fetch {url} after {retries} attempts: {e}")
                    return None
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                if attempt == retries - 1:
                    return None
                await asyncio.sleep(1)
        
        return None
    
    def parse_search_results(self, html: str) -> SearchResult:
        """
        Parse search results HTML.
        
        Args:
            html: HTML content of search results page
            
        Returns:
            SearchResult with total count and contracts
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract total found count
        found_total = 0
        total_element = soup.find('div', class_='search-results__total')
        if total_element:
            text = total_element.get_text(strip=True)
            # Extract number from text like "Найдено: 1 234"
            import re
            match = re.search(r'(\d[\d\s]*)', text)
            if match:
                number_str = match.group(1).replace(' ', '')
                try:
                    found_total = int(number_str)
                except ValueError:
                    logger.warning(f"Could not parse total count from: {text}")
        
        # Extract contracts
        contracts = []
        contract_elements = soup.find_all('div', class_='search-registry-entry-block')
        
        for element in contract_elements:
            try:
                # Extract reestr number
                reestr_elem = element.find('div', class_='registry-entry__header-mid__number')
                reestr_number = reestr_elem.get_text(strip=True) if reestr_elem else "N/A"
                
                # Extract contract URL
                link_elem = element.find('a', class_='registry-entry__header-mid__number')
                contract_url = urljoin(self.BASE_URL, link_elem['href']) if link_elem else ""
                
                # Extract sign date
                date_elem = element.find('div', class_='data-block__value')
                sign_date = date_elem.get_text(strip=True) if date_elem else "N/A"
                
                # Extract price
                price_elem = element.find('div', class_='price-block__value')
                price_text = price_elem.get_text(strip=True) if price_elem else "0"
                # Remove non-numeric characters except decimal point
                import re
                price_clean = re.sub(r'[^\d.,]', '', price_text)
                price_clean = price_clean.replace(',', '.')
                try:
                    price = float(price_clean)
                except ValueError:
                    price = 0.0
                
                # Create contract object
                contract = Contract(
                    reestr_number=reestr_number,
                    contract_url=contract_url,
                    sign_date=sign_date,
                    price=price,
                    currency="RUB"
                )
                contracts.append(contract)
                
            except Exception as e:
                logger.warning(f"Failed to parse contract element: {e}")
                continue
        
        return SearchResult(found_total=found_total, contracts=contracts)
    
    async def search_contracts(
        self,
        ktru_code: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        law: LawType = LawType.FZ_44,
        execution_status: ContractStatus = ContractStatus.EXECUTED,
        region: Region = Region.SZFO,
        max_pages: int = 10
    ) -> Tuple[int, List[Contract]]:
        """
        Search for contracts with given parameters.
        
        Args:
            ktru_code: KTRU classification code
            date_from: Start date in format DD.MM.YYYY
            date_to: End date in format DD.MM.YYYY
            law: Procurement law type
            execution_status: Contract execution status
            region: Federal district region
            max_pages: Maximum number of pages to scrape
            
        Returns:
            Tuple of (total_found_count, list_of_contracts)
        """
        # Check robots.txt for delay
        self.robots_delay = await self.check_robots_txt()
        
        all_contracts = []
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
                page=page
            )
            
            # Fetch page
            html = await self.fetch_page(url)
            if not html:
                logger.warning(f"Failed to fetch page {page}")
                break
            
            # Parse results
            result = self.parse_search_results(html)
            
            # First page gives us total count
            if page == 1:
                total_found = result.found_total
            
            # Add contracts from this page
            all_contracts.extend(result.contracts)
            
            # Stop if we have all contracts or no more contracts
            if not result.contracts or len(all_contracts) >= total_found:
                break
            
            logger.info(f"Page {page}: found {len(result.contracts)} contracts")
        
        logger.info(f"Total contracts found: {len(all_contracts)}/{total_found}")
        return total_found, all_contracts


async def search_contracts(
    ktru_code: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    law: LawType = LawType.FZ_44,
    execution_status: ContractStatus = ContractStatus.EXECUTED,
    region: Region = Region.SZFO,
    max_pages: int = 10
) -> Tuple[int, List[Contract]]:
    """
    Convenience function for searching contracts.
    
    Args:
        ktru_code: KTRU classification code
        date_from: Start date in format DD.MM.YYYY
        date_to: End date in format DD.MM.YYYY
        law: Procurement law type
        execution_status: Contract execution status
        region: Federal district region
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
