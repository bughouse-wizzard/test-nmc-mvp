"""
Contract Detail & Attachment Parser for zakupki.gov.ru

This module implements logic to:
1. Fetch the contract common info page (`.../common-info.html`).
2. Navigate to/fetch the 'Payments and Objects of Purchase' tab to extract line items (Specification).
3. Identify attachments. For contracts > 2025 (or as configured), implement logic to download 
   the 'Printed Form' (Печатная форма) PDF/DOCX to a temporary storage or memory buffer for AI processing.
4. Handle extraction of Unit Prices from the structured HTML table if available.
"""

import asyncio
import logging
import os
import re
import tempfile
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, BinaryIO
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
import httpx
import pdfplumber
from docx import Document

logger = logging.getLogger(__name__)


@dataclass
class ContractLineItem:
    """Represents a line item from the contract specification."""
    item_number: str
    name: str
    okpd2_code: Optional[str] = None
    ktru_code: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    manufacturer: Optional[str] = None
    country_of_origin: Optional[str] = None
    additional_info: Optional[str] = None


@dataclass
class ContractAttachment:
    """Represents an attachment from the contract."""
    name: str
    url: str
    file_type: str  # 'pdf', 'docx', 'doc', 'xlsx', etc.
    size: Optional[int] = None
    description: Optional[str] = None
    is_printed_form: bool = False


@dataclass
class ContractInfo:
    """Represents parsed contract information."""
    reestr_number: str
    contract_url: str
    sign_date: datetime
    customer: str
    supplier: str
    total_price: float
    currency: str
    execution_status: str
    line_items: List[ContractLineItem]
    attachments: List[ContractAttachment]
    raw_html: Optional[str] = None
    printed_form_path: Optional[str] = None


class ContractParser:
    """Parser for zakupki.gov.ru contract details and attachments."""
    
    def __init__(
        self,
        base_url: str = "https://zakupki.gov.ru",
        session: Optional[aiohttp.ClientSession] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        temp_dir: Optional[str] = None,
        year_threshold: int = 2025
    ):
        """
        Initialize the contract parser.
        
        Args:
            base_url: Base URL for zakupki.gov.ru
            session: Optional aiohttp ClientSession for HTTP requests
            http_client: Optional httpx AsyncClient for HTTP requests
            temp_dir: Directory for temporary file storage
            year_threshold: Year threshold for downloading printed forms (default: 2025)
        """
        self.base_url = base_url.rstrip('/')
        self.session = session
        self.http_client = http_client
        self.year_threshold = year_threshold
        
        # Create temporary directory if not provided
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix="contract_parser_"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ContractParser initialized with temp_dir: {self.temp_dir}")
    
    async def parse_contract(self, contract_url: str) -> ContractInfo:
        """
        Parse contract details from the given URL.
        
        Args:
            contract_url: URL to the contract common-info.html page
            
        Returns:
            ContractInfo object with parsed contract details
        """
        logger.info(f"Parsing contract from URL: {contract_url}")
        
        # Extract reestr number from URL
        reestr_number = self._extract_reestr_number(contract_url)
        
        # Fetch and parse common info page
        common_info_html = await self._fetch_page(contract_url)
        contract_info = self._parse_common_info(common_info_html, contract_url, reestr_number)
        
        # Try to fetch and parse payments/specifications tab
        try:
            payments_url = self._build_payments_url(contract_url)
            payments_html = await self._fetch_page(payments_url)
            line_items = self._parse_payments_tab(payments_html)
            contract_info.line_items = line_items
        except Exception as e:
            logger.warning(f"Failed to parse payments tab: {e}")
            contract_info.line_items = []
        
        # Identify and process attachments
        try:
            attachments_url = self._build_attachments_url(contract_url)
            attachments_html = await self._fetch_page(attachments_url)
            attachments = self._parse_attachments_tab(attachments_html, contract_url)
            contract_info.attachments = attachments
            
            # Download printed form if contract is from threshold year or later
            if contract_info.sign_date.year >= self.year_threshold:
                printed_form = self._find_printed_form(attachments)
                if printed_form:
                    printed_form_path = await self._download_printed_form(printed_form)
                    contract_info.printed_form_path = printed_form_path
        except Exception as e:
            logger.warning(f"Failed to parse attachments: {e}")
            contract_info.attachments = []
        
        return contract_info
    
    def _extract_reestr_number(self, url: str) -> str:
        """Extract reestr number from contract URL."""
        match = re.search(r'reestrNumber=([^&]+)', url)
        if match:
            return match.group(1)
        raise ValueError(f"Could not extract reestr number from URL: {url}")
    
    def _get_common_info_url(self, url: str) -> str:
        """
        Transform any contract URL to common-info.html format.
        
        Args:
            url: Any contract URL (e.g., document-info.html, payment-info.html, etc.)
            
        Returns:
            URL to the common-info.html page
        """
        # If already a common-info URL, return as-is
        if 'common-info.html' in url:
            return url
        
        # Extract reestr number
        reestr_number = self._extract_reestr_number(url)
        
        # Build common info URL
        return f"{self.base_url}/epz/contract/contractCard/common-info.html?reestrNumber={reestr_number}"
    
    def _extract_contract_year(self, contract_data: Dict[str, Any]) -> int:
        """
        Extract year from contract data.
        
        Args:
            contract_data: Dictionary containing contract information
            
        Returns:
            Extracted year as integer
        """
        # Try to get year from sign_date
        if 'sign_date' in contract_data:
            sign_date = contract_data['sign_date']
            if isinstance(sign_date, datetime):
                return sign_date.year
            elif isinstance(sign_date, str):
                # Try to parse date string
                try:
                    parsed_date = self._parse_date(sign_date)
                    return parsed_date.year
                except:
                    pass
        
        # Try to extract year from URL or other fields
        if 'contract_url' in contract_data:
            url = contract_data['contract_url']
            # Look for year in URL pattern
            year_match = re.search(r'/(\d{4})/', url)
            if year_match:
                return int(year_match.group(1))
        
        # Default to current year if cannot determine
        logger.warning(f"Could not extract year from contract data, using current year")
        return datetime.now().year
    
    async def _fetch_page(self, url: str) -> str:
        """Fetch HTML page content asynchronously."""
        try:
            # Try aiohttp session first
            if self.session:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response.raise_for_status()
                    return await response.text()
            # Fall back to httpx client
            elif self.http_client:
                response = await self.http_client.get(url)
                response.raise_for_status()
                return response.text
            else:
                # Create a temporary httpx client
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text
        except Exception as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise
    
    def _build_payments_url(self, base_url: str) -> str:
        """Build URL for payments/specifications tab."""
        # Replace common-info.html with payments.html or similar pattern
        if 'common-info.html' in base_url:
            return base_url.replace('common-info.html', 'payment-info.html')
        else:
            # Try alternative pattern
            return base_url.replace('common-info', 'payment-info')
    
    def _build_attachments_url(self, base_url: str) -> str:
        """Build URL for attachments tab."""
        if 'common-info.html' in base_url:
            return base_url.replace('common-info.html', 'attachments.html')
        else:
            return base_url.replace('common-info', 'attachments')
    
    def _parse_common_info(self, html: str, url: str, reestr_number: str) -> ContractInfo:
        """Parse common information from contract page."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract basic contract information
        # Note: These selectors are examples and need to be adjusted based on actual HTML structure
        sign_date_str = self._extract_field(soup, 'Дата заключения контракта')
        customer = self._extract_field(soup, 'Заказчик')
        supplier = self._extract_field(soup, 'Поставщик')
        total_price_str = self._extract_field(soup, 'Цена контракта')
        currency = self._extract_field(soup, 'Валюта', default='RUB')
        execution_status = self._extract_field(soup, 'Статус исполнения')
        
        # Parse dates and prices
        sign_date = self._parse_date(sign_date_str)
        total_price = self._parse_price(total_price_str)
        
        return ContractInfo(
            reestr_number=reestr_number,
            contract_url=url,
            sign_date=sign_date,
            customer=customer or 'Не указан',
            supplier=supplier or 'Не указан',
            total_price=total_price or 0.0,
            currency=currency,
            execution_status=execution_status or 'Не указан',
            line_items=[],
            attachments=[],
            raw_html=html
        )
    
    def _parse_payments_tab(self, html: str) -> List[ContractLineItem]:
        """Parse line items from payments/specifications tab."""
        soup = BeautifulSoup(html, 'html.parser')
        line_items = []
        
        # Look for specification tables
        tables = soup.find_all('table', class_=re.compile(r'specification|line-items|payments'))
        
        for table in tables:
            # Try to parse table rows
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 5:  # Minimum cells for a line item
                    try:
                        line_item = self._parse_line_item_row(cells)
                        if line_item:
                            line_items.append(line_item)
                    except Exception as e:
                        logger.debug(f"Failed to parse row: {e}")
        
        return line_items
    
    def _parse_specification(self, html: str) -> List[ContractLineItem]:
        """
        Parse contract specification (line items).
        Alias for _parse_payments_tab for backward compatibility.
        
        Args:
            html: HTML content of specification/payments tab
            
        Returns:
            List of ContractLineItem objects
        """
        return self._parse_payments_tab(html)
    
    def _parse_line_item_row(self, cells: List) -> Optional[ContractLineItem]:
        """Parse a single row into a line item."""
        # This is a simplified parser - actual implementation depends on HTML structure
        try:
            item_number = cells[0].get_text(strip=True) if len(cells) > 0 else ''
            name = cells[1].get_text(strip=True) if len(cells) > 1 else ''
            
            # Try to extract codes
            okpd2_code = None
            ktru_code = None
            code_text = cells[2].get_text(strip=True) if len(cells) > 2 else ''
            if code_text:
                # Look for OKPD2 and KTRU codes
                okpd2_match = re.search(r'OKPD2[:\s]*([\d\.]+)', code_text, re.IGNORECASE)
                ktru_match = re.search(r'KTRU[:\s]*([\d\.\-]+)', code_text, re.IGNORECASE)
                okpd2_code = okpd2_match.group(1) if okpd2_match else None
                ktru_code = ktru_match.group(1) if ktru_match else None
            
            unit = cells[3].get_text(strip=True) if len(cells) > 3 else ''
            quantity_str = cells[4].get_text(strip=True) if len(cells) > 4 else ''
            unit_price_str = cells[5].get_text(strip=True) if len(cells) > 5 else ''
            total_price_str = cells[6].get_text(strip=True) if len(cells) > 6 else ''
            
            # Parse numeric values
            quantity = self._parse_float(quantity_str)
            unit_price = self._parse_price(unit_price_str)
            total_price = self._parse_price(total_price_str)
            
            return ContractLineItem(
                item_number=item_number,
                name=name,
                okpd2_code=okpd2_code,
                ktru_code=ktru_code,
                unit=unit,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price
            )
        except Exception as e:
            logger.debug(f"Failed to parse line item row: {e}")
            return None
    
    def _parse_attachments_tab(self, html: str, base_url: str) -> List[ContractAttachment]:
        """Parse attachments from attachments tab."""
        soup = BeautifulSoup(html, 'html.parser')
        attachments = []
        
        # Look for attachment links
        attachment_links = soup.find_all('a', href=re.compile(r'\.(pdf|docx?|xlsx?)$', re.IGNORECASE))
        
        for link in attachment_links:
            try:
                href = link.get('href', '')
                name = link.get_text(strip=True) or os.path.basename(href)
                
                # Make absolute URL if relative
                if href.startswith('/'):
                    # Extract base domain from base_url
                    domain_match = re.match(r'(https?://[^/]+)', base_url)
                    if domain_match:
                        href = domain_match.group(1) + href
                
                # Determine file type
                file_ext = os.path.splitext(href)[1].lower().lstrip('.')
                if file_ext in ['pdf', 'doc', 'docx', 'xls', 'xlsx']:
                    is_printed_form = 'печатн' in name.lower() or 'printed' in name.lower()
                    
                    attachment = ContractAttachment(
                        name=name,
                        url=href,
                        file_type=file_ext,
                        is_printed_form=is_printed_form
                    )
                    attachments.append(attachment)
            except Exception as e:
                logger.debug(f"Failed to parse attachment link: {e}")
        
        return attachments
    
    def _identify_attachments(self, html: str, base_url: str) -> List[ContractAttachment]:
        """
        Identify and categorize attachments.
        Alias for _parse_attachments_tab for backward compatibility.
        
        Args:
            html: HTML content of attachments tab
            base_url: Base URL for resolving relative links
            
        Returns:
            List of ContractAttachment objects
        """
        return self._parse_attachments_tab(html, base_url)
    
    def _find_printed_form(self, attachments: List[ContractAttachment]) -> Optional[ContractAttachment]:
        """Find printed form among attachments."""
        for attachment in attachments:
            if attachment.is_printed_form:
                return attachment
        
        # If no explicit printed form, look for PDFs
        for attachment in attachments:
            if attachment.file_type == 'pdf':
                return attachment
        
        return None
    
    def _extract_unit_prices(self, line_items: List[ContractLineItem]) -> List[Dict[str, Any]]:
        """
        Extract unit prices from line items.
        
        Args:
            line_items: List of ContractLineItem objects
            
        Returns:
            List of dictionaries with unit price information
        """
        unit_prices = []
        
        for item in line_items:
            if item.unit_price is not None:
                unit_price_info = {
                    'item_number': item.item_number,
                    'name': item.name,
                    'unit': item.unit,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'total_price': item.total_price,
                    'okpd2_code': item.okpd2_code,
                    'ktru_code': item.ktru_code
                }
                unit_prices.append(unit_price_info)
        
        return unit_prices
    
    async def _download_printed_form(self, attachment: ContractAttachment) -> str:
        """Download printed form to temporary storage asynchronously."""
        try:
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f'.{attachment.file_type}',
                dir=self.temp_dir,
                delete=False
            )
            
            # Download content asynchronously
            if self.session:
                async with self.session.get(attachment.url) as response:
                    response.raise_for_status()
                    # Write content in chunks
                    with open(temp_file.name, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
            elif self.http_client:
                async with self.http_client.stream('GET', attachment.url) as response:
                    response.raise_for_status()
                    with open(temp_file.name, 'wb') as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)
            else:
                async with httpx.AsyncClient() as client:
                    async with client.stream('GET', attachment.url) as response:
                        response.raise_for_status()
                        with open(temp_file.name, 'wb') as f:
                            async for chunk in response.aiter_bytes():
                                f.write(chunk)
            
            temp_file.close()
            logger.info(f"Downloaded printed form to: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Failed to download printed form: {e}")
            raise
    
    def _extract_field(self, soup: BeautifulSoup, field_name: str, default: str = None) -> Optional[str]:
        """Extract field value by label name."""
        # Look for label containing field name
        label = soup.find(lambda tag: tag.name in ['span', 'div', 'td'] and 
                         field_name.lower() in tag.get_text(strip=True).lower())
        
        if label:
            # Try to find associated value
            parent = label.parent
            if parent:
                # Look for value in sibling or next element
                for sibling in parent.find_all(['span', 'div', 'td']):
                    if sibling != label and sibling.get_text(strip=True):
                        return sibling.get_text(strip=True)
        
        return default
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        if not date_str:
            return datetime.now()
        
        # Try common date formats
        formats = ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y']
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        # If all fail, return current date
        logger.warning(f"Could not parse date: {date_str}")
        return datetime.now()
    
    def _parse_price(self, price_str: str) -> Optional[float]:
        """Parse price string to float."""
        if not price_str:
            return None
        
        # Remove currency symbols and spaces (keep digits and commas)
        cleaned = re.sub(r'[^\d,]', '', price_str.strip())
        # Replace comma with dot for decimal
        cleaned = cleaned.replace(',', '.')
        
        try:
            return float(cleaned)
        except ValueError:
            logger.debug(f"Could not parse price: {price_str}")
            return None
    
    def _extract_currency(self, price_str: str) -> str:
        """
        Extract currency from price string.
        
        Args:
            price_str: Price string (e.g., "100 USD", "200 €", "300 РУБ")
            
        Returns:
            Currency code (USD, EUR, RUB)
        """
        if not price_str:
            return "RUB"  # Default currency
        
        price_str_upper = price_str.upper()
        
        # Check for currency indicators
        if "USD" in price_str_upper or "$" in price_str:
            return "USD"
        elif "EUR" in price_str_upper or "€" in price_str:
            return "EUR"
        elif "RUB" in price_str_upper or "РУБ" in price_str_upper or "₽" in price_str or "РУБ." in price_str_upper:
            return "RUB"
        elif "RUR" in price_str_upper:  # Old Russian ruble code
            return "RUB"
        
        # Default to RUB for Russian procurement
        return "RUB"
    
    def _parse_float(self, value_str: str) -> Optional[float]:
        """Parse any float value."""
        return self._parse_price(value_str)
    
    def extract_text_from_printed_form(self, file_path: str) -> str:
        """
        Extract text from printed form (PDF or DOCX).
        
        Args:
            file_path: Path to the printed form file
            
        Returns:
            Extracted text content
        """
        if not os.path.exists(file_path):
            return ""
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_ext in ['.doc', '.docx']:
                return self._extract_text_from_docx(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_ext}")
                return ""
        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
            return ""
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file."""
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    
    def _extract_text_from_docx(self, docx_path: str) -> str:
        """Extract text from DOCX file."""
        doc = Document(docx_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    
    def cleanup_temp_files(self, file_paths: List[str]):
        """
        Clean up temporary files.
        
        Args:
            file_paths: List of file paths to delete
        """
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.debug(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file {file_path}: {e}")
    
    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from URL.
        Alias for _fetch_page for backward compatibility.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
        """
        return await self._fetch_page(url)
    
    async def _download_file(self, url: str, file_path: str) -> str:
        """
        Download file from URL.
        Simplified version for backward compatibility.
        
        Args:
            url: URL to download from
            file_path: Path to save the file
            
        Returns:
            Path to downloaded file
        """
        # Create a temporary attachment object
        from urllib.parse import urlparse
        file_name = os.path.basename(urlparse(url).path)
        file_ext = os.path.splitext(file_name)[1].lstrip('.')
        
        temp_attachment = ContractAttachment(
            name=file_name,
            url=url,
            file_type=file_ext,
            is_printed_form=False
        )
        
        # Use existing download logic
        return await self._download_printed_form(temp_attachment)
    
    async def cleanup(self):
        """Clean up temporary files and resources."""
        try:
            # Remove temporary directory and all its contents
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Error cleaning up temp directory: {e}")


# Factory function for easier usage
async def create_contract_parser(
    base_url: str = "https://zakupki.gov.ru",
    temp_dir: Optional[str] = None,
    year_threshold: int = 2025
) -> ContractParser:
    """
    Create a ContractParser instance with proper HTTP client.

    Args:
        base_url: Base URL for zakupki.gov.ru
        temp_dir: Directory for temporary file storage
        year_threshold: Year threshold for downloading printed forms

    Returns:
        ContractParser instance
    """
    # Create HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }
    )

    return ContractParser(
        base_url=base_url,
        http_client=http_client,
        temp_dir=temp_dir,
        year_threshold=year_threshold
    )
