"""
Contract parser for extracting data from zakupki.gov.ru contract pages.
Implements logic to fetch contract details, specifications, and attachments.
"""

import asyncio
import io
import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, BinaryIO
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ContractAttachment(BaseModel):
    """Model for contract attachments."""
    name: str
    url: str
    file_type: str  # pdf, docx, xlsx, etc.
    size_bytes: Optional[int] = None
    description: Optional[str] = None


class ContractSpecificationItem(BaseModel):
    """Model for specification line items."""
    item_number: str
    name: str
    okpd2_code: Optional[str] = None
    ktru_code: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    currency: str = "RUB"
    additional_info: Optional[str] = None


class ContractCommonInfo(BaseModel):
    """Model for contract common information."""
    reestr_number: str
    contract_url: str
    sign_date: Optional[datetime] = None
    customer_name: Optional[str] = None
    supplier_name: Optional[str] = None
    contract_price: Optional[float] = None
    currency: str = "RUB"
    contract_status: Optional[str] = None
    execution_status: Optional[str] = None
    law_type: Optional[str] = None  # 44-ФЗ, 223-ФЗ, etc.


class ContractParseResult(BaseModel):
    """Result of contract parsing."""
    common_info: ContractCommonInfo
    specifications: List[ContractSpecificationItem] = Field(default_factory=list)
    attachments: List[ContractAttachment] = Field(default_factory=list)
    printed_form_content: Optional[bytes] = None  # Binary content of printed form
    printed_form_type: Optional[str] = None  # pdf, docx, etc.
    raw_html: Dict[str, str] = Field(default_factory=dict)  # Raw HTML for debugging
    errors: List[str] = Field(default_factory=list)


class ContractParser:
    """
    Parser for extracting contract data from zakupki.gov.ru.
    
    Features:
    1. Fetch contract common info page (/common-info.html)
    2. Navigate to 'Payments and Objects of Purchase' tab for specifications
    3. Identify and categorize attachments
    4. Download 'Printed Form' for contracts > 2025
    5. Extract unit prices from HTML tables
    """
    
    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: int = 30,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ):
        """
        Initialize the contract parser.
        
        Args:
            session: Optional aiohttp session (will create one if not provided)
            timeout: Request timeout in seconds
            user_agent: User agent string for requests
        """
        self._session = session
        self.timeout = timeout
        self.user_agent = user_agent
        self.base_headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
        }
        
    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(headers=self.base_headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def parse_contract(self, contract_url: str) -> ContractParseResult:
        """
        Main method to parse a contract from its URL.
        
        Args:
            contract_url: URL to the contract card on zakupki.gov.ru
            
        Returns:
            ContractParseResult with all extracted data
        """
        errors = []
        raw_html = {}
        
        try:
            # 1. Fetch and parse common info page
            common_info_url = self._ensure_common_info_url(contract_url)
            logger.info(f"Fetching common info from: {common_info_url}")
            
            common_info_html = await self._fetch_html(common_info_url)
            raw_html["common_info"] = common_info_html
            
            common_info = await self._parse_common_info(common_info_html, contract_url)
            
            # 2. Fetch and parse specifications from payments tab
            specifications = []
            try:
                payments_url = self._get_payments_tab_url(contract_url)
                payments_html = await self._fetch_html(payments_url)
                raw_html["payments"] = payments_html
                
                specifications = await self._parse_specifications(payments_html)
            except Exception as e:
                error_msg = f"Failed to parse specifications: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
            
            # 3. Identify attachments
            attachments = []
            try:
                attachments = await self._identify_attachments(common_info_html, contract_url)
            except Exception as e:
                error_msg = f"Failed to identify attachments: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
            
            # 4. Download printed form for contracts > 2025
            printed_form_content = None
            printed_form_type = None
            
            if common_info.sign_date and common_info.sign_date.year >= 2025:
                try:
                    printed_form_content, printed_form_type = await self._download_printed_form(
                        common_info_html, contract_url
                    )
                except Exception as e:
                    error_msg = f"Failed to download printed form: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
            
            return ContractParseResult(
                common_info=common_info,
                specifications=specifications,
                attachments=attachments,
                printed_form_content=printed_form_content,
                printed_form_type=printed_form_type,
                raw_html=raw_html,
                errors=errors
            )
            
        except Exception as e:
            error_msg = f"Failed to parse contract: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            # Return minimal result with errors
            return ContractParseResult(
                common_info=ContractCommonInfo(
                    reestr_number="UNKNOWN",
                    contract_url=contract_url
                ),
                errors=errors
            )
    
    def _ensure_common_info_url(self, contract_url: str) -> str:
        """Ensure URL points to common-info.html page."""
        parsed = urlparse(contract_url)
        path = parsed.path
        
        if path.endswith("/common-info.html"):
            return contract_url
        
        # Remove trailing slash if present
        if path.endswith("/"):
            path = path[:-1]
        
        # Append /common-info.html
        new_path = f"{path}/common-info.html"
        return urljoin(contract_url, new_path)
    
    def _get_payments_tab_url(self, contract_url: str) -> str:
        """Get URL for payments and objects of purchase tab."""
        parsed = urlparse(contract_url)
        path = parsed.path
        
        # Remove trailing slash if present
        if path.endswith("/"):
            path = path[:-1]
        
        # Append /payments.html (typical pattern for payments tab)
        new_path = f"{path}/payments.html"
        return urljoin(contract_url, new_path)
    
    async def _fetch_html(self, url: str) -> str:
        """Fetch HTML content from URL."""
        if not self._session:
            self._session = aiohttp.ClientSession(headers=self.base_headers)
        
        async with self._session.get(url, timeout=self.timeout) as response:
            response.raise_for_status()
            return await response.text()
    
    async def _parse_common_info(self, html: str, contract_url: str) -> ContractCommonInfo:
        """
        Parse common information from contract page.
        
        Extracts:
        - Registry number
        - Sign date
        - Customer name
        - Supplier name
        - Contract price
        - Status information
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract registry number - typically in a span with class or in title
        reestr_number = "UNKNOWN"
        reestr_elem = soup.find('span', class_=re.compile('registry-number|reestr', re.I))
        if reestr_elem:
            reestr_number = reestr_elem.get_text(strip=True)
        else:
            # Try to find in page title or headings
            title_elem = soup.find('h1') or soup.find('title')
            if title_elem:
                text = title_elem.get_text()
                # Look for pattern like "№ 12345678901234567890"
                match = re.search(r'№\s*([\d\-]+)', text)
                if match:
                    reestr_number = match.group(1)
        
        # Extract sign date
        sign_date = None
        date_elem = soup.find('td', class_=re.compile('sign-date|date', re.I))
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            try:
                # Try different date formats
                for fmt in ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y']:
                    try:
                        sign_date = datetime.strptime(date_text, fmt)
                        break
                    except ValueError:
                        continue
            except Exception:
                pass
        
        # Extract customer and supplier names
        customer_name = None
        supplier_name = None
        
        # Look for tables with customer/supplier information
        tables = soup.find_all('table')
        for table in tables:
            table_text = table.get_text().lower()
            if 'заказчик' in table_text:
                # Try to extract customer name
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2 and 'заказчик' in cells[0].get_text().lower():
                        customer_name = cells[1].get_text(strip=True)
                        break
            
            if 'поставщик' in table_text or 'исполнитель' in table_text:
                # Try to extract supplier name
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2 and ('поставщик' in cells[0].get_text().lower() or 
                                           'исполнитель' in cells[0].get_text().lower()):
                        supplier_name = cells[1].get_text(strip=True)
                        break
        
        # Extract contract price
        contract_price = None
        price_elem = soup.find('td', class_=re.compile('price|sum|стоимость', re.I))
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            # Extract numeric value
            match = re.search(r'[\d\s,]+\.?\d*', price_text.replace(',', '.'))
            if match:
                try:
                    # Remove spaces and convert to float
                    price_str = match.group().replace(' ', '').replace(',', '.')
                    contract_price = float(price_str)
                except ValueError:
                    pass
        
        # Extract contract status
        contract_status = None
        status_elem = soup.find('span', class_=re.compile('status', re.I))
        if status_elem:
            contract_status = status_elem.get_text(strip=True)
        
        # Extract execution status
        execution_status = None
        exec_elem = soup.find('td', class_=re.compile('execution|исполнение', re.I))
        if exec_elem:
            execution_status = exec_elem.get_text(strip=True)
        
        # Determine law type (44-ФЗ, 223-ФЗ, etc.)
        law_type = None
        law_elem = soup.find('td', class_=re.compile('law|закон', re.I))
        if law_elem:
            law_type = law_elem.get_text(strip=True)
        else:
            # Try to infer from URL or page content
            page_text = soup.get_text().lower()
            if '44-фз' in page_text:
                law_type = '44-ФЗ'
            elif '223-фз' in page_text:
                law_type = '223-ФЗ'
        
        return ContractCommonInfo(
            reestr_number=reestr_number,
            contract_url=contract_url,
            sign_date=sign_date,
            customer_name=customer_name,
            supplier_name=supplier_name,
            contract_price=contract_price,
            contract_status=contract_status,
            execution_status=execution_status,
            law_type=law_type
        )
    
    async def _parse_specifications(self, html: str) -> List[ContractSpecificationItem]:
        """
        Parse specification items from payments/objects of purchase tab.
        
        Looks for HTML tables with line items and extracts:
        - Item number
        - Name/description
        - OKPD2/KTRU codes
        - Unit
        - Quantity
        - Unit price
        - Total price
        """
        soup = BeautifulSoup(html, 'lxml')
        items = []
        
        # Find all tables that might contain specification data
        tables = soup.find_all('table')
        
        for table in tables:
            # Check if table looks like a specification table
            table_text = table.get_text().lower()
            if not any(keyword in table_text for keyword in ['позиция', 'наименование', 'ед.', 'количество', 'цена']):
                continue
            
            # Extract rows
            rows = table.find_all('tr')
            if len(rows) < 2:  # Need at least header and one data row
                continue
            
            # Try to identify column indices
            headers = rows[0].find_all(['th', 'td'])
            header_texts = [h.get_text(strip=True).lower() for h in headers]
            
            col_indices = {
                'item_num': self._find_column_index(header_texts, ['№', 'позиция', 'номер']),
                'name': self._find_column_index(header_texts, ['наименование', 'описание', 'предмет']),
                'okpd2': self._find_column_index(header_texts, ['окпд2', 'код окпд2']),
                'ktru': self._find_column_index(header_texts, ['ктру', 'код ктру']),
                'unit': self._find_column_index(header_texts, ['ед.', 'единица', 'ед изм']),
                'quantity': self._find_column_index(header_texts, ['количество', 'кол-во']),
                'unit_price': self._find_column_index(header_texts, ['цена', 'цена за ед.', 'цена единицы']),
                'total_price': self._find_column_index(header_texts, ['сумма', 'стоимость', 'всего']),
            }
            
            # Process data rows (skip header)
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < max(idx for idx in col_indices.values() if idx is not None):
                    continue
                
                # Extract data based on column indices
                item_data = {}
                for field, idx in col_indices.items():
                    if idx is not None and idx < len(cells):
                        item_data[field] = cells[idx].get_text(strip=True)
                
                # Create specification item if we have at least a name
                if 'name' in item_data and item_data['name']:
                    spec_item = self._create_specification_item(item_data)
                    if spec_item:
                        items.append(spec_item)
        
        return items
    
    def _find_column_index(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index by matching keywords in header texts."""
        for i, header in enumerate(headers):
            if any(keyword in header for keyword in keywords):
                return i
        return None
    
    def _create_specification_item(self, item_data: Dict[str, str]) -> Optional[ContractSpecificationItem]:
        """Create ContractSpecificationItem from parsed data."""
        try:
            # Parse numeric values
            quantity = None
            if 'quantity' in item_data and item_data['quantity']:
                try:
                    quantity = float(item_data['quantity'].replace(',', '.').replace(' ', ''))
                except ValueError:
                    pass
            
            unit_price = None
            if 'unit_price' in item_data and item_data['unit_price']:
                try:
                    # Extract numeric value from price string
                    price_text = item_data['unit_price']
                    match = re.search(r'[\d\s,]+\.?\d*', price_text.replace(',', '.'))
                    if match:
                        price_str = match.group().replace(' ', '').replace(',', '.')
                        unit_price = float(price_str)
                except ValueError:
                    pass
            
            total_price = None
            if 'total_price' in item_data and item_data['total_price']:
                try:
                    price_text = item_data['total_price']
                    match = re.search(r'[\d\s,]+\.?\d*', price_text.replace(',', '.'))
                    if match:
                        price_str = match.group().replace(' ', '').replace(',', '.')
                        total_price = float(price_str)
                except ValueError:
                    pass
            
            # Get item number (default to empty string if not found)
            item_number = item_data.get('item_num', '')
            
            return ContractSpecificationItem(
                item_number=item_number,
                name=item_data.get('name', ''),
                okpd2_code=item_data.get('okpd2'),
                ktru_code=item_data.get('ktru'),
                unit=item_data.get('unit'),
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                additional_info=None
            )
        except Exception as e:
            logger.warning(f"Failed to create specification item: {str(e)}")
            return None
    
    async def _identify_attachments(self, html: str, base_url: str) -> List[ContractAttachment]:
        """
        Identify attachments from contract page.
        
        Looks for:
        - Links to PDF, DOCX, XLSX files
        - Attachment tables or sections
        - 'Printed Form' (Печатная форма) links
        """
        soup = BeautifulSoup(html, 'lxml')
        attachments = []
        
        # Find all links that might be attachments
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link['href']
            link_text = link.get_text(strip=True).lower()
            
            # Check if link points to a document file
            if self._is_document_link(href):
                # Determine file type from extension
                file_type = self._get_file_type_from_url(href)
                if not file_type:
                    continue
                
                # Build absolute URL
                attachment_url = urljoin(base_url, href)
                
                # Get attachment name from link text or URL
                name = link.get_text(strip=True)
                if not name or name == href:
                    # Extract name from URL
                    name = Path(urlparse(href).path).stem
                    if not name:
                        name = f"attachment_{len(attachments) + 1}"
                
                # Check if this is a printed form
                is_printed_form = any(keyword in link_text for keyword in [
                    'печатная форма', 'печатная', 'printed form', 'форма'
                ])
                
                attachment = ContractAttachment(
                    name=name,
                    url=attachment_url,
                    file_type=file_type,
                    description="Printed Form" if is_printed_form else None
                )
                attachments.append(attachment)
        
        return attachments
    
    def _is_document_link(self, url: str) -> bool:
        """Check if URL points to a document file."""
        doc_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.rtf', '.odt', '.ods']
        url_lower = url.lower()
        return any(url_lower.endswith(ext) for ext in doc_extensions)
    
    def _get_file_type_from_url(self, url: str) -> Optional[str]:
        """Extract file type from URL extension."""
        url_lower = url.lower()
        if url_lower.endswith('.pdf'):
            return 'pdf'
        elif url_lower.endswith('.doc') or url_lower.endswith('.docx'):
            return 'docx'
        elif url_lower.endswith('.xls') or url_lower.endswith('.xlsx'):
            return 'xlsx'
        elif url_lower.endswith('.rtf'):
            return 'rtf'
        elif url_lower.endswith('.odt'):
            return 'odt'
        elif url_lower.endswith('.ods'):
            return 'ods'
        return None
    
    async def _download_printed_form(self, html: str, base_url: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Download the 'Printed Form' (Печатная форма) document.
        
        Args:
            html: HTML content of contract page
            base_url: Base URL for resolving relative links
            
        Returns:
            Tuple of (content_bytes, file_type) or (None, None) if not found
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Find printed form links
        printed_form_links = []
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link['href']
            link_text = link.get_text(strip=True).lower()
            
            # Check if this is a printed form link
            if any(keyword in link_text for keyword in ['печатная форма', 'печатная', 'printed form']):
                if self._is_document_link(href):
                    printed_form_links.append((href, link))
        
        if not printed_form_links:
            logger.warning("No printed form links found")
            return None, None
        
        # Try to download the first printed form link
        printed_form_url, link_element = printed_form_links[0]
        absolute_url = urljoin(base_url, printed_form_url)
        
        try:
            logger.info(f"Downloading printed form from: {absolute_url}")
            
            if not self._session:
                self._session = aiohttp.ClientSession(headers=self.base_headers)
            
            async with self._session.get(absolute_url, timeout=self.timeout) as response:
                response.raise_for_status()
                
                # Get content type
                content_type = response.headers.get('Content-Type', '').lower()
                file_type = self._get_file_type_from_url(absolute_url)
                
                if not file_type and 'pdf' in content_type:
                    file_type = 'pdf'
                elif not file_type and ('word' in content_type or 'doc' in content_type):
                    file_type = 'docx'
                elif not file_type and ('excel' in content_type or 'sheet' in content_type):
                    file_type = 'xlsx'
                
                # Read content
                content = await response.read()
                
                logger.info(f"Downloaded printed form: {len(content)} bytes, type: {file_type}")
                return content, file_type
                
        except Exception as e:
            logger.error(f"Failed to download printed form: {str(e)}")
            return None, None