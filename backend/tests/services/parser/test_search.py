"""
Unit tests for the search parser.
"""
import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from services.parser.search import SearchParser


class TestSearchParser(unittest.TestCase):
    """Test cases for SearchParser class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = SearchParser()
        
    def test_build_search_params(self):
        """Test building search parameters."""
        # Test with minimal parameters
        params = self.parser._build_search_params(
            ktru_code="03121110-1",
            customer_region="СЗФО",
            law="44-ФЗ",
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 12, 31),
            execution_statuses=["Исполнение завершено"],
        )
        
        self.assertIsInstance(params, dict)
        self.assertIn("searchString", params)
        self.assertEqual(params["searchString"], "03121110-1")
        self.assertIn("selectedRegions", params)
        self.assertEqual(params["selectedRegions"], "СЗФО")
        self.assertIn("selectedFz", params)
        self.assertEqual(params["selectedFz"], "fz44")
        
        # Test with different law
        params = self.parser._build_search_params(
            ktru_code="03121110-1",
            customer_region="СЗФО",
            law="223-ФЗ",
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 12, 31),
            execution_statuses=["Исполнение завершено"],
        )
        self.assertEqual(params["selectedFz"], "fz223")
        
        # Test with multiple execution statuses
        params = self.parser._build_search_params(
            ktru_code="03121110-1",
            customer_region="СЗФО",
            law="44-ФЗ",
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 12, 31),
            execution_statuses=["Исполнение завершено", "Исполняется"],
        )
        self.assertIn("contractStage", params)
        self.assertIn("EXECUTION_COMPLETED", params["contractStage"])
        self.assertIn("EXECUTION_IN_PROGRESS", params["contractStage"])
    
    def test_build_search_url(self):
        """Test building complete search URL."""
        url = self.parser.build_search_url(
            ktru_code="03121110-1",
            customer_region="СЗФО",
            law="44-ФЗ",
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 12, 31),
            execution_statuses=["Исполнение завершено"],
        )
        
        self.assertIsInstance(url, str)
        self.assertTrue(url.startswith(self.parser.search_url))
        self.assertIn("?searchString=03121110-1", url)
        self.assertIn("selectedFz=fz44", url)
        self.assertIn("selectedRegions=%D0%A1%D0%97%D0%A4%D0%9E", url)  # URL-encoded СЗФО
    
    def test_parse_contract_card(self):
        """Test parsing individual contract card."""
        # Create a mock BeautifulSoup element
        mock_card = MagicMock()
        
        # Mock registry number element
        mock_registry_element = MagicMock()
        mock_registry_element.get_text.return_value = "1234567890123456789"
        mock_registry_element.get.return_value = "/epz/contract/contractCard/document-info.html?reestrNumber=1234567890123456789"
        # Mock dictionary-like access for href attribute
        mock_registry_element.__getitem__.return_value = "/epz/contract/contractCard/document-info.html?reestrNumber=1234567890123456789"
        
        # Mock date element
        mock_date_element = MagicMock()
        mock_date_element.get_text.return_value = "01.01.2024"
        
        # Mock price element
        mock_price_element = MagicMock()
        mock_price_element.get_text.return_value = "1 234 567,89 руб."
        
        # Mock customer element
        mock_customer_element = MagicMock()
        mock_customer_element.get_text.return_value = "ООО 'Тестовая компания'"
        
        # Mock status element
        mock_status_element = MagicMock()
        mock_status_element.get_text.return_value = "Исполнение завершено"
        
        # Set up select_one to return appropriate elements
        def select_one_side_effect(selector):
            if selector == "a.registry-entry__header-mid__number" or selector == "a.registry-entry__header-mid__number[href]":
                return mock_registry_element
            elif selector == "div.data-block__value":
                return mock_date_element
            elif selector == "div.price-block__value":
                return mock_price_element
            elif selector == "div.registry-entry__body-href":
                return mock_customer_element
            elif selector == "div.registry-entry__header-mid__title":
                return mock_status_element
            return None
        
        mock_card.select_one.side_effect = select_one_side_effect
        
        # Parse the card
        result = self.parser._parse_contract_card(mock_card)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["registry_no"], "1234567890123456789")
        self.assertEqual(result["date"], "01.01.2024")
        self.assertEqual(result["price"], 1234567.89)
        self.assertIn("/epz/contract/contractCard/document-info.html", result["url"])
        self.assertEqual(result["customer"], "ООО 'Тестовая компания'")
        self.assertEqual(result["status"], "Исполнение завершено")
    
    def test_parse_contract_card_missing_fields(self):
        """Test parsing contract card with missing fields."""
        mock_card = MagicMock()
        mock_card.select_one.return_value = None
        
        result = self.parser._parse_contract_card(mock_card)
        self.assertIsNone(result)
    
    def test_parse_search_results(self):
        """Test parsing search results HTML."""
        # Create mock HTML with contract cards
        html = """
        <html>
            <body>
                <div class="search-results__total">Найдено: 123</div>
                <div class="search-registry-entry-block">
                    <a class="registry-entry__header-mid__number" href="/epz/contract/contractCard/document-info.html?reestrNumber=123">
                        1234567890123456789
                    </a>
                    <div class="data-block__value">01.01.2024</div>
                    <div class="price-block__value">1 234 567,89 руб.</div>
                </div>
                <div class="search-registry-entry-block">
                    <a class="registry-entry__header-mid__number" href="/epz/contract/contractCard/document-info.html?reestrNumber=456">
                        9876543210987654321
                    </a>
                    <div class="data-block__value">15.02.2024</div>
                    <div class="price-block__value">987 654,32 руб.</div>
                </div>
            </body>
        </html>
        """
        
        total_found, contracts = self.parser._parse_search_results(html)
        
        self.assertEqual(total_found, 123)
        self.assertEqual(len(contracts), 2)
        
        # Check first contract
        self.assertEqual(contracts[0]["registry_no"], "1234567890123456789")
        self.assertEqual(contracts[0]["date"], "01.01.2024")
        self.assertEqual(contracts[0]["price"], 1234567.89)
        
        # Check second contract
        self.assertEqual(contracts[1]["registry_no"], "9876543210987654321")
        self.assertEqual(contracts[1]["date"], "15.02.2024")
        self.assertEqual(contracts[1]["price"], 987654.32)
    
    def test_sort_and_limit_contracts(self):
        """Test sorting and limiting contracts."""
        contracts = [
            {"registry_no": "1", "date": "15.02.2024", "price": 1000},
            {"registry_no": "2", "date": "01.01.2024", "price": 2000},
            {"registry_no": "3", "date": "10.03.2024", "price": 3000},
            {"registry_no": "4", "date": "05.02.2024", "price": 4000},
        ]
        
        # Test sorting (newest first)
        sorted_contracts = self.parser._sort_and_limit_contracts(contracts, 10)
        
        # Should be sorted by date descending
        self.assertEqual(sorted_contracts[0]["registry_no"], "3")  # 10.03.2024 - newest
        self.assertEqual(sorted_contracts[1]["registry_no"], "1")  # 15.02.2024
        self.assertEqual(sorted_contracts[2]["registry_no"], "4")  # 05.02.2024
        self.assertEqual(sorted_contracts[3]["registry_no"], "2")  # 01.01.2024 - oldest
        
        # Test limiting
        limited_contracts = self.parser._sort_and_limit_contracts(contracts, 2)
        self.assertEqual(len(limited_contracts), 2)
        self.assertEqual(limited_contracts[0]["registry_no"], "3")  # Newest
        self.assertEqual(limited_contracts[1]["registry_no"], "1")  # Second newest
    
    @patch('services.parser.search.aiohttp.ClientSession')
    def test_search_contracts_mock(self, mock_session_class):
        """Test search_contracts with mocked HTTP requests."""
        import asyncio
        
        # Create mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text.return_value = """
        <html>
            <div class="search-results__total">Найдено: 5</div>
            <div class="search-registry-entry-block">
                <a class="registry-entry__header-mid__number" href="/epz/contract/contractCard/document-info.html?reestrNumber=123">
                    1234567890123456789
                </a>
                <div class="data-block__value">01.01.2024</div>
                <div class="price-block__value">1 234 567,89 руб.</div>
            </div>
        </html>
        """
        
        # Create mock session
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        mock_session_class.return_value = mock_session
        
        # Call search_contracts using asyncio.run
        total_found, contracts = asyncio.run(self.parser.search_contracts(
            ktru_code="03121110-1",
            customer_region="СЗФО",
            law="44-ФЗ",
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 12, 31),
            execution_statuses=["Исполнение завершено"],
            limit_contracts=10,
        ))
        
        # Verify results
        self.assertEqual(total_found, 5)
        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0]["registry_no"], "1234567890123456789")
        
        # Verify HTTP request was made
        mock_session.get.assert_called_once()


class TestSearchParserIntegration(unittest.TestCase):
    """Integration tests for SearchParser (requires network)."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = SearchParser()
        # Reduce retries and timeout for tests
        self.parser.max_retries = 1
        self.parser.timeout = 5
    
    @unittest.skip("Skipping network test to avoid external requests")
    async def test_build_url_integration(self):
        """Test that built URLs are valid (doesn't make actual request)."""
        url = self.parser.build_search_url(
            ktru_code="03121110-1",
            customer_region="СЗФО",
            law="44-ФЗ",
            date_from=datetime(2024, 1, 1),
            date_to=datetime(2024, 12, 31),
            execution_statuses=["Исполнение завершено"],
        )
        
        # URL should be well-formed
        self.assertTrue(url.startswith("https://"))
        self.assertIn("zakupki.gov.ru", url)
        self.assertIn("searchString=03121110-1", url)


if __name__ == "__main__":
    # Run tests
    unittest.main()