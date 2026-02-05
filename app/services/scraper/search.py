"""
Zakupki.gov.ru search scraper implementation.

This module provides functionality to search for contracts on zakupki.gov.ru
with specific parameters: 44-FZ, Status=Executed, Region=SZFO, Date=3 years, KTRU.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

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
    URAL = "URAL"  # Уральский федеральный округ
    SIB = "SIB"    # Сибирский федеральный округ
    DFO = "DFO"    # Дальневосточный федеральный округ


@dataclass
class Contract:
    """Contract data model."""
    reestr_number: str  # Реестровый номер
    date: datetime      # Дата контракта
    price: float       # Цена контракта
    link: str          # Ссылка на контракт
    customer: Optional[str] = None  # Заказчик
    supplier: Optional[str] = None  # Поставщик
    subject: Optional[str] = None   # Предмет контракта


@dataclass
class SearchResult:
    """Search result container."""
    found_total: int          # Общее количество найденных контрактов
    contracts: List[Contract]  # Список контрактов
    search_url: str           # URL поиска


class ZakupkiScraper:
    """Main scraper class for zakupki.gov.ru."""
    
    BASE_URL = "https://zakupki.gov.ru"
    SEARCH_PATH = "/epz/order/extendedsearch/results.html"
    
    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0
    ):
        """
        Initialize the scraper.
        
        Args:
            client: Optional httpx client (will be created if not provided)
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries in seconds
            timeout: Request timeout in seconds
        """
        self.client = client or httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.last_request_time = 0
        self.robots_delay = 1.0  # Default delay from robots.txt
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def _build_search_url(
        self,
        law_type: LawType = LawType.FZ_44,
        status: ContractStatus = ContractStatus.EXECUTED,
        region: Region = Region.SZFO,
        years_back: int = 3,
        ktru_code: Optional[str] = None
    ) -> str:
        """
        Build search URL for zakupki.gov.ru based on parameters.
        
        Args:
            law_type: Type of procurement law (44-FZ or 223-FZ)
            status: Contract status
            region: Federal district
            years_back: Number of years to look back
            ktru_code: Optional KTRU classification code
            
        Returns:
            Complete search URL
        """
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * years_back)
        
        # Format dates for URL
        date_format = "%d.%m.%Y"
        date_from = start_date.strftime(date_format)
        date_to = end_date.strftime(date_format)
        
        # Build query parameters
        params = {
            "searchString": ktru_code or "",
            "morphology": "on",
            "searchFilter": f"{date_from} до {date_to}",
            "sortBy": "UPDATE_DATE",
            "pageNumber": "1",
            "sortDirection": "false",
            "recordsPerPage": "_50",
            "showLotsInfoHidden": "false",
            "fz44": "on" if law_type == LawType.FZ_44 else "off",
            "fz223": "on" if law_type == LawType.FZ_223 else "off",
            "contractStage": "1" if status == ContractStatus.EXECUTED else "0",
            "contractStage": "1",  # Исполненные контракты
            "regionDeleted": "false",
            "sortBy": "UPDATE_DATE",
            "regions": self._get_region_code(region),
            "contractPriceFrom": "",
            "contractPriceTo": "",
            "currencyId": "-1",
            "budgetLevelsIdNameHidden": "",
            "customerTitle": "",
            "customerCode": "",
            "customerFz94id": "",
            "customerInn": "",
            "okpd2Ids": "",
            "okpd2IdsCodes": "",
        }
        
        # Build URL with parameters
        query_string = "&".join([f"{k}={v}" for k, v in params.items() if v])
        url = f"{self.BASE_URL}{self.SEARCH_PATH}?{query_string}"
        
        logger.debug(f"Built search URL: {url}")
        return url
    
    def _get_region_code(self, region: Region) -> str:
        """Get region code for zakupki.gov.ru."""
        region_codes = {
            Region.SZFO: "78000000",  # Северо-Западный федеральный округ
            Region.TSFO: "77000000",  # Центральный федеральный округ
            Region.YUFO: "79000000",  # Южный федеральный округ
            Region.PFO: "73000000",   # Приволжский федеральный округ
            Region.URAL: "74000000",  # Уральский федеральный округ
            Region.SIB: "75000000",   # Сибирский федеральный округ
            Region.DFO: "76000000",   # Дальневосточный федеральный округ
        }
        return region_codes.get(region, "78000000")  # Default to SZFO
    
    async def _respect_robots_delay(self):
        """Respect robots.txt delay between requests."""
        import time
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.robots_delay:
            wait_time = self.robots_delay - time_since_last
            logger.debug(f"Respecting robots.txt delay: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def _fetch_with_retry(self, url: str) -> httpx.Response:
        """
        Fetch URL with retry logic and exponential backoff.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                await self._respect_robots_delay()
                response = await self.client.get(url)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to fetch {url} after {self.max_retries} attempts: {e}")
                    raise
                
                delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Attempt {attempt + 1} failed for {url}, retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        
        # This should never be reached due to raise above
        raise httpx.HTTPError(f"Failed to fetch {url} after {self.max_retries} attempts")
    
    def _parse_search_results(self, html: str, search_url: str) -> SearchResult:
        """
        Parse search results HTML to extract contract data.
        
        Args:
            html: HTML content of search results page
            search_url: Original search URL
            
        Returns:
            SearchResult with found_total and contracts list
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract total found count
        found_total = 0
        total_element = soup.find("div", class_="search-results__total")
        if total_element:
            text = total_element.get_text(strip=True)
            # Extract number from text like "Найдено: 1 234"
            import re
            numbers = re.findall(r'\d+', text.replace(" ", ""))
            if numbers:
                found_total = int(numbers[0])
        
        # Extract contracts
        contracts = []
        contract_rows = soup.find_all("div", class_="search-registry-entry-block")
        
        for row in contract_rows:
            try:
                contract = self._parse_contract_row(row)
                if contract:
                    contracts.append(contract)
            except Exception as e:
                logger.warning(f"Failed to parse contract row: {e}")
                continue
        
        return SearchResult(
            found_total=found_total,
            contracts=contracts,
            search_url=search_url
        )
    
    def _parse_contract_row(self, row) -> Optional[Contract]:
        """Parse individual contract row from search results."""
        try:
            # Extract reestr number
            reestr_elem = row.find("div", class_="registry-entry__header-mid__number")
            reestr_number = reestr_elem.get_text(strip=True) if reestr_elem else "N/A"
            
            # Extract date
            date_elem = row.find("div", class_="data-block__value")
            date_str = date_elem.get_text(strip=True) if date_elem else ""
            date = self._parse_date(date_str)
            
            # Extract price
            price_elem = row.find("div", class_="price-block__value")
            price_str = price_elem.get_text(strip=True) if price_elem else "0"
            price = self._parse_price(price_str)
            
            # Extract link
            link_elem = row.find("a", class_="registry-entry__header-mid__number__link")
            link = f"{self.BASE_URL}{link_elem['href']}" if link_elem else ""
            
            # Extract customer and supplier (if available)
            customer_elem = row.find("div", class_="registry-entry__body-href")
            customer = customer_elem.get_text(strip=True) if customer_elem else None
            
            supplier_elem = row.find("div", class_="registry-entry__body-value")
            supplier = supplier_elem.get_text(strip=True) if supplier_elem else None
            
            return Contract(
                reestr_number=reestr_number,
                date=date,
                price=price,
                link=link,
                customer=customer,
                supplier=supplier
            )
        except Exception as e:
            logger.warning(f"Error parsing contract row: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string from Russian format."""
        try:
            # Try different date formats
            formats = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None
        except Exception:
            return None
    
    def _parse_price(self, price_str: str) -> float:
        """Parse price string to float."""
        try:
            if not price_str or not price_str.strip():
                return 0.0
                
            # Remove spaces and common currency symbols
            cleaned = price_str.strip()
            # Remove common currency symbols and abbreviations
            currency_symbols = ["₽", "€", "$", "р.", "руб.", "RUB", "EUR", "USD"]
            for symbol in currency_symbols:
                cleaned = cleaned.replace(symbol, "")
            
            # Remove all spaces
            cleaned = cleaned.replace(" ", "")
            
            # Handle different decimal separators
            import re
            
            # Check if it's European format with comma as decimal separator
            # Pattern: digits, optional thousands separators (dots or spaces), comma, 1-2 digits
            euro_pattern = r'^(\d{1,3}(?:[.\s]\d{3})*),(\d{1,2})$'
            euro_match = re.match(euro_pattern, cleaned)
            
            if euro_match:
                # European format: 1.234.567,89 or 1 234 567,89
                integer_part = euro_match.group(1).replace(".", "").replace(" ", "")
                decimal_part = euro_match.group(2)
                cleaned = f"{integer_part}.{decimal_part}"
            else:
                # Try US/International format with dot as decimal
                # Remove commas (thousands separators)
                cleaned = cleaned.replace(",", "")
                # If there are multiple dots, keep only the last one as decimal
                if cleaned.count(".") > 1:
                    parts = cleaned.split(".")
                    cleaned = "".join(parts[:-1]) + "." + parts[-1]
            
            # Extract number with optional minus sign
            # Pattern: optional minus, digits, optional dot, optional digits
            number_pattern = r'(-?\d+(?:\.\d+)?)'
            match = re.search(number_pattern, cleaned)
            
            if match:
                return float(match.group(1))
            else:
                return 0.0
                
        except Exception:
            return 0.0
    
    async def search(
        self,
        law_type: LawType = LawType.FZ_44,
        status: ContractStatus = ContractStatus.EXECUTED,
        region: Region = Region.SZFO,
        years_back: int = 3,
        ktru_code: Optional[str] = None
    ) -> SearchResult:
        """
        Search for contracts on zakupki.gov.ru.
        
        Args:
            law_type: Type of procurement law (44-FZ or 223-FZ)
            status: Contract status
            region: Federal district
            years_back: Number of years to look back
            ktru_code: Optional KTRU classification code
            
        Returns:
            SearchResult with found contracts
        """
        # Build search URL
        search_url = self._build_search_url(
            law_type=law_type,
            status=status,
            region=region,
            years_back=years_back,
            ktru_code=ktru_code
        )
        
        logger.info(f"Searching contracts with URL: {search_url}")
        
        try:
            # Fetch search results
            response = await self._fetch_with_retry(search_url)
            html = response.text
            
            # Parse results
            result = self._parse_search_results(html, search_url)
            
            logger.info(f"Found {result.found_total} contracts, parsed {len(result.contracts)}")
            return result
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise


async def main():
    """Example usage of the scraper."""
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async with ZakupkiScraper() as scraper:
        try:
            # Search for contracts with default parameters
            result = await scraper.search(
                law_type=LawType.FZ_44,
                status=ContractStatus.EXECUTED,
                region=Region.SZFO,
                years_back=3,
                ktru_code=None  # Optional KTRU code
            )
            
            print(f"Total found: {result.found_total}")
            print(f"Parsed contracts: {len(result.contracts)}")
            print(f"Search URL: {result.search_url}")
            
            # Print first few contracts
            for i, contract in enumerate(result.contracts[:5], 1):
                print(f"\nContract {i}:")
                print(f"  Reestr Number: {contract.reestr_number}")
                print(f"  Date: {contract.date.strftime('%d.%m.%Y') if contract.date else 'N/A'}")
                print(f"  Price: {contract.price:,.2f} ₽")
                print(f"  Link: {contract.link}")
                if contract.customer:
                    print(f"  Customer: {contract.customer}")
                if contract.supplier:
                    print(f"  Supplier: {contract.supplier}")
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())