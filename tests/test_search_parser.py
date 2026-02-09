"""
Unit tests for search_parser module.
"""

import os
from datetime import datetime
from pathlib import Path

import pytest

from app.services.parsers.search_parser import parse_search_results, build_search_url


def load_fixture(filename: str) -> str:
    """Load HTML fixture from tests/fixtures directory."""
    fixture_path = Path(__file__).parent / 'fixtures' / filename
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return f.read()


class TestParseSearchResults:
    """Test parse_search_results function."""
    
    def test_parse_search_results_total_count(self):
        """Test that total count is extracted correctly."""
        html = load_fixture('search_results.html')
        total_count, contracts = parse_search_results(html)
        
        assert total_count == 15
        assert isinstance(total_count, int)
    
    def test_parse_search_results_contract_count(self):
        """Test that all contracts are extracted."""
        html = load_fixture('search_results.html')
        total_count, contracts = parse_search_results(html)
        
        # Should extract 10+ items as specified in requirements
        assert len(contracts) >= 10
        assert len(contracts) == 15  # We have 15 contracts in the fixture
    
    def test_parse_search_results_contract_structure(self):
        """Test that each contract has the required fields."""
        html = load_fixture('search_results.html')
        total_count, contracts = parse_search_results(html)
        
        for contract in contracts:
            assert 'reestr_number' in contract
            assert 'contract_url' in contract
            assert 'sign_date' in contract
            assert 'price' in contract
            
            # Check field types
            assert isinstance(contract['reestr_number'], str)
            assert isinstance(contract['contract_url'], str)
            assert contract['sign_date'] is None or isinstance(contract['sign_date'], datetime)
            assert contract['price'] is None or isinstance(contract['price'], float)
    
    def test_parse_search_results_reestr_numbers(self):
        """Test that registry numbers are extracted correctly."""
        html = load_fixture('search_results.html')
        total_count, contracts = parse_search_results(html)
        
        # Check first few contracts
        expected_numbers = [
            '12345678901234567890',
            '23456789012345678901',
            '34567890123456789012',
        ]
        
        for i, expected in enumerate(expected_numbers):
            if i < len(contracts):
                assert contracts[i]['reestr_number'] == expected
    
    def test_parse_search_results_contract_urls(self):
        """Test that contract URLs are extracted correctly."""
        html = load_fixture('search_results.html')
        total_count, contracts = parse_search_results(html)
        
        for contract in contracts:
            assert contract['contract_url'] is not None
            assert contract['contract_url'].startswith('https://zakupki.gov.ru')
            assert 'contractCard/common-info' in contract['contract_url']
            assert 'reestrNumber=' in contract['contract_url']
    
    def test_parse_search_results_sign_dates(self):
        """Test that sign dates are extracted and parsed correctly."""
        html = load_fixture('search_results.html')
        total_count, contracts = parse_search_results(html)
        
        # Check dates for first few contracts
        expected_dates = [
            datetime(2024, 1, 15),
            datetime(2024, 1, 20),
            datetime(2024, 1, 25),
        ]
        
        for i, expected in enumerate(expected_dates):
            if i < len(contracts):
                assert contracts[i]['sign_date'] == expected
    
    def test_parse_search_results_prices(self):
        """Test that prices are extracted and cleaned correctly."""
        html = load_fixture('search_results.html')
        total_count, contracts = parse_search_results(html)
        
        # Check prices for first few contracts
        expected_prices = [
            1234567.89,
            987654.32,
            555555.55,
        ]
        
        for i, expected in enumerate(expected_prices):
            if i < len(contracts):
                assert contracts[i]['price'] == pytest.approx(expected, rel=1e-9)
    
    def test_parse_search_results_empty_html(self):
        """Test parsing empty HTML."""
        total_count, contracts = parse_search_results('')
        
        assert total_count == 0
        assert len(contracts) == 0
    
    def test_parse_search_results_no_contracts(self):
        """Test parsing HTML without contract elements."""
        html = '<html><body><div>No contracts here</div></body></html>'
        total_count, contracts = parse_search_results(html)
        
        assert total_count == 0
        assert len(contracts) == 0
    
    def test_parse_search_results_malformed_html(self):
        """Test parsing malformed HTML."""
        html = '<div>This is not valid HTML<div>'
        total_count, contracts = parse_search_results(html)
        
        # Should not crash
        assert total_count == 0
        assert len(contracts) == 0


class TestBuildSearchUrl:
    """Test build_search_url function."""
    
    def test_build_search_url_basic(self):
        """Test building URL with basic parameters."""
        params = {
            'region': 'SZFO',
            'date_from': '01.01.2024',
            'date_to': '31.12.2024',
            'law': '44-ФЗ',
            'ktru': '1234567890',
            'status': 'Execution Complete',
        }
        
        url = build_search_url(params)
        
        assert url.startswith('https://zakupki.gov.ru/epz/contract/search/results.html?')
        assert 'regions=78000000000' in url  # SZFO region code
        assert 'contractDateFrom=01.01.2024' in url
        assert 'contractDateTo=31.12.2024' in url
        assert 'fz44=on' in url
        assert 'ktruCodes=1234567890' in url
        assert 'executionStatus=EXECUTED' in url
        assert 'pageNumber=1' in url
        assert 'recordsPerPage=50' in url
    
    def test_build_search_url_different_law(self):
        """Test building URL with different procurement law."""
        params = {
            'law': '223-ФЗ',
        }
        
        url = build_search_url(params)
        assert 'fz223=on' in url
    
    def test_build_search_url_different_status(self):
        """Test building URL with different execution status."""
        params = {
            'status': 'In Progress',
        }
        
        url = build_search_url(params)
        assert 'executionStatus=EXECUTING' in url
    
    def test_build_search_url_pagination(self):
        """Test building URL with custom pagination."""
        params = {
            'page': 2,
            'page_size': 100,
        }
        
        url = build_search_url(params)
        assert 'pageNumber=2' in url
        assert 'recordsPerPage=100' in url
    
    def test_build_search_url_unknown_region(self):
        """Test building URL with unknown region."""
        params = {
            'region': 'UNKNOWN_REGION',
        }
        
        url = build_search_url(params)
        # Should not include regions parameter for unknown region
        assert 'regions=' not in url
    
    def test_build_search_url_empty_params(self):
        """Test building URL with empty parameters."""
        url = build_search_url({})
        
        # Should return base URL without query parameters
        assert url == 'https://zakupki.gov.ru/epz/contract/search/results.html'
    
    def test_build_search_url_partial_params(self):
        """Test building URL with partial parameters."""
        params = {
            'date_from': '01.01.2024',
            'date_to': '31.12.2024',
        }
        
        url = build_search_url(params)
        assert 'contractDateFrom=01.01.2024' in url
        assert 'contractDateTo=31.12.2024' in url
        assert 'pageNumber=1' in url  # Default values should be included
    
    def test_build_search_url_special_characters(self):
        """Test building URL with special characters in parameters."""
        params = {
            'ktru': '123-456/789',
        }
        
        url = build_search_url(params)
        # Special characters should be properly encoded
        assert 'ktruCodes=123-456%2F789' in url or 'ktruCodes=123-456/789' in url


if __name__ == '__main__':
    pytest.main([__file__, '-v'])