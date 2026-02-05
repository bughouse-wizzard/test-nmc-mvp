"""
Tests for contract parser.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from backend.services.parser.contract import ContractParser


class TestContractParser:
    """Test contract parser functionality."""
    
    @pytest.mark.asyncio
    async def test_extract_reestr_number(self):
        """Test reestr number extraction from URL."""
        parser = ContractParser()
        
        # Test with valid URL
        url = "https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber=1234567890"
        result = parser._extract_reestr_number(url)
        assert result == "1234567890"
        
        # Test with URL without reestrNumber
        url = "https://zakupki.gov.ru/epz/contract/contractCard/common-info.html"
        result = parser._extract_reestr_number(url)
        assert result == ""
    
    @pytest.mark.asyncio
    async def test_is_2025_plus_contract(self):
        """Test 2025+ contract detection."""
        parser = ContractParser()
        
        # Test with 2025 date
        assert parser._is_2025_plus_contract("01.01.2025") == True
        assert parser._is_2025_plus_contract("2025-12-31") == True
        
        # Test with 2024 date
        assert parser._is_2025_plus_contract("31.12.2024") == False
        
        # Test with invalid date
        assert parser._is_2025_plus_contract("invalid date") == False
        assert parser._is_2025_plus_contract(None) == False
    
    def test_extract_unit_prices(self):
        """Test unit price extraction from specification."""
        parser = ContractParser()
        
        # Test with valid specification
        specification = [
            {
                'наименование': 'Товар 1',
                'количество': '10',
                'ед. изм.': 'шт',
                'цена': '1 000,50 руб.',
                'стоимость': '10 005,00'
            },
            {
                'наименование': 'Товар 2',
                'количество': '5',
                'ед. изм.': 'кг',
                'цена за единицу': '500.75',
                'стоимость': '2 503,75'
            }
        ]
        
        unit_prices = parser._extract_unit_prices(specification)
        assert len(unit_prices) == 2
        assert unit_prices[0]['price'] == 1000.50
        assert unit_prices[0]['item_name'] == 'Товар 1'
        assert unit_prices[1]['price'] == 500.75
        assert unit_prices[1]['item_name'] == 'Товар 2'
    
    @pytest.mark.asyncio
    async def test_parse_specification(self):
        """Test specification parsing from HTML."""
        parser = ContractParser()
        
        # Mock HTML with table
        html = """
        <html>
            <body>
                <table>
                    <tr>
                        <th>Наименование</th>
                        <th>Количество</th>
                        <th>Ед. изм.</th>
                        <th>Цена</th>
                        <th>Стоимость</th>
                    </tr>
                    <tr>
                        <td>Товар 1</td>
                        <td>10</td>
                        <td>шт</td>
                        <td>1000.50</td>
                        <td>10005.00</td>
                    </tr>
                    <tr>
                        <td>Товар 2</td>
                        <td>5</td>
                        <td>кг</td>
                        <td>500.75</td>
                        <td>2503.75</td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        specification = await parser._parse_specification(html)
        assert len(specification) == 2
        assert specification[0]['наименование'] == 'Товар 1'
        assert specification[0]['количество'] == '10'
        assert specification[1]['наименование'] == 'Товар 2'
        assert specification[1]['цена'] == '500.75'
    
    @pytest.mark.asyncio
    async def test_identify_attachments(self):
        """Test attachment identification."""
        parser = ContractParser()
        
        # Mock HTML with attachment links
        html = """
        <html>
            <body>
                <a href="/documents/printed_form.pdf">Печатная форма</a>
                <a href="/documents/spec.pdf">Спецификация.pdf</a>
                <a href="/documents/contract.docx">Договор.docx</a>
                <a href="/documents/price.xlsx">Прайс-лист.xlsx</a>
                <a href="/about">О сайте</a>
            </body>
        </html>
        """
        
        attachments = await parser._identify_attachments(html)
        assert attachments['printed_form'] == '/documents/printed_form.pdf'
        assert len(attachments['other_attachments']) == 3
        assert any(att['name'] == 'спецификация.pdf' for att in attachments['other_attachments'])
    
    @pytest.mark.asyncio
    async def test_parse_contract_integration(self):
        """Test full contract parsing integration with mocks."""
        parser = ContractParser(session=AsyncMock())
        
        # Mock session responses
        mock_session = parser._session
        mock_session.request = AsyncMock()
        
        # Mock common info response
        common_info_html = """
        <html>
            <body>
                <div>Дата заключения: 15.01.2025</div>
                <div>Цена контракта: 1 000 000,50 руб.</div>
                <table>
                    <tr><td>Наименование заказчика</td><td>ООО "Заказчик"</td></tr>
                </table>
                <table>
                    <tr><td>Наименование поставщика</td><td>ООО "Поставщик"</td></tr>
                </table>
                <a href="/documents/printed_form.pdf">Печатная форма</a>
            </body>
        </html>
        """
        
        # Mock payments tab response
        payments_html = """
        <html>
            <body>
                <table>
                    <tr>
                        <th>Наименование</th>
                        <th>Количество</th>
                        <th>Цена</th>
                    </tr>
                    <tr>
                        <td>Товар 1</td>
                        <td>100</td>
                        <td>10 000,50</td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        # Set up mock responses
        mock_response_common = AsyncMock()
        mock_response_common.text = AsyncMock(return_value=common_info_html)
        mock_response_common.raise_for_status = Mock()
        
        mock_response_payments = AsyncMock()
        mock_response_payments.text = AsyncMock(return_value=payments_html)
        mock_response_payments.raise_for_status = Mock()
        
        mock_session.request.side_effect = [mock_response_common, mock_response_payments]
        
        # Test parsing
        contract_url = "https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber=1234567890"
        
        # Mock printed form download
        with patch.object(parser, '_download_printed_form', AsyncMock(return_value=None)):
            result = await parser.parse_contract(contract_url)
        
        # Verify results
        assert result['reestr_number'] == '1234567890'
        assert result['contract_url'] == contract_url
        assert result['common_info']['sign_date'] == '15.01.2025'
        assert result['common_info']['contract_price'] == 1000000.50
        assert result['common_info']['customer'] == 'ООО "Заказчик"'
        assert result['common_info']['supplier'] == 'ООО "Поставщик"'
        assert result['attachments']['printed_form'] == '/documents/printed_form.pdf'
        assert result['is_2025_plus'] == True
        assert len(result['specification']) == 1
        assert result['specification'][0]['наименование'] == 'Товар 1'
        assert len(result['unit_prices']) == 1
        assert result['unit_prices'][0]['price'] == 10000.50