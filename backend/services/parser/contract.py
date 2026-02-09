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
    
    def parse_common_info(self, html: str) -> Dict[str, Any]:
        """
        Extract basic fields from common info HTML.
        
        Args:
            html: HTML content of the common info page
            
        Returns:
            Dictionary with extracted basic fields
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract basic contract information
        reestr_number = self._extract_field(soup, 'Реестровый номер')
        sign_date_str = self._extract_field(soup, 'Дата заключения контракта')
        customer = self._extract_field(soup, 'Заказчик')
        supplier = self._extract_field(soup, 'Поставщик')
        total_price_str = self._extract_field(soup, 'Цена контракта')
        currency = self._extract_field(soup, 'Валюта', default='RUB')
        execution_status = self._extract_field(soup, 'Статус исполнения')
        
        # Parse dates and prices
        sign_date = self._parse_date(sign_date_str) if sign_date_str else None
        total_price = self._parse_price(total_price_str) if total_price_str else None
        
        return {
            'reestr_number': reestr_number,
            'sign_date': sign_date,
            'customer': customer,
            'supplier': supplier,
            'total_price': total_price,
            'currency': currency,
            'execution_status': execution_status,
            'raw_html': html
        }
    
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
    
    def parse_objects_tab(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse objects tab to extract product information.
        
        Args:
            html: HTML content of the objects/payments tab
            
        Returns:
            List of dictionaries with extracted product information including characteristics
        """
        soup = BeautifulSoup(html, 'html.parser')
        products = []
        
        # Look for specification tables - try multiple possible table classes/ids
        tables = soup.find_all('table', class_=re.compile(r'specification|line-items|payments|products|objects'))
        if not tables:
            # Try to find any table that might contain product information
            tables = soup.find_all('table')
        
        for table in tables:
            # Check if this looks like a products table by examining headers
            headers = table.find_all('th')
            header_texts = [h.get_text(strip=True).lower() for h in headers]
            
            # Check for product-related headers
            product_keywords = ['наименование', 'name', 'объект', 'product', 'товар']
            if any(keyword in ' '.join(header_texts) for keyword in product_keywords):
                products.extend(self._parse_products_table(table))
        
        return products
    
    def _parse_products_table(self, table) -> List[Dict[str, Any]]:
        """Parse a products table to extract product information with characteristics."""
        products = []
        rows = table.find_all('tr')
        current_product = None
        
        for i, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            
            # Skip header rows
            if all(cell.name == 'th' for cell in cells):
                continue
            
            # Check if this is a product row (has enough cells and contains product data)
            if len(cells) >= 5 and not self._is_characteristics_row(row):
                # Parse product row
                product_data = self._parse_product_row(cells)
                if product_data:
                    current_product = product_data
                    products.append(current_product)
            
            # Check if this is a characteristics row (follows a product row)
            elif self._is_characteristics_row(row):
                if current_product:
                    characteristics = self._extract_characteristics(row)
                    current_product['characteristics'] = characteristics
        
        return products
    
    def _is_characteristics_row(self, row) -> bool:
        """Check if a row contains characteristics data."""
        row_text = row.get_text(strip=True).lower()
        characteristics_keywords = ['характеристик', 'characteristic', 'описание', 'description', 'техническ']
        return any(keyword in row_text for keyword in characteristics_keywords)
    
    def _parse_product_row(self, cells: List) -> Optional[Dict[str, Any]]:
        """Parse a product row into a dictionary."""
        try:
            # Extract data from cells based on expected positions
            item_number = cells[0].get_text(strip=True) if len(cells) > 0 else ''
            name = cells[1].get_text(strip=True) if len(cells) > 1 else ''
            
            # Extract OKPD2/KTRU codes
            okpd2_code = None
            ktru_code = None
            if len(cells) > 2:
                code_text = cells[2].get_text(strip=True)
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
            
            return {
                'item_number': item_number,
                'name': name,
                'okpd2_code': okpd2_code,
                'ktru_code': ktru_code,
                'unit': unit,
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price,
                'characteristics': None  # Will be filled by characteristics row
            }
        except Exception as e:
            logger.debug(f"Failed to parse product row: {e}")
            return None
    
    def _extract_characteristics(self, row) -> str:
        """Extract characteristics text from a row."""
        try:
            # Get all text from the row, excluding table structure
            text_parts = []
            for element in row.find_all(['td', 'div', 'span', 'p', 'ul', 'li']):
                text = element.get_text(strip=True)
                if text and len(text) > 3:  # Filter out very short text
                    text_parts.append(text)
            
            # Join with newlines for readability
            return '\n'.join(text_parts)
        except Exception as e:
            logger.debug(f"Failed to extract characteristics: {e}")
            return ""
    
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
    
    def parse_attachments_list(self, html: str, base_url: str = "") -> List[Dict[str, Any]]:
        """
        Parse attachments list from HTML and filter for important documents.
        
        Args:
            html: HTML content of the attachments tab
            base_url: Base URL for resolving relative links
            
        Returns:
            List of dictionaries with attachment information, filtered for important documents
        """
        soup = BeautifulSoup(html, 'html.parser')
        attachments = []
        
        # Look for all links that might be attachments
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            try:
                href = link.get('href', '')
                name = link.get_text(strip=True) or os.path.basename(href)
                
                # Skip empty links or non-document links
                if not href or not self._is_document_link(href):
                    continue
                
                # Make absolute URL if relative
                if base_url and href.startswith('/'):
                    # Extract base domain from base_url
                    domain_match = re.match(r'(https?://[^/]+)', base_url)
                    if domain_match:
                        href = domain_match.group(1) + href
                elif base_url and not href.startswith(('http://', 'https://')):
                    # Handle relative paths
                    href = urljoin(base_url, href)
                
                # Determine file type
                file_ext = os.path.splitext(href)[1].lower().lstrip('.')
                
                # Check if this is an important document based on keywords
                name_lower = name.lower()
                is_important = False
                document_type = 'other'
                
                # Check for specific document types
                if any(keyword in name_lower for keyword in ['печатн', 'printed', 'print form']):
                    is_important = True
                    document_type = 'printed_form'
                elif any(keyword in name_lower for keyword in ['техническ', 'technical', 'тз', 'specification']):
                    is_important = True
                    document_type = 'technical_specification'
                elif any(keyword in name_lower for keyword in ['спецификац', 'specification']):
                    is_important = True
                    document_type = 'specification'
                elif any(keyword in name_lower for keyword in ['контракт', 'contract', 'договор']):
                    is_important = True
                    document_type = 'contract'
                
                # Get file size if available (look in sibling elements)
                file_size = self._extract_file_size(link)
                
                attachment = {
                    'name': name,
                    'url': href,
                    'file_type': file_ext,
                    'file_size': file_size,
                    'document_type': document_type,
                    'is_important': is_important,
                    'download_url': href
                }
                attachments.append(attachment)
                
            except Exception as e:
                logger.debug(f"Failed to parse attachment link: {e}")
        
        # Sort by importance (important documents first)
        attachments.sort(key=lambda x: (not x['is_important'], x['name']))
        
        return attachments
    
    def _is_document_link(self, href: str) -> bool:
        """Check if a link points to a document file."""
        document_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.rtf', '.txt', '.odt', '.ods']
        href_lower = href.lower()
        return any(href_lower.endswith(ext) for ext in document_extensions) or 'download' in href_lower
    
    def _extract_file_size(self, link_element) -> Optional[str]:
        """Extract file size from link element or nearby elements."""
        try:
            # Look in the parent row for file size information
            parent_row = link_element.find_parent('tr')
            if parent_row:
                # Look for cells that might contain size information
                cells = parent_row.find_all(['td', 'div', 'span'])
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    # Look for size patterns like "2.5 МБ", "1.8 MB", "1024 KB"
                    size_match = re.search(r'(\d+[\.,]?\d*)\s*(МБ|MB|КБ|KB|ГБ|GB|байт|bytes?)', cell_text, re.IGNORECASE)
                    if size_match:
                        return f"{size_match.group(1)} {size_match.group(2)}"
            
            # Check sibling elements
            for sibling in link_element.find_next_siblings():
                sibling_text = sibling.get_text(strip=True)
                size_match = re.search(r'(\d+[\.,]?\d*)\s*(МБ|MB|КБ|KB|ГБ|GB)', sibling_text, re.IGNORECASE)
                if size_match:
                    return f"{size_match.group(1)} {size_match.group(2)}"
                    
        except Exception as e:
            logger.debug(f"Failed to extract file size: {e}")
        
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
    
    def is_contract_2025_or_later(self, contract_date: Optional[datetime]) -> bool:
        """
        Check if contract is from 2025 or later.
        
        Args:
            contract_date: Contract sign date
            
        Returns:
            True if contract is from 2025 or later, False otherwise
        """
        if not contract_date:
            return False
        
        return contract_date.year >= self.year_threshold
    
    def prioritize_print_form_extraction(self, attachments: List[Dict[str, Any]], 
                                         contract_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Prioritize print form extraction based on contract date.
        
        Args:
            attachments: List of attachment dictionaries
            contract_date: Contract sign date (optional)
            
        Returns:
            Filtered and prioritized list of attachments
        """
        if not attachments:
            return []
        
        # If contract date is provided and contract is 2025+, prioritize printed forms
        if contract_date and self.is_contract_2025_or_later(contract_date):
            # Find printed forms
            printed_forms = [a for a in attachments if a.get('document_type') == 'printed_form']
            
            # If we found printed forms, return them first
            if printed_forms:
                # Sort printed forms by relevance
                printed_forms.sort(key=lambda x: (
                    'печатн' in x.get('name', '').lower(),
                    'pdf' in x.get('file_type', '').lower()
                ), reverse=True)
                
                # Add other important documents after printed forms
                other_important = [a for a in attachments if a.get('is_important') and a.get('document_type') != 'printed_form']
                other_docs = [a for a in attachments if not a.get('is_important')]
                
                return printed_forms + other_important + other_docs
        
        # For older contracts or no date, just sort by importance
        return sorted(attachments, key=lambda x: (not x.get('is_important', False), x.get('name', '')))
    
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
        # Try different strategies to find the field
        
        # Strategy 1: Look for label with class 'label' containing field name
        label = soup.find('span', class_='label', string=lambda text: text and field_name.lower() in text.lower())
        if not label:
            # Also try without colon
            label = soup.find('span', class_='label', string=lambda text: text and field_name.lower() in text.lower().rstrip(':'))
        
        if label:
            # Find the value span next to it
            parent = label.parent
            if parent:
                value_span = parent.find('span', class_='value')
                if value_span:
                    return value_span.get_text(strip=True)
        
        # Strategy 2: Look for any element containing field name
        label = soup.find(lambda tag: tag.name in ['span', 'div', 'td', 'th'] and 
                         field_name.lower() in tag.get_text(strip=True).lower())
        
        if label:
            # Try to find associated value
            parent = label.parent
            if parent:
                # Look for value in sibling elements
                for sibling in parent.find_all(['span', 'div', 'td']):
                    if sibling != label and sibling.get_text(strip=True):
                        sibling_text = sibling.get_text(strip=True)
                        # Check if this looks like a value (not another label)
                        if len(sibling_text) > 0 and not any(
                            kw in sibling_text.lower() for kw in 
                            ['реестровый', 'дата', 'заказчик', 'поставщик', 'цена', 'валюта', 'статус']
                        ):
                            return sibling_text
        
        # Strategy 3: Search in info rows
        info_rows = soup.find_all(['div', 'tr'], class_=lambda x: x and 'info' in x.lower() or 'row' in x.lower())
        for row in info_rows:
            row_text = row.get_text(strip=True)
            if field_name.lower() in row_text.lower():
                # Extract value after field name
                parts = row_text.split(':', 1)
                if len(parts) > 1:
                    value = parts[1].strip()
                    # Remove currency symbols and extra spaces
                    value = value.replace('₽', '').replace('€', '').replace('$', '').strip()
                    return value if value else None
        
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
