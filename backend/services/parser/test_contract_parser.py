"""
Test file for ContractParser functionality.
"""

import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from .contract import ContractParser, ContractCommonInfo, ContractSpecificationItem, ContractAttachment

# Configure logging for tests
logging.basicConfig(level=logging.WARNING)


class TestContractParser:
    """Test cases for ContractParser."""
    
    def test_ensure_common_info_url(self):
        """Test URL transformation for common info page."""
        parser = ContractParser()
        
        # Test with URL that already has common-info.html
        url1 = "https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber=123"
        assert parser._ensure_common_info_url(url1) == url1
        
        # Test with URL without common-info.html
        url2 = "https://zakupki.gov.ru/epz/contract/contractCard/"
        expected2 = "https://zakupki.gov.ru/epz/contract/contractCard/common-info.html"
        assert parser._ensure_common_info_url(url2) == expected2
        
        # Test with URL with trailing slash
        url3 = "https://zakupki.gov.ru/epz/contract/contractCard"
        expected3 = "https://zakupki.gov.ru/epz/contract/contractCard/common-info.html"
        assert parser._ensure_common_info_url(url3) == expected3
    
    def test_get_payments_tab_url(self):
        """Test URL transformation for payments tab."""
        parser = ContractParser()
        
        # Test with base URL
        url = "https://zakupki.gov.ru/epz/contract/contractCard/"
        expected = "https://zakupki.gov.ru/epz/contract/contractCard/payments.html"
        assert parser._get_payments_tab_url(url) == expected
        
        # Test with URL with trailing slash
        url2 = "https://zakupki.gov.ru/epz/contract/contractCard"
        expected2 = "https://zakupki.gov.ru/epz/contract/contractCard/payments.html"
        assert parser._get_payments_tab_url(url2) == expected2
    
    def test_is_document_link(self):
        """Test document link detection."""
        parser = ContractParser()
        
        # Test PDF links
        assert parser._is_document_link("document.pdf") == True
        assert parser._is_document_link("document.PDF") == True
        assert parser._is_document_link("https://example.com/doc.pdf") == True
        
        # Test DOCX links
        assert parser._is_document_link("document.docx") == True
        assert parser._is_document_link("document.doc") == True
        
        # Test XLSX links
        assert parser._is_document_link("document.xlsx") == True
        assert parser._is_document_link("document.xls") == True
        
        # Test non-document links
        assert parser._is_document_link("document.html") == False
        assert parser._is_document_link("document.txt") == False
        assert parser._is_document_link("https://example.com/page.html") == False
    
    def test_get_file_type_from_url(self):
        """Test file type extraction from URL."""
        parser = ContractParser()
        
        assert parser._get_file_type_from_url("document.pdf") == "pdf"
        assert parser._get_file_type_from_url("document.docx") == "docx"
        assert parser._get_file_type_from_url("document.doc") == "docx"
        assert parser._get_file_type_from_url("document.xlsx") == "xlsx"
        assert parser._get_file_type_from_url("document.xls") == "xlsx"
        assert parser._get_file_type_from_url("document.rtf") == "rtf"
        assert parser._get_file_type_from_url("unknown.txt") == None
    
    def test_find_column_index(self):
        """Test column index finding in headers."""
        parser = ContractParser()
        
        headers = ["№", "наименование", "ед. изм", "количество", "цена"]
        
        assert parser._find_column_index(headers, ["№", "номер"]) == 0
        assert parser._find_column_index(headers, ["наименование", "описание"]) == 1
        assert parser._find_column_index(headers, ["ед.", "единица"]) == 2
        assert parser._find_column_index(headers, ["количество", "кол-во"]) == 3
        assert parser._find_column_index(headers, ["цена", "стоимость"]) == 4
        assert parser._find_column_index(headers, ["несуществующий"]) == None
    
    def test_create_specification_item(self):
        """Test specification item creation from parsed data."""
        parser = ContractParser()
        
        # Test with complete data
        item_data = {
            'item_num': '1',
            'name': 'Test Product',
            'okpd2': '12.34.56.789',
            'ktru': '01.02.03',
            'unit': 'шт.',
            'quantity': '10',
            'unit_price': '1 234,56',
            'total_price': '12 345,60'
        }
        
        result = parser._create_specification_item(item_data)
        assert result is not None
        assert result.item_number == '1'
        assert result.name == 'Test Product'
        assert result.okpd2_code == '12.34.56.789'
        assert result.ktru_code == '01.02.03'
        assert result.unit == 'шт.'
        assert result.quantity == 10.0
        assert result.unit_price == 1234.56
        assert result.total_price == 12345.60
        
        # Test with minimal data
        item_data_minimal = {
            'name': 'Minimal Product',
            'item_num': '2'
        }
        
        result2 = parser._create_specification_item(item_data_minimal)
        assert result2 is not None
        assert result2.item_number == '2'
        assert result2.name == 'Minimal Product'
        assert result2.quantity is None
        assert result2.unit_price is None
    
    @pytest.mark.asyncio
    async def test_parse_common_info(self):
        """Test common info parsing from HTML."""
        parser = ContractParser()
        
        # Create sample HTML with contract information
        html = """
        <html>
            <head><title>Договор № 12345678901234567890</title></head>
            <body>
                <h1>Информация о контракте</h1>
                <table>
                    <tr><td>Дата заключения</td><td>15.01.2024</td></tr>
                    <tr><td>Заказчик</td><td>ООО "Тестовый Заказчик"</td></tr>
                    <tr><td>Поставщик</td><td>ООО "Тестовый Поставщик"</td></tr>
                    <tr><td>Стоимость контракта</td><td>1 234 567,89 руб.</td></tr>
                    <tr><td>Статус</td><td>Исполнение завершено</td></tr>
                </table>
                <span class="status">Активный</span>
            </body>
        </html>
        """
        
        result = await parser._parse_common_info(html, "https://example.com/contract")
        
        assert result.reestr_number == "12345678901234567890"
        assert result.contract_url == "https://example.com/contract"
        assert result.sign_date == datetime(2024, 1, 15)
        assert result.customer_name == 'ООО "Тестовый Заказчик"'
        assert result.supplier_name == 'ООО "Тестовый Поставщик"'
        assert result.contract_price == 1234567.89
        assert result.contract_status == "Активный"
        assert result.execution_status == "Исполнение завершено"
    
    @pytest.mark.asyncio
    async def test_parse_specifications(self):
        """Test specification parsing from HTML."""
        parser = ContractParser()
        
        # Create sample HTML with specification table
        html = """
        <html>
            <body>
                <table>
                    <tr>
                        <th>№</th>
                        <th>Наименование</th>
                        <th>ОКПД2</th>
                        <th>КТРУ</th>
                        <th>Ед. изм.</th>
                        <th>Количество</th>
                        <th>Цена за ед.</th>
                        <th>Сумма</th>
                    </tr>
                    <tr>
                        <td>1</td>
                        <td>Тестовый товар 1</td>
                        <td>12.34.56.789</td>
                        <td>01.02.03</td>
                        <td>шт.</td>
                        <td>10</td>
                        <td>1 234,56</td>
                        <td>12 345,60</td>
                    </tr>
                    <tr>
                        <td>2</td>
                        <td>Тестовый товар 2</td>
                        <td>98.76.54.321</td>
                        <td>04.05.06</td>
                        <td>кг</td>
                        <td>5,5</td>
                        <td>500</td>
                        <td>2 750</td>
                    </tr>
                </table>
            </body>
        </html>
        """
        
        results = await parser._parse_specifications(html)
        
        assert len(results) == 2
        
        # Check first item
        item1 = results[0]
        assert item1.item_number == "1"
        assert item1.name == "Тестовый товар 1"
        assert item1.okpd2_code == "12.34.56.789"
        assert item1.ktru_code == "01.02.03"
        assert item1.unit == "шт."
        assert item1.quantity == 10.0
        assert item1.unit_price == 1234.56
        assert item1.total_price == 12345.60
        
        # Check second item
        item2 = results[1]
        assert item2.item_number == "2"
        assert item2.name == "Тестовый товар 2"
        assert item2.okpd2_code == "98.76.54.321"
        assert item2.ktru_code == "04.05.06"
        assert item2.unit == "кг"
        assert item2.quantity == 5.5
        assert item2.unit_price == 500.0
        assert item2.total_price == 2750.0
    
    @pytest.mark.asyncio
    async def test_identify_attachments(self):
        """Test attachment identification from HTML."""
        parser = ContractParser()
        
        # Create sample HTML with attachment links
        html = """
        <html>
            <body>
                <a href="/documents/contract.pdf">Договор в формате PDF</a>
                <a href="/documents/spec.docx">Спецификация</a>
                <a href="/documents/printed-form.pdf">Печатная форма</a>
                <a href="/page.html">Не документ</a>
                <a href="https://external.com/doc.xlsx">Внешний документ</a>
            </body>
        </html>
        """
        
        base_url = "https://zakupki.gov.ru/epz/contract/contractCard/"
        results = await parser._identify_attachments(html, base_url)
        
        assert len(results) == 4  # 4 document links
        
        # Check PDF attachment
        pdf_att = next(a for a in results if a.file_type == "pdf" and "contract.pdf" in a.url)
        assert pdf_att.name == "Договор в формате PDF"
        assert "contract.pdf" in pdf_att.url
        assert pdf_att.description is None
        
        # Check DOCX attachment
        docx_att = next(a for a in results if a.file_type == "docx")
        assert docx_att.name == "Спецификация"
        assert "spec.docx" in docx_att.url
        
        # Check printed form
        printed_form = next(a for a in results if a.description == "Printed Form")
        assert printed_form.file_type == "pdf"
        assert "printed-form.pdf" in printed_form.url
        
        # Check XLSX attachment
        xlsx_att = next(a for a in results if a.file_type == "xlsx")
        assert "doc.xlsx" in xlsx_att.url
    
    @pytest.mark.asyncio
    async def test_parse_contract_integration(self):
        """Test full contract parsing integration with mocked HTTP requests."""
        parser = ContractParser()
        
        # Mock session and responses
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        
        # Mock common info HTML
        common_info_html = """
        <html>
            <head><title>Договор № 12345678901234567890</title></head>
            <body>
                <h1>Контракт от 15.01.2024</h1>
                <table>
                    <tr><td>Заказчик</td><td>Тестовый Заказчик</td></tr>
                    <tr><td>Поставщик</td><td>Тестовый Поставщик</td></tr>
                    <tr><td>Стоимость</td><td>100 000 руб.</td></tr>
                </table>
                <a href="/printed-form.pdf">Печатная форма</a>
            </body>
        </html>
        """
        
        # Mock payments HTML
        payments_html = """
        <html>
            <body>
                <table>
                    <tr><th>№</th><th>Наименование</th><th>Цена</th></tr>
                    <tr><td>1</td><td>Товар 1</td><td>1 000</td></tr>
                </table>
            </body>
        </html>
        """
        
        # Mock printed form PDF
        pdf_content = b"%PDF-1.4 mock pdf content"
        
        # Configure mock responses
        mock_response.text = AsyncMock(side_effect=[common_info_html, payments_html])
        mock_response.read = AsyncMock(return_value=pdf_content)
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()
        
        mock_session.get = AsyncMock(return_value=mock_response)
        
        # Test with mocked session
        parser._session = mock_session
        contract_url = "https://zakupki.gov.ru/epz/contract/contractCard/"
        
        result = await parser.parse_contract(contract_url)
        
        # Verify results
        assert result.common_info.reestr_number == "12345678901234567890"
        assert len(result.specifications) == 1
        assert result.specifications[0].name == "Товар 1"
        assert result.specifications[0].unit_price == 1000.0
        
        # Verify attachments were identified
        assert len(result.attachments) > 0
        
        # Verify printed form was downloaded (contract is from 2024, not >= 2025)
        # So printed form should NOT be downloaded
        assert result.printed_form_content is None
        assert result.printed_form_type is None
        
        # Verify HTTP calls were made
        assert mock_session.get.call_count >= 2


if __name__ == "__main__":
    # Run simple demonstration
    print("Running ContractParser tests...")
    
    # Create parser instance
    parser = ContractParser()
    
    # Test URL helpers
    print("\n1. Testing URL helpers:")
    test_url = "https://zakupki.gov.ru/epz/contract/contractCard/"
    print(f"   Original URL: {test_url}")
    print(f"   Common info URL: {parser._ensure_common_info_url(test_url)}")
    print(f"   Payments URL: {parser._get_payments_tab_url(test_url)}")
    
    # Test document detection
    print("\n2. Testing document detection:")
    test_docs = ["doc.pdf", "spec.docx", "data.xlsx", "page.html"]
    for doc in test_docs:
        is_doc = parser._is_document_link(doc)
        file_type = parser._get_file_type_from_url(doc)
        print(f"   {doc}: is_document={is_doc}, file_type={file_type}")
    
    print("\nContractParser implementation complete!")