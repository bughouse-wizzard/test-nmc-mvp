"""
Tests for the Contract Parser module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from backend.services.parser.contract import ContractParser


class TestContractParser:
    """Test suite for ContractParser class."""
    
    def test_init(self):
        """Test parser initialization."""
        parser = ContractParser()
        assert parser.base_url == "https://zakupki.gov.ru"
        assert parser.timeout == 30
        assert parser.max_retries == 3
        assert parser.crawl_delay == 60
        
        # Test custom initialization
        parser = ContractParser(
            base_url="http://test.url",
            timeout=10,
            max_retries=2,
            crawl_delay=5
        )
        assert parser.base_url == "http://test.url"
        assert parser.timeout == 10
        assert parser.max_retries == 2
        assert parser.crawl_delay == 5
    
    def test_extract_reestr_number(self):
        """Test reestr number extraction from URL."""
        parser = ContractParser()
        
        # Test valid URL with reestrNumber parameter
        url = "https://zakupki.gov.ru/contractCard/common-info.html?reestrNumber=1234567890"
        result = parser._extract_reestr_number(url)
        assert result == "1234567890"
        
        # Test URL without reestrNumber parameter
        url = "https://zakupki.gov.ru/contractCard/common-info.html"
        result = parser._extract_reestr_number(url)
        assert result == ""
        
        # Test URL with multiple parameters
        url = "https://zakupki.gov.ru/contractCard/common-info.html?reestrNumber=123&other=param"
        result = parser._extract_reestr_number(url)
        assert result == "123"
    
    def test_extract_text(self):
        """Test text extraction from BeautifulSoup."""
        from bs4 import BeautifulSoup
        
        parser = ContractParser()
        
        # Create test HTML
        html = """
        <html>
            <div class="contract-number">CONTRACT-123</div>
            <div class="sign-date">2024-01-15</div>
        </html>
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Test existing element
        result = parser._extract_text(soup, ".contract-number")
        assert result == "CONTRACT-123"
        
        # Test non-existing element
        result = parser._extract_text(soup, ".non-existing")
        assert result == ""
    
    def test_extract_text_from_element(self):
        """Test text extraction from element within another element."""
        from bs4 import BeautifulSoup
        
        parser = ContractParser()
        
        # Create test HTML
        html = """
        <div class="line-item">
            <span class="item-name">Test Item</span>
            <span class="item-quantity">10</span>
        </div>
        """
        soup = BeautifulSoup(html, 'lxml')
        element = soup.find("div", class_="line-item")
        
        # Test existing child element
        result = parser._extract_text_from_element(element, ".item-name")
        assert result == "Test Item"
        
        # Test non-existing child element
        result = parser._extract_text_from_element(element, ".non-existing")
        assert result == ""
    
    def test_extract_characteristics(self):
        """Test characteristics extraction."""
        from bs4 import BeautifulSoup
        
        parser = ContractParser()
        
        # Test with colon-separated characteristics
        html = """
        <div>
            <div class="characteristic">Color: Red</div>
            <div class="characteristic">Size: Large</div>
            <div class="characteristic">Weight: 10kg</div>
        </div>
        """
        soup = BeautifulSoup(html, 'lxml')
        element = soup.find("div")
        
        result = parser._extract_characteristics(element)
        assert result == {
            "Color": "Red",
            "Size": "Large",
            "Weight": "10kg"
        }
        
        # Test without colon (fallback to numbered keys)
        html = """
        <div>
            <span class="char">Some characteristic</span>
            <span class="char">Another one</span>
        </div>
        """
        soup = BeautifulSoup(html, 'lxml')
        element = soup.find("div")
        
        result = parser._extract_characteristics(element)
        assert "char_0" in result
        assert "char_1" in result
        assert result["char_0"] == "Some characteristic"
        assert result["char_1"] == "Another one"
    
    def test_extract_specification_table(self):
        """Test specification table extraction."""
        from bs4 import BeautifulSoup
        
        parser = ContractParser()
        
        # Create test table
        html = """
        <table class="specification">
            <tr>
                <th>Наименование</th>
                <th>Количество</th>
                <th>Цена</th>
            </tr>
            <tr>
                <td>Item 1</td>
                <td>10</td>
                <td>1000.50</td>
            </tr>
            <tr>
                <td>Item 2</td>
                <td>5</td>
                <td>2000.00</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, 'lxml')
        
        result = parser._extract_specification_table(soup)
        assert len(result) == 2
        assert result[0] == {"Наименование": "Item 1", "Количество": "10", "Цена": "1000.50"}
        assert result[1] == {"Наименование": "Item 2", "Количество": "5", "Цена": "2000.00"}
    
    def test_extract_line_items(self):
        """Test line items extraction."""
        from bs4 import BeautifulSoup
        
        parser = ContractParser()
        
        # Create test line items
        html = """
        <div>
            <div class="line-item">
                <span class="item-name">Product A</span>
                <span class="item-quantity">100</span>
                <span class="item-unit">шт.</span>
                <span class="item-price">150.75 руб.</span>
                <span class="item-total">15075.00</span>
                <div class="characteristic">Color: Blue</div>
            </div>
            <tr class="item-row">
                <td class="item-name">Product B</td>
                <td class="item-quantity">50</td>
                <td class="item-unit">кг</td>
                <td class="item-price">200.00</td>
                <td class="item-total">10000.00</td>
            </tr>
        </div>
        """
        soup = BeautifulSoup(html, 'lxml')
        
        result = parser._extract_line_items(soup)
        assert len(result) == 2
        
        # Check first item (div.line-item)
        assert result[0]["name"] == "Product A"
        assert result[0]["quantity"] == "100"
        assert result[0]["unit"] == "шт."
        assert result[0]["price_per_unit"] == "150.75 руб."
        assert result[0]["total_price"] == "15075.00"
        assert result[0]["characteristics"] == {"Color": "Blue"}
        
        # Check second item (tr.item-row)
        assert result[1]["name"] == "Product B"
        assert result[1]["quantity"] == "50"
        assert result[1]["unit"] == "кг"
        assert result[1]["price_per_unit"] == "200.00"
        assert result[1]["total_price"] == "10000.00"
    
    def test_extract_contract_year(self):
        """Test contract year extraction."""
        parser = ContractParser()
        
        # Test with valid date string
        common_info = {"sign_date": "15 января 2024 года"}
        result = parser._extract_contract_year(common_info)
        assert result == 2024
        
        # Test with different date format
        common_info = {"sign_date": "2023-12-31"}
        result = parser._extract_contract_year(common_info)
        assert result == 2023
        
        # Test without date (should return current year)
        common_info = {"sign_date": ""}
        result = parser._extract_contract_year(common_info)
        assert result >= 2024  # Current year or later
    
    def test_parse_price(self):
        """Test price parsing."""
        parser = ContractParser()
        
        # Test various price formats
        test_cases = [
            ("1000.50", 1000.5),
            ("1 000,50", 1000.5),
            ("1,000.50", 1000.5),
            ("1000 руб.", 1000.0),
            ("$1,000.50", 1000.5),
            ("1 000.50 EUR", 1000.5),
            ("invalid", None),
            ("", None),
        ]
        
        for price_str, expected in test_cases:
            result = parser._parse_price(price_str)
            if expected is None:
                assert result is None
            else:
                assert result == pytest.approx(expected, rel=1e-9)
    
    def test_extract_currency(self):
        """Test currency extraction."""
        parser = ContractParser()
        
        test_cases = [
            ("1000 руб.", "RUB"),
            ("1000 р.", "RUB"),
            ("1000 ₽", "RUB"),
            ("$1000", "USD"),
            ("1000 USD", "USD"),
            ("1000 доллар", "USD"),
            ("1000 €", "EUR"),
            ("1000 EUR", "EUR"),
            ("1000 евро", "EUR"),
            ("1000", "RUB"),  # Default
            ("", "RUB"),  # Default
        ]
        
        for price_str, expected in test_cases:
            result = parser._extract_currency(price_str)
            assert result == expected
    
    def test_extract_unit_prices(self):
        """Test unit price extraction."""
        parser = ContractParser()
        
        # Create test payments data
        payments_data = {
            "line_items": [
                {
                    "name": "Product A",
                    "quantity": "10",
                    "unit": "шт.",
                    "price_per_unit": "150.75 руб.",
                    "total_price": "1507.50"
                },
                {
                    "name": "Product B",
                    "quantity": "5",
                    "unit": "кг",
                    "price_per_unit": "invalid",  # Should be skipped
                    "total_price": "1000.00"
                }
            ],
            "specification": [
                {
                    "Наименование": "Service C",
                    "Цена за единицу": "2000,00"
                },
                {
                    "Наименование": "Item D",
                    "Unit Price": "$500.00"
                }
            ]
        }
        
        result = parser._extract_unit_prices(payments_data)
        assert len(result) == 3
        
        # Check line item price
        assert result[0]["item_name"] == "Product A"
        assert result[0]["unit_price"] == 150.75
        assert result[0]["currency"] == "RUB"
        assert result[0]["quantity"] == "10"
        assert result[0]["unit"] == "шт."
        
        # Check specification prices
        assert result[1]["item_name"] == "Service C"
        assert result[1]["unit_price"] == 2000.0
        assert result[1]["source"] == "specification_table"
        
        assert result[2]["item_name"] == "Item D"
        assert result[2]["unit_price"] == 500.0
        assert result[2]["source"] == "specification_table"
    
    @pytest.mark.asyncio
    async def test_make_request_success(self):
        """Test successful HTTP request."""
        parser = ContractParser()
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = AsyncMock()
            mock_response.text = "<html>Test response</html>"
            
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            response = await parser._make_request("http://test.url")
            
            assert response == mock_response
            mock_client.request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_make_request_retry(self):
        """Test HTTP request with retry logic."""
        parser = ContractParser(max_retries=2)
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response_success = AsyncMock()
            mock_response_success.status_code = 200
            mock_response_success.raise_for_status = AsyncMock()
            
            mock_response_error = AsyncMock()
            mock_response_error.raise_for_status.side_effect = Exception("Error")
            
            mock_client = AsyncMock()
            # First call fails, second succeeds
            mock_client.request = AsyncMock(side_effect=[mock_response_error, mock_response_success])
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            response = await parser._make_request("http://test.url")
            
            assert response == mock_response_success
            assert mock_client.request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_parse_contract_integration(self):
        """Test full contract parsing integration (mocked)."""
        parser = ContractParser()
        
        # Mock all the internal methods
        with patch.object(parser, '_extract_reestr_number', return_value="1234567890"), \
             patch.object(parser, '_parse_common_info', return_value={
                 "contract_number": "CONTRACT-123",
                 "sign_date": "2024-01-15",
                 "customer": "Test Customer",
                 "supplier": "Test Supplier",
                 "contract_price": "100000.00",
                 "currency": "RUB",
                 "status": "Исполнение завершено"
             }), \
             patch.object(parser, '_parse_payments_tab', return_value={
                 "specification": [{"Наименование": "Item 1", "Цена": "1000.00"}],
                 "line_items": [{"name": "Product A", "price_per_unit": "150.75"}]
             }), \
             patch.object(parser, '_identify_attachments', return_value=[
                 {"name": "Печатная форма", "url": "http://test.url/doc.pdf", "type": "printed_form"}
             ]), \
             patch.object(parser, '_download_printed_form', return_value={
                 "file_path": "/tmp/test.pdf",
                 "file_name": "Печатная форма"
             }):
            
            result = await parser.parse_contract("http://test.url/contract")
            
            assert result["reestr_number"] == "1234567890"
            assert result["contract_url"] == "http://test.url/contract"
            assert result["common_info"]["contract_number"] == "CONTRACT-123"
            assert result["payments_data"]["specification"][0]["Наименование"] == "Item 1"
            assert len(result["attachments"]) == 1
            assert result["attachments"][0]["type"] == "printed_form"
            assert result["printed_form_data"]["file_name"] == "Печатная форма"
            assert "parsed_at" in result