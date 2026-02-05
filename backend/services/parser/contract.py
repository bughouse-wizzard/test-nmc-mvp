"""
Contract parser for extracting data from zakupki.gov.ru contract cards.
Implements logic to fetch contract pages, extract specification data,
identify attachments, and download printed forms for contracts > 2025.
"""
import asyncio
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse

import aiohttp
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class ContractParser:
    """Parser for zakupki.gov.ru contract cards."""
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """
        Initialize contract parser.
        
        Args:
            session: Optional aiohttp ClientSession for HTTP requests
        """
        self.base_url = settings.ZAKUPKI_BASE_URL
        self.timeout = settings.REQUEST_TIMEOUT
        self.max_retries = settings.MAX_RETRIES
        self.crawl_delay = settings.CRAWL_DELAY
        
        self._session = session
        self._temp_files = []  # Track temporary files for cleanup
        
    async def __aenter__(self):
        """Async context manager entry."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
        # Clean up temporary files
        for temp_file in self._temp_files:
            try:
                if Path(temp_file).exists():
                    Path(temp_file).unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_file}: {e}")
    
    async def _make_request(self, url: str, method: str = "GET", **kwargs) -> str:
        """
        Make HTTP request with retry logic.
        
        Args:
            url: URL to request
            method: HTTP method
            **kwargs: Additional arguments for aiohttp request
            
        Returns:
            Response text content
            
        Raises:
            aiohttp.ClientError: If request fails after retries
        """
        for attempt in range(self.max_retries):
            try:
                async with self._session.request(method, url, **kwargs) as response:
                    response.raise_for_status()
                    content = await response.text()
                    
                    # Respect crawl delay
                    if self.crawl_delay > 0:
                        await asyncio.sleep(self.crawl_delay)
                    
                    return content
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Request failed after {self.max_retries} attempts: {e}")
                    raise
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    async def parse_contract(self, contract_url: str) -> Dict[str, Any]:
        """
        Parse contract data from zakupki.gov.ru.
        
        Args:
            contract_url: URL to contract card
            
        Returns:
            Dictionary with parsed contract data
        """
        logger.info(f"Parsing contract: {contract_url}")
        
        # Extract reestr number from URL
        reestr_number = self._extract_reestr_number(contract_url)
        
        # Fetch common info page
        common_info_html = await self._fetch_common_info(contract_url)
        common_info = await self._parse_common_info(common_info_html, contract_url)
        
        # Fetch payments and objects tab
        payments_html = await self._fetch_payments_tab(contract_url)
        specification = await self._parse_specification(payments_html)
        
        # Identify attachments
        attachments = await self._identify_attachments(common_info_html)
        
        # Check if contract is 2025 or later
        sign_date = common_info.get('sign_date')
        is_2025_plus = self._is_2025_plus_contract(sign_date)
        
        # Download printed form if contract is 2025+
        printed_form_data = None
        if is_2025_plus and attachments.get('printed_form'):
            printed_form_data = await self._download_printed_form(
                attachments['printed_form']
            )
        
        # Extract unit prices
        unit_prices = self._extract_unit_prices(specification)
        
        return {
            'reestr_number': reestr_number,
            'contract_url': contract_url,
            'common_info': common_info,
            'specification': specification,
            'attachments': attachments,
            'is_2025_plus': is_2025_plus,
            'printed_form_data': printed_form_data,
            'unit_prices': unit_prices,
            'parsed_at': datetime.utcnow().isoformat()
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
        parsed = urlparse(contract_url)
        query_params = dict(param.split('=') for param in parsed.query.split('&') if '=' in param)
        return query_params.get('reestrNumber', '')
    
    async def _fetch_common_info(self, contract_url: str) -> str:
        """
        Fetch contract common info page.
        
        Args:
            contract_url: Contract URL
            
        Returns:
            HTML content of common info page
        """
        # Ensure URL ends with common-info.html
        if not contract_url.endswith('common-info.html'):
            # Construct common info URL from base contract URL
            base_url = contract_url.split('?')[0] if '?' in contract_url else contract_url
            base_url = base_url.rstrip('/')
            contract_url = f"{base_url}/common-info.html?{contract_url.split('?')[1]}" if '?' in contract_url else f"{base_url}/common-info.html"
        
        logger.debug(f"Fetching common info from: {contract_url}")
        return await self._make_request(contract_url)
    
    async def _parse_common_info(self, html: str, contract_url: str) -> Dict[str, Any]:
        """
        Parse common info page data.
        
        Args:
            html: HTML content of common info page
            contract_url: Original contract URL
            
        Returns:
            Dictionary with common info data
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract basic contract information
        # This is a simplified implementation - actual parsing would need
        # to be adapted to the specific HTML structure of zakupki.gov.ru
        
        common_info = {
            'sign_date': None,
            'contract_price': None,
            'customer': None,
            'supplier': None,
            'status': None,
            'execution_status': None,
        }
        
        # Try to find sign date
        # Look for elements containing "Дата заключения" or similar
        sign_date_elements = soup.find_all(text=lambda t: 'дата заключения' in t.lower() if t else False)
        for element in sign_date_elements:
            parent = element.parent
            if parent:
                # Try to find date in sibling or parent elements
                date_text = parent.find_next(text=True)
                if date_text:
                    try:
                        # Try to parse date
                        date_str = date_text.strip()
                        # Simple date parsing - would need more robust implementation
                        common_info['sign_date'] = date_str
                        break
                    except:
                        continue
        
        # Try to find contract price
        price_elements = soup.find_all(text=lambda t: 'цена контракта' in t.lower() if t else False)
        for element in price_elements:
            parent = element.parent
            if parent:
                price_text = parent.find_next(text=True)
                if price_text:
                    try:
                        # Extract numeric value
                        import re
                        price_match = re.search(r'[\d\s,\.]+', price_text)
                        if price_match:
                            price_str = price_match.group().replace(' ', '').replace(',', '.')
                            common_info['contract_price'] = float(price_str)
                        break
                    except:
                        continue
        
        # Extract customer and supplier information
        # Look for tables or divs with organization information
        org_tables = soup.find_all('table')
        for table in org_tables:
            table_text = table.get_text().lower()
            if 'заказчик' in table_text:
                # Extract customer info
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2 and 'наименование' in cells[0].get_text().lower():
                        common_info['customer'] = cells[1].get_text().strip()
                        break
            elif 'поставщик' in table_text or 'исполнитель' in table_text:
                # Extract supplier info
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2 and 'наименование' in cells[0].get_text().lower():
                        common_info['supplier'] = cells[1].get_text().strip()
                        break
        
        return common_info
    
    async def _fetch_payments_tab(self, contract_url: str) -> str:
        """
        Fetch 'Payments and Objects of Purchase' tab content.
        
        Args:
            contract_url: Contract URL
            
        Returns:
            HTML content of payments tab
        """
        # Construct payments tab URL
        base_url = contract_url.split('?')[0] if '?' in contract_url else contract_url
        base_url = base_url.rstrip('/').replace('/common-info.html', '')
        
        # Try different possible URL patterns for payments tab
        payments_urls = [
            f"{base_url}/payment.html?{contract_url.split('?')[1]}" if '?' in contract_url else f"{base_url}/payment.html",
            f"{base_url}/payments.html?{contract_url.split('?')[1]}" if '?' in contract_url else f"{base_url}/payments.html",
            f"{base_url}/objects.html?{contract_url.split('?')[1]}" if '?' in contract_url else f"{base_url}/objects.html",
        ]
        
        for url in payments_urls:
            try:
                logger.debug(f"Trying payments tab URL: {url}")
                html = await self._make_request(url)
                # Check if page contains relevant content
                if 'платеж' in html.lower() or 'объект' in html.lower():
                    return html
            except aiohttp.ClientError:
                continue
        
        # If no payments tab found, return empty string
        logger.warning(f"Could not find payments tab for contract: {contract_url}")
        return ""
    
    async def _parse_specification(self, html: str) -> List[Dict[str, Any]]:
        """
        Parse specification (line items) from payments tab.
        
        Args:
            html: HTML content of payments tab
            
        Returns:
            List of specification items
        """
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        specification = []
        
        # Look for tables containing specification data
        tables = soup.find_all('table')
        
        for table in tables:
            table_text = table.get_text().lower()
            
            # Check if this table contains specification data
            spec_keywords = ['наименование', 'количество', 'цена', 'ед. изм.', 'стоимость']
            if any(keyword in table_text for keyword in spec_keywords):
                # Parse table rows
                rows = table.find_all('tr')
                headers = []
                
                # Extract headers from first row
                if rows:
                    header_cells = rows[0].find_all(['th', 'td'])
                    headers = [cell.get_text().strip().lower() for cell in header_cells]
                
                # Process data rows
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all('td')
                    if len(cells) >= len(headers):
                        item = {}
                        for i, cell in enumerate(cells):
                            if i < len(headers):
                                header = headers[i]
                                value = cell.get_text().strip()
                                item[header] = value
                        
                        if item:  # Only add if we have data
                            specification.append(item)
        
        return specification
    
    async def _identify_attachments(self, html: str) -> Dict[str, Any]:
        """
        Identify attachments in contract.
        
        Args:
            html: HTML content of common info page
            
        Returns:
            Dictionary with attachment information
        """
        soup = BeautifulSoup(html, 'lxml')
        attachments = {
            'printed_form': None,
            'other_attachments': []
        }
        
        # Look for attachment links
        attachment_links = soup.find_all('a', href=True)
        
        for link in attachment_links:
            link_text = link.get_text().lower()
            href = link['href']
            
            # Check for printed form
            if 'печатная форма' in link_text or 'printed form' in link_text.lower():
                attachments['printed_form'] = href
            # Check for other attachments
            elif any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']):
                attachments['other_attachments'].append({
                    'name': link_text,
                    'url': href
                })
        
        return attachments
    
    def _is_2025_plus_contract(self, sign_date: Optional[str]) -> bool:
        """
        Check if contract is from 2025 or later.
        
        Args:
            sign_date: Contract sign date string
            
        Returns:
            True if contract is from 2025 or later
        """
        if not sign_date:
            return False
        
        try:
            # Try to extract year from date string
            import re
            year_match = re.search(r'(\d{4})', sign_date)
            if year_match:
                year = int(year_match.group(1))
                return year >= 2025
        except:
            pass
        
        return False
    
    async def _download_printed_form(self, printed_form_url: str) -> Dict[str, Any]:
        """
        Download printed form document.
        
        Args:
            printed_form_url: URL to printed form document
            
        Returns:
            Dictionary with document data and metadata
        """
        logger.info(f"Downloading printed form: {printed_form_url}")
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_path = temp_file.name
        self._temp_files.append(temp_path)
        temp_file.close()
        
        try:
            # Download file
            async with self._session.get(printed_form_url) as response:
                response.raise_for_status()
                
                # Save to temporary file
                with open(temp_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                
                # Extract text based on file type
                file_ext = Path(printed_form_url).suffix.lower()
                text_content = ""
                
                if file_ext == '.pdf':
                    text_content = self._extract_text_from_pdf(temp_path)
                elif file_ext in ['.doc', '.docx']:
                    text_content = self._extract_text_from_docx(temp_path)
                else:
                    # Try to read as text
                    try:
                        with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text_content = f.read()
                    except:
                        text_content = ""
                
                return {
                    'url': printed_form_url,
                    'local_path': temp_path,
                    'file_size': Path(temp_path).stat().st_size,
                    'text_content': text_content[:10000],  # Limit text size
                    'downloaded_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to download printed form: {e}")
            # Clean up temp file on error
            try:
                Path(temp_path).unlink()
                self._temp_files.remove(temp_path)
            except:
                pass
            return None
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            return ""
    
    def _extract_text_from_docx(self, docx_path: str) -> str:
        """
        Extract text from DOCX file.
        
        Args:
            docx_path: Path to DOCX file
            
        Returns:
            Extracted text
        """
        try:
            doc = Document(docx_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from DOCX: {e}")
            return ""
    
    def _extract_unit_prices(self, specification: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract unit prices from specification.
        
        Args:
            specification: List of specification items
            
        Returns:
            List of unit prices with metadata
        """
        unit_prices = []
        
        for item in specification:
            # Look for price-related fields
            price_fields = ['цена', 'цена за единицу', 'цена, руб.', 'стоимость', 'unit price']
            
            for field in price_fields:
                if field in item:
                    price_str = item[field]
                    try:
                        # Clean and parse price
                        import re
                        # Remove non-numeric characters except decimal point
                        price_clean = re.sub(r'[^\d,\.]', '', price_str)
                        price_clean = price_clean.replace(',', '.')
                        
                        if price_clean:
                            price = float(price_clean)
                            
                            # Get related information
                            unit_price_item = {
                                'price': price,
                                'currency': 'RUB',  # Default, could be extracted
                                'item_name': item.get('наименование', ''),
                                'quantity': item.get('количество', ''),
                                'unit': item.get('ед. изм.', ''),
                                'total': item.get('стоимость', ''),
                                'source_field': field
                            }
                            unit_prices.append(unit_price_item)
                            break
                    except (ValueError, TypeError):
                        continue
        
        return unit_prices