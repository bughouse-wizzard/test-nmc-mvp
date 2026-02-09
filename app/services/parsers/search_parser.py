"""
Search Results Parser for zakupki.gov.ru
Parses HTML search results and extracts contract information.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlencode

from bs4 import BeautifulSoup


def parse_search_results(html_content: str) -> Tuple[int, List[Dict]]:
    """
    Parse HTML search results from zakupki.gov.ru.
    
    Args:
        html_content: HTML content of search results page
        
    Returns:
        Tuple of (found_total_count, list_of_contracts)
        Each contract dict contains:
        - reestr_number: Registry number
        - contract_url: URL to contract details
        - sign_date: Signing date as datetime object
        - price: Price as float (cleaned from currency symbols)
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Extract total found count
    found_total = _extract_total_count(soup)
    
    # 2. Find contract containers
    contract_elements = soup.select('div.search-registry-entry-block')
    if not contract_elements:
        # Try alternative selectors
        contract_elements = soup.select('div.registry-entry')
    
    contracts = []
    for contract_element in contract_elements:
        contract_data = _parse_contract_element(contract_element)
        if contract_data:
            contracts.append(contract_data)
    
    return found_total, contracts


def _extract_total_count(soup: BeautifulSoup) -> int:
    """Extract total found count from search results header."""
    # Try multiple selectors for total count
    total_selectors = [
        'div.search-results__total',
        'div.search-results-total',
        'div.total-results',
        'span.total-count',
        'div.results-count',
    ]
    
    for selector in total_selectors:
        total_element = soup.select_one(selector)
        if total_element:
            total_text = total_element.get_text(strip=True)
            # Extract number from text like "Найдено: 1 234" or "1 234 найденных записей"
            numbers = re.findall(r'\d[\d\s]*', total_text)
            if numbers:
                # Take the largest number (in case there are multiple)
                largest_number = max(numbers, key=lambda x: int(x.replace(' ', '')))
                return int(largest_number.replace(' ', ''))
    
    return 0


def _parse_contract_element(contract_element) -> Optional[Dict]:
    """Parse individual contract element."""
    try:
        # Extract registry number
        reestr_number = _extract_reestr_number(contract_element)
        if not reestr_number:
            return None
        
        # Extract contract URL
        contract_url = _extract_contract_url(contract_element)
        
        # Extract sign date
        sign_date = _extract_sign_date(contract_element)
        
        # Extract price
        price = _extract_price(contract_element)
        
        return {
            'reestr_number': reestr_number,
            'contract_url': contract_url,
            'sign_date': sign_date,
            'price': price,
        }
    except Exception as e:
        # Log error and skip this contract
        return None


def _extract_reestr_number(contract_element) -> Optional[str]:
    """Extract registry number from contract element."""
    # Try multiple selectors for registry number
    registry_selectors = [
        'a.registry-entry__header-mid__number',
        'div.registry-entry__header-mid__number',
        'span.contract-number',
        'div.contract-id',
        'a[href*="/contract/"]',
        'a[href*="/epz/contract/"]',
    ]
    
    for selector in registry_selectors:
        element = contract_element.select_one(selector)
        if element:
            text = element.get_text(strip=True)
            if text:
                # Clean up the text - remove extra whitespace and newlines
                return re.sub(r'\s+', ' ', text).strip()
    
    return None


def _extract_contract_url(contract_element) -> Optional[str]:
    """Extract contract URL from contract element."""
    # Look for links to contract details
    link_selectors = [
        'a[href*="/contract/"]',
        'a[href*="/epz/contract/"]',
        'a[href*="contractCard/common-info"]',
    ]
    
    base_url = 'https://zakupki.gov.ru'
    
    for selector in link_selectors:
        link = contract_element.select_one(selector)
        if link and link.get('href'):
            href = link.get('href')
            # Make sure URL is absolute
            if href.startswith('/'):
                return urljoin(base_url, href)
            elif href.startswith('http'):
                return href
            else:
                return urljoin(base_url, '/' + href.lstrip('/'))
    
    return None


def _extract_sign_date(contract_element) -> Optional[datetime]:
    """Extract signing date from contract element."""
    # Try multiple selectors for date
    date_selectors = [
        'div.data-block__value',
        'span.contract-date',
        'div.publish-date',
        'time',
        'div.date-value',
    ]
    
    for selector in date_selectors:
        element = contract_element.select_one(selector)
        if element:
            date_text = element.get_text(strip=True)
            if date_text:
                # Try to parse date in DD.MM.YYYY format
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
                if date_match:
                    try:
                        return datetime.strptime(date_match.group(1), '%d.%m.%Y')
                    except ValueError:
                        continue
    
    return None


def _extract_price(contract_element) -> Optional[float]:
    """Extract price from contract element."""
    # Try multiple selectors for price
    price_selectors = [
        'div.price-block__value',
        'span.contract-price',
        'div.price-value',
        'div.amount',
    ]
    
    for selector in price_selectors:
        element = contract_element.select_one(selector)
        if element:
            price_text = element.get_text(strip=True)
            if price_text:
                # Extract numbers and decimal separators
                # Handle formats like "1 234 567,89 руб." or "1,234,567.89"
                # First, normalize decimal separator
                price_text = price_text.replace(',', '.')
                # Remove spaces used as thousand separators
                price_text = price_text.replace(' ', '')
                # Extract all numbers and dots (for decimal)
                # Use regex to find price pattern (digits with optional decimal part)
                price_match = re.search(r'(\d+(?:\.\d+)?)', price_text)
                if price_match:
                    try:
                        return float(price_match.group(1))
                    except ValueError:
                        continue
    
    return None


def build_search_url(params: Dict) -> str:
    """
    Build search URL for zakupki.gov.ru based on user parameters.
    
    Args:
        params: Dictionary with search parameters:
            - region: Region code (e.g., 'SZFO' for Северо-Западный федеральный округ)
            - date_from: Start date in DD.MM.YYYY format
            - date_to: End date in DD.MM.YYYY format
            - law: Procurement law (e.g., '44-ФЗ')
            - ktru: KTRU code
            - status: Execution status (e.g., 'Execution Complete')
            
    Returns:
        Complete URL for search results
    """
    base_url = 'https://zakupki.gov.ru/epz/contract/search/results.html'
    
    # Map parameters to zakupki.gov.ru query parameters
    query_params = {}
    
    # Region mapping (simplified - would need complete mapping in production)
    region_mapping = {
        'SZFO': '78000000000',  # Северо-Западный федеральный округ
        'TSFO': '45000000000',  # Центральный федеральный округ
        'YUFO': '61000000000',  # Южный федеральный округ
        'PFO': '52000000000',   # Приволжский федеральный округ
        'URFO': '66000000000',  # Уральский федеральный округ
        'SFO': '54000000000',   # Сибирский федеральный округ
        'DFO': '27000000000',   # Дальневосточный федеральный округ
    }
    
    if 'region' in params:
        region_code = region_mapping.get(params['region'], '')
        if region_code:
            query_params['regions'] = region_code
    
    # Date range
    if 'date_from' in params:
        query_params['contractDateFrom'] = params['date_from']
    if 'date_to' in params:
        query_params['contractDateTo'] = params['date_to']
    
    # Procurement law
    if 'law' in params:
        law = params['law']
        if law == '44-ФЗ':
            query_params['fz44'] = 'on'
        elif law == '223-ФЗ':
            query_params['fz223'] = 'on'
        elif law == '94-ФЗ':
            query_params['fz94'] = 'on'
    
    # KTRU code
    if 'ktru' in params:
        query_params['ktruCodes'] = params['ktru']
    
    # Execution status
    if 'status' in params:
        status = params['status']
        if status == 'Execution Complete':
            query_params['executionStatus'] = 'EXECUTED'
        elif status == 'In Progress':
            query_params['executionStatus'] = 'EXECUTING'
        elif status == 'Terminated':
            query_params['executionStatus'] = 'TERMINATED'
    
    # Only add default parameters if we have any user parameters
    # or if explicitly requested
    if params:
        # Add pagination and other default parameters
        query_params['pageNumber'] = params.get('page', 1)
        query_params['recordsPerPage'] = params.get('page_size', 50)
        query_params['sortBy'] = 'UPDATE_DATE'
        query_params['sortDirection'] = 'false'  # descending
    
    # Build URL
    if query_params:
        return f"{base_url}?{urlencode(query_params)}"
    return base_url