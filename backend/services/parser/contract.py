"""
Contract Detail & Attachment Parser for zakupki.gov.ru contracts.

This module implements logic to:
1. Fetch the contract common info page (.../common-info.html)
2. Navigate to/fetch the 'Payments and Objects of Purchase' tab to extract line items (Specification)
3. Identify attachments
4. For contracts > 2025 (or as configured), download the 'Printed Form' (Печатная форма) PDF/DOCX
5. Handle extraction of Unit Prices from structured HTML tables
"""

import asyncio
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, BinaryIO
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)


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
    
    async def parse_contract(self, contract_url: str) -> Dict[str, Any]:
        """
        Parse contract details from the given URL.
        
        Args:
            contract_url: URL to the contract card on zakupki.gov.ru
            
        Returns:
            Dictionary containing parsed contract data including:
            - common_info: Basic contract information
            - specification: Line items from 'Payments and Objects of Purchase' tab
            - attachments: List of attachments
            - printed_form: Information about downloaded printed form (if applicable)
            - unit_prices: Extracted unit prices
        """
        logger.info(f"Parsing contract: {contract_url}")
        
        result = {
            "contract_url": contract_url,
            "common_info": {},
            "specification": [],
            "attachments": [],
            "printed_form": None,
            "unit_prices": [],
            "parsed_at": datetime.utcnow().isoformat()
        }
        
        try:
            # 1. Fetch and parse common info page
            common_info_url = self._get_common_info_url(contract_url)
            result["common_info"] = await self._parse_common_info(common_info_url)
            
            # 2. Extract specification from 'Payments and Objects of Purchase' tab
            result["specification"] = await self._parse_specification(contract_url)
            
            # 3. Identify attachments
            result["attachments"] = await self._identify_attachments(contract_url)
            
            # 4. Check if contract is from year > threshold and download printed form
            contract_year = self._extract_contract_year(result["common_info"])
            if contract_year and contract_year >= self.year_threshold:
                result["printed_form"] = await self._download_printed_form(contract_url)
            
            # 5. Extract unit prices from HTML tables
            result["unit_prices"] = await self._extract_unit_prices(contract_url)
            
            logger.info(f"Successfully parsed contract: {contract_url}")
            
        except Exception as e:
            logger.error(f"Error parsing contract {contract_url}: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result
    
    def _get_common_info_url(self, contract_url: str) -> str:
        """
        Construct the common info page URL from contract URL.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            URL to the common info page
        """
        # Remove trailing slash if present
        contract_url = contract_url.rstrip('/')
        
        # Check if URL already ends with common-info.html
        if contract_url.endswith('common-info.html'):
            return contract_url
        
        # Check if URL contains common-info.html somewhere in the path
        if 'common-info.html' in contract_url:
            # Extract the base URL before common-info.html
            parts = contract_url.split('common-info.html')
            return parts[0] + 'common-info.html'
        
        # Otherwise, append /common-info.html
        return f"{contract_url}/common-info.html"
    
    async def _parse_common_info(self, common_info_url: str) -> Dict[str, Any]:
        """
        Fetch and parse the contract common info page.
        
        Args:
            common_info_url: URL to the common info page
            
        Returns:
            Dictionary with parsed common information
        """
        logger.info(f"Fetching common info from: {common_info_url}")
        
        html_content = await self._fetch_html(common_info_url)
        soup = BeautifulSoup(html_content, 'lxml')
        
        common_info = {}
        
        # Extract basic contract information
        # This is a simplified example - actual parsing would depend on the HTML structure
        try:
            # Extract contract number
            contract_number_elem = soup.find('span', {'class': 'cardMainInfo__purchaseLink'})
            if contract_number_elem:
                common_info['contract_number'] = contract_number_elem.text.strip()
            
            # Extract contract date
            date_elem = soup.find('div', {'class': 'cardMainInfo__purchaseDate'})
            if date_elem:
                common_info['sign_date'] = date_elem.text.strip()
            
            # Extract customer information
            customer_elem = soup.find('div', {'class': 'cardMainInfo__customer'})
            if customer_elem:
                common_info['customer'] = customer_elem.text.strip()
            
            # Extract supplier information
            supplier_elem = soup.find('div', {'class': 'cardMainInfo__supplier'})
            if supplier_elem:
                common_info['supplier'] = supplier_elem.text.strip()
            
            # Extract contract price
            price_elem = soup.find('div', {'class': 'cardMainInfo__price'})
            if price_elem:
                common_info['total_price'] = price_elem.text.strip()
            
            # Extract additional fields based on actual HTML structure
            # This would need to be adapted to the real website structure
            
        except Exception as e:
            logger.warning(f"Error parsing common info: {e}")
        
        return common_info
    
    async def _parse_specification(self, contract_url: str) -> List[Dict[str, Any]]:
        """
        Parse specification (line items) from 'Payments and Objects of Purchase' tab.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            List of specification line items
        """
        logger.info(f"Parsing specification for contract: {contract_url}")
        
        # Construct URL for the specification tab
        # This URL pattern might need adjustment based on actual website structure
        spec_url = contract_url.rstrip('/') + "/payment-objects.html"
        
        try:
            html_content = await self._fetch_html(spec_url)
            soup = BeautifulSoup(html_content, 'lxml')
            
            specification = []
            
            # Find specification table
            # This selector would need to be adjusted based on actual HTML structure
            table = soup.find('table', {'class': 'specification-table'})
            
            if not table:
                # Try alternative table selectors
                table = soup.find('table', {'id': 'paymentObjectsTable'})
            
            if table:
                # Extract table rows
                rows = table.find_all('tr')
                
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all('td')
                    
                    if len(cells) >= 4:  # Adjust based on actual column count
                        item = {
                            'position': cells[0].text.strip() if len(cells) > 0 else '',
                            'name': cells[1].text.strip() if len(cells) > 1 else '',
                            'quantity': cells[2].text.strip() if len(cells) > 2 else '',
                            'unit_price': cells[3].text.strip() if len(cells) > 3 else '',
                            'total_price': cells[4].text.strip() if len(cells) > 4 else '',
                        }
                        specification.append(item)
            
            return specification
            
        except Exception as e:
            logger.warning(f"Error parsing specification: {e}")
            return []
    
    async def _identify_attachments(self, contract_url: str) -> List[Dict[str, Any]]:
        """
        Identify attachments in the contract.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            List of attachments with metadata
        """
        logger.info(f"Identifying attachments for contract: {contract_url}")
        
        # Construct URL for attachments page
        attachments_url = contract_url.rstrip('/') + "/documents.html"
        
        try:
            html_content = await self._fetch_html(attachments_url)
            soup = BeautifulSoup(html_content, 'lxml')
            
            attachments = []
            
            # Find attachment links
            # This selector would need to be adjusted based on actual HTML structure
            attachment_links = soup.find_all('a', {'class': 'document-link'})
            
            for link in attachment_links:
                href = link.get('href', '')
                text = link.text.strip()
                
                if href and (href.endswith('.pdf') or href.endswith('.doc') or href.endswith('.docx')):
                    attachment = {
                        'name': text,
                        'url': urljoin(self.base_url, href),
                        'file_type': href.split('.')[-1].lower(),
                        'size': None  # Would need additional parsing for file size
                    }
                    attachments.append(attachment)
            
            return attachments
            
        except Exception as e:
            logger.warning(f"Error identifying attachments: {e}")
            return []
    
    async def _download_printed_form(self, contract_url: str) -> Optional[Dict[str, Any]]:
        """
        Download the 'Printed Form' (Печатная форма) for contracts after threshold year.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            Dictionary with printed form information and file path, or None if not found
        """
        logger.info(f"Downloading printed form for contract: {contract_url}")
        
        try:
            # First, find the printed form link
            attachments = await self._identify_attachments(contract_url)
            
            printed_form_attachments = [
                att for att in attachments 
                if 'печатная форма' in att['name'].lower() or 'printed form' in att['name'].lower()
            ]
            
            if not printed_form_attachments:
                logger.warning(f"No printed form found for contract: {contract_url}")
                return None
            
            # Download the first printed form attachment
            printed_form = printed_form_attachments[0]
            file_url = printed_form['url']
            
            # Download the file
            file_content = await self._download_file(file_url)
            
            if file_content:
                # Save to temporary file
                file_ext = printed_form['file_type']
                temp_file = self.temp_dir / f"printed_form_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}"
                
                with open(temp_file, 'wb') as f:
                    f.write(file_content)
                
                printed_form_info = {
                    'name': printed_form['name'],
                    'url': file_url,
                    'file_type': file_ext,
                    'file_path': str(temp_file),
                    'file_size': len(file_content),
                    'downloaded_at': datetime.utcnow().isoformat()
                }
                
                logger.info(f"Downloaded printed form to: {temp_file}")
                return printed_form_info
            
        except Exception as e:
            logger.error(f"Error downloading printed form: {e}")
        
        return None
    
    async def _extract_unit_prices(self, contract_url: str) -> List[Dict[str, Any]]:
        """
        Extract unit prices from structured HTML tables.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            List of unit prices with metadata
        """
        logger.info(f"Extracting unit prices for contract: {contract_url}")
        
        # First, get specification which may contain unit prices
        specification = await self._parse_specification(contract_url)
        
        unit_prices = []
        
        for item in specification:
            if item.get('unit_price'):
                try:
                    # Clean and parse unit price
                    price_str = item['unit_price']
                    # Remove non-numeric characters except decimal point
                    price_clean = ''.join(c for c in price_str if c.isdigit() or c == '.' or c == ',')
                    # Replace comma with dot for decimal parsing
                    price_clean = price_clean.replace(',', '.')
                    
                    if price_clean:
                        unit_price = {
                            'item_name': item.get('name', ''),
                            'position': item.get('position', ''),
                            'price_value': float(price_clean),
                            'currency': self._extract_currency(price_str),
                            'quantity': item.get('quantity', ''),
                            'total_price': item.get('total_price', '')
                        }
                        unit_prices.append(unit_price)
                        
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing unit price '{item.get('unit_price')}': {e}")
        
        return unit_prices
    
    def _extract_contract_year(self, common_info: Dict[str, Any]) -> Optional[int]:
        """
        Extract contract year from common information.
        
        Args:
            common_info: Dictionary with parsed common information
            
        Returns:
            Contract year as integer, or None if cannot be extracted
        """
        sign_date = common_info.get('sign_date', '')
        
        # Try to extract year from date string
        import re
        year_match = re.search(r'\b(20\d{2})\b', sign_date)
        
        if year_match:
            try:
                return int(year_match.group(1))
            except (ValueError, TypeError):
                pass
        
        return None
    
    def _extract_currency(self, price_str: str) -> str:
        """
        Extract currency from price string.
        
        Args:
            price_str: Price string
            
        Returns:
            Currency code (default: 'RUB')
        """
        price_str_upper = price_str.upper()
        
        if 'USD' in price_str_upper or '$' in price_str:
            return 'USD'
        elif 'EUR' in price_str_upper or '€' in price_str:
            return 'EUR'
        elif 'RUB' in price_str_upper or 'РУБ' in price_str_upper or '₽' in price_str:
            return 'RUB'
        
        return 'RUB'  # Default to RUB
    
    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
        """
        try:
            if self.http_client:
                response = await self.http_client.get(url)
                response.raise_for_status()
                return response.text
            elif self.session:
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    return await response.text()
            else:
                # Create a temporary client
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.text
                    
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            raise
    
    async def _download_file(self, url: str) -> Optional[bytes]:
        """
        Download file from URL.
        
        Args:
            url: URL to download
            
        Returns:
            File content as bytes, or None if download fails
        """
        try:
            if self.http_client:
                response = await self.http_client.get(url)
                response.raise_for_status()
                return response.content
            elif self.session:
                async with self.session.get(url) as response:
                    response.raise_for_status()
                    return await response.read()
            else:
                # Create a temporary client
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.content
                    
        except Exception as e:
            logger.error(f"Error downloading file {url}: {e}")
            return None
    
    async def cleanup(self):
        """Clean up temporary files."""
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