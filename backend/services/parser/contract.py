"""
Contract Detail & Attachment Parser for zakupki.gov.ru

This module implements logic to:
1. Fetch the contract common info page (`.../common-info.html`)
2. Navigate to/fetch the 'Payments and Objects of Purchase' tab to extract line items (Specification)
3. Identify attachments. For contracts > 2025 (or as configured), implement logic to download 
   the 'Printed Form' (Печатная форма) PDF/DOCX to a temporary storage or memory buffer for AI processing.
4. Handle extraction of Unit Prices from the structured HTML table if available.
"""

import asyncio
import logging
import tempfile
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger(__name__)


class ContractParser:
    """Parser for contract details and attachments from zakupki.gov.ru"""
    
    def __init__(
        self,
        base_url: str = None,
        timeout: int = None,
        max_retries: int = None,
        crawl_delay: int = None
    ):
        """
        Initialize the contract parser.
        
        Args:
            base_url: Base URL for zakupki.gov.ru
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            crawl_delay: Delay between requests in seconds
        """
        self.base_url = base_url or settings.ZAKUPKI_BASE_URL
        self.timeout = timeout or settings.REQUEST_TIMEOUT
        self.max_retries = max_retries or settings.MAX_RETRIES
        self.crawl_delay = crawl_delay or settings.CRAWL_DELAY
        
        # HTTP client configuration
        self.client_timeout = httpx.Timeout(self.timeout)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
        }
        
        # Temporary storage for downloaded files
        self.temp_dir = Path(tempfile.gettempdir()) / "nmck_parser"
        self.temp_dir.mkdir(exist_ok=True)
        
    async def _make_request(self, url: str, method: str = "GET", **kwargs) -> httpx.Response:
        """
        Make HTTP request with retry logic and rate limiting.
        
        Args:
            url: URL to request
            method: HTTP method
            **kwargs: Additional arguments for httpx request
            
        Returns:
            httpx.Response object
            
        Raises:
            httpx.HTTPError: If request fails after all retries
        """
        async with httpx.AsyncClient(timeout=self.client_timeout) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        **kwargs
                    )
                    response.raise_for_status()
                    
                    # Respect crawl delay
                    if self.crawl_delay > 0:
                        await asyncio.sleep(self.crawl_delay)
                    
                    return response
                    
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    if attempt == self.max_retries - 1:
                        logger.error(f"Request failed after {self.max_retries} attempts: {e}")
                        raise
                    
                    logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    async def parse_contract(self, contract_url: str) -> Dict[str, Any]:
        """
        Parse contract details from the given URL.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            Dictionary with parsed contract data
        """
        logger.info(f"Parsing contract: {contract_url}")
        
        # Extract reestr number from URL
        reestr_number = self._extract_reestr_number(contract_url)
        
        # Parse common info page
        common_info = await self._parse_common_info(contract_url)
        
        # Parse payments and objects tab
        payments_data = await self._parse_payments_tab(contract_url)
        
        # Identify and download attachments
        attachments = await self._identify_attachments(contract_url)
        
        # Check if contract is from 2025 or later
        contract_year = self._extract_contract_year(common_info)
        is_2025_plus = contract_year >= 2025
        
        # Download printed form if contract is 2025+
        printed_form_data = None
        if is_2025_plus:
            printed_form_data = await self._download_printed_form(contract_url, attachments)
        
        # Extract unit prices
        unit_prices = self._extract_unit_prices(payments_data)
        
        return {
            "reestr_number": reestr_number,
            "contract_url": contract_url,
            "common_info": common_info,
            "payments_data": payments_data,
            "attachments": attachments,
            "contract_year": contract_year,
            "is_2025_plus": is_2025_plus,
            "printed_form_data": printed_form_data,
            "unit_prices": unit_prices,
            "parsed_at": datetime.utcnow().isoformat()
        }
    
    def _extract_reestr_number(self, contract_url: str) -> str:
        """
        Extract reestr number from contract URL.
        
        Args:
            contract_url: Contract URL
            
        Returns:
            Reestr number
        """
        # Parse URL and extract reestrNumber parameter
        parsed_url = urlparse(contract_url)
        query_params = dict(param.split('=') for param in parsed_url.query.split('&') if '=' in param)
        return query_params.get('reestrNumber', '')
    
    async def _parse_common_info(self, contract_url: str) -> Dict[str, Any]:
        """
        Parse the common info page of the contract.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            Dictionary with common info data
        """
        logger.info(f"Parsing common info page: {contract_url}")
        
        try:
            response = await self._make_request(contract_url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract basic contract information
            # This is a simplified example - actual implementation would need to
            # parse the specific HTML structure of zakupki.gov.ru
            
            common_info = {
                "contract_number": self._extract_text(soup, ".contract-number"),
                "sign_date": self._extract_text(soup, ".sign-date"),
                "customer": self._extract_text(soup, ".customer-info"),
                "supplier": self._extract_text(soup, ".supplier-info"),
                "contract_price": self._extract_text(soup, ".contract-price"),
                "currency": self._extract_text(soup, ".currency"),
                "status": self._extract_text(soup, ".contract-status"),
                "html_content": response.text[:5000]  # Store first 5000 chars for debugging
            }
            
            return common_info
            
        except Exception as e:
            logger.error(f"Failed to parse common info: {e}")
            return {"error": str(e)}
    
    def _extract_text(self, soup: BeautifulSoup, selector: str) -> str:
        """
        Extract text from element using CSS selector.
        
        Args:
            soup: BeautifulSoup object
            selector: CSS selector
            
        Returns:
            Extracted text or empty string
        """
        element = soup.select_one(selector)
        return element.get_text(strip=True) if element else ""
    
    async def _parse_payments_tab(self, contract_url: str) -> Dict[str, Any]:
        """
        Parse the 'Payments and Objects of Purchase' tab.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            Dictionary with payments and objects data
        """
        logger.info(f"Parsing payments and objects tab: {contract_url}")
        
        try:
            # Construct URL for payments tab
            # The actual URL pattern might be different - this is an example
            payments_url = contract_url.replace("common-info.html", "payments.html")
            
            response = await self._make_request(payments_url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract specification table
            specification = self._extract_specification_table(soup)
            
            # Extract line items
            line_items = self._extract_line_items(soup)
            
            payments_data = {
                "specification": specification,
                "line_items": line_items,
                "html_content": response.text[:5000]  # Store first 5000 chars for debugging
            }
            
            return payments_data
            
        except Exception as e:
            logger.error(f"Failed to parse payments tab: {e}")
            return {"error": str(e), "specification": [], "line_items": []}
    
    def _extract_specification_table(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extract specification table from HTML.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of specification items
        """
        specification = []
        
        # Look for specification tables
        # This is a simplified example - actual implementation would need to
        # parse the specific HTML structure of zakupki.gov.ru
        
        tables = soup.find_all("table", class_="specification")
        if not tables:
            tables = soup.find_all("table")
        
        for table in tables:
            rows = table.find_all("tr")
            headers = [th.get_text(strip=True) for th in rows[0].find_all("th")] if rows else []
            
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) >= len(headers):
                    item = {}
                    for i, header in enumerate(headers):
                        if i < len(cells):
                            item[header] = cells[i].get_text(strip=True)
                    specification.append(item)
        
        return specification
    
    def _extract_line_items(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract line items from the payments tab.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of line items with details
        """
        line_items = []
        
        # Look for line items in the page
        # This is a simplified example - actual implementation would need to
        # parse the specific HTML structure of zakupki.gov.ru
        
        item_containers = soup.find_all("div", class_="line-item")
        if not item_containers:
            # Try alternative selectors
            item_containers = soup.find_all("tr", class_="item-row")
        
        for container in item_containers:
            item = {
                "name": self._extract_text_from_element(container, ".item-name"),
                "quantity": self._extract_text_from_element(container, ".item-quantity"),
                "unit": self._extract_text_from_element(container, ".item-unit"),
                "price_per_unit": self._extract_text_from_element(container, ".item-price"),
                "total_price": self._extract_text_from_element(container, ".item-total"),
                "characteristics": self._extract_characteristics(container)
            }
            line_items.append(item)
        
        return line_items
    
    def _extract_text_from_element(self, element, selector: str) -> str:
        """
        Extract text from element within another element.
        
        Args:
            element: Parent BeautifulSoup element
            selector: CSS selector
            
        Returns:
            Extracted text or empty string
        """
        child = element.select_one(selector)
        return child.get_text(strip=True) if child else ""
    
    def _extract_characteristics(self, element) -> Dict[str, str]:
        """
        Extract characteristics from a line item element.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            Dictionary of characteristics
        """
        characteristics = {}
        
        # Look for characteristic elements
        char_elements = element.find_all("div", class_="characteristic")
        if not char_elements:
            char_elements = element.find_all("span", class_="char")
        
        for char_elem in char_elements:
            # Try to extract name-value pairs
            text = char_elem.get_text(strip=True)
            if ":" in text:
                name, value = text.split(":", 1)
                characteristics[name.strip()] = value.strip()
            else:
                characteristics[f"char_{len(characteristics)}"] = text
        
        return characteristics
    
    async def _identify_attachments(self, contract_url: str) -> List[Dict[str, str]]:
        """
        Identify available attachments for the contract.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            List of attachment information
        """
        logger.info(f"Identifying attachments: {contract_url}")
        
        try:
            # Navigate to attachments tab or page
            attachments_url = contract_url.replace("common-info.html", "documents.html")
            
            response = await self._make_request(attachments_url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            attachments = []
            
            # Look for attachment links
            attachment_links = soup.find_all("a", href=True)
            
            for link in attachment_links:
                href = link.get("href", "")
                text = link.get_text(strip=True)
                
                # Check if this looks like an attachment
                if any(ext in href.lower() for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]):
                    attachment_type = "document"
                    if "печатная форма" in text.lower() or "printed form" in text.lower():
                        attachment_type = "printed_form"
                    
                    attachments.append({
                        "name": text,
                        "url": urljoin(self.base_url, href),
                        "type": attachment_type,
                        "file_extension": Path(href).suffix.lower()
                    })
            
            return attachments
            
        except Exception as e:
            logger.error(f"Failed to identify attachments: {e}")
            return []
    
    async def _download_printed_form(self, contract_url: str, attachments: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """
        Download the 'Printed Form' (Печатная форма) attachment.
        
        Args:
            contract_url: URL to the contract card
            attachments: List of identified attachments
            
        Returns:
            Dictionary with downloaded file data or None if not found
        """
        # Find printed form attachment
        printed_form = None
        for attachment in attachments:
            if attachment.get("type") == "printed_form":
                printed_form = attachment
                break
        
        if not printed_form:
            logger.warning(f"No printed form found for contract: {contract_url}")
            return None
        
        logger.info(f"Downloading printed form: {printed_form['url']}")
        
        try:
            response = await self._make_request(printed_form["url"])
            
            # Save to temporary file
            file_id = str(uuid.uuid4())
            file_ext = printed_form.get("file_extension", ".pdf")
            temp_file = self.temp_dir / f"{file_id}{file_ext}"
            
            with open(temp_file, "wb") as f:
                f.write(response.content)
            
            # Read file content for processing
            file_content = response.content
            
            return {
                "file_path": str(temp_file),
                "file_name": printed_form["name"],
                "file_size": len(file_content),
                "file_extension": file_ext,
                "content_type": response.headers.get("content-type", ""),
                "content_preview": file_content[:1000] if file_content else b"",  # First 1000 bytes
                "downloaded_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to download printed form: {e}")
            return None
    
    def _extract_contract_year(self, common_info: Dict[str, Any]) -> int:
        """
        Extract contract year from common info.
        
        Args:
            common_info: Common info dictionary
            
        Returns:
            Contract year or current year if not found
        """
        sign_date = common_info.get("sign_date", "")
        
        # Try to extract year from date string
        year_match = re.search(r'\b(20\d{2})\b', sign_date)
        if year_match:
            return int(year_match.group(1))
        
        # Fallback to current year
        return datetime.now().year
    
    def _extract_unit_prices(self, payments_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract unit prices from payments data.
        
        Args:
            payments_data: Payments data dictionary
            
        Returns:
            List of unit prices
        """
        unit_prices = []
        
        # Extract from line items
        for item in payments_data.get("line_items", []):
            price_str = item.get("price_per_unit", "")
            if price_str:
                # Try to parse price
                price_value = self._parse_price(price_str)
                if price_value:
                    unit_prices.append({
                        "item_name": item.get("name", ""),
                        "unit_price": price_value,
                        "currency": self._extract_currency(price_str),
                        "quantity": item.get("quantity", ""),
                        "unit": item.get("unit", "")
                    })
        
        # Also try to extract from specification table
        for spec_item in payments_data.get("specification", []):
            for key, value in spec_item.items():
                if any(term in key.lower() for term in ["цена", "price", "стоимость"]):
                    price_value = self._parse_price(value)
                    if price_value:
                        unit_prices.append({
                            "item_name": spec_item.get("Наименование", ""),
                            "unit_price": price_value,
                            "source": "specification_table",
                            "field_name": key
                        })
        
        return unit_prices
    
    def _parse_price(self, price_str: str) -> Optional[float]:
        """
        Parse price string to float.
        
        Args:
            price_str: Price string
            
        Returns:
            Parsed float value or None if cannot parse
        """
        try:
            # Remove currency symbols and spaces
            cleaned = re.sub(r'[^\d.,]', '', price_str)
            # Replace comma with dot for decimal
            cleaned = cleaned.replace(',', '.')
            # Remove thousand separators
            cleaned = cleaned.replace(' ', '')
            return float(cleaned)
        except (ValueError, AttributeError):
            return None
    
    def _extract_currency(self, price_str: str) -> str:
        """
        Extract currency from price string.
        
        Args:
            price_str: Price string
            
        Returns:
            Currency code (RUB, USD, EUR, etc.) or "RUB" as default
        """
        price_str_lower = price_str.lower()
        if any(curr in price_str_lower for curr in ["usd", "$", "доллар"]):
            return "USD"
        elif any(curr in price_str_lower for curr in ["eur", "€", "евро"]):
            return "EUR"
        elif any(curr in price_str_lower for curr in ["rub", "₽", "руб", "р."]):
            return "RUB"
        else:
            return "RUB"