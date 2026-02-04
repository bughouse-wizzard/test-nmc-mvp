"""
Tests for zakupki.gov.ru search scraper.
"""

import pytest
from datetime import datetime, timedelta
from app.services.scraper.search import ZakupkiSearchScraper


class TestZakupkiSearchScraper:
    """Test suite for ZakupkiSearchScraper."""
    
    def test_build_search_url_basic(self):
        """Test URL builder with basic parameters."""
        scraper = ZakupkiSearchScraper()
        
        ktru_code = "31.20.11.110"
        url = scraper.build_search_url(ktru_code=ktru_code)
        
        assert "zakupki.gov.ru" in url
        assert "epz/order/extendedsearch/results.html" in url
        assert ktru_code in url
        assert "fz44=on" in url
        assert "regions=78000000000" in url  # СЗФО region code
        
    def test_build_search_url_with_dates(self):
        """Test URL builder with custom dates."""
        scraper = ZakupkiSearchScraper()
        
        date_from = "2022-01-01"
        date_to = "2023-12-31"
        url = scraper.build_search_url(
            ktru_code="31.20.11.110",
            date_from=date_from,
            date_to=date_to,
        )
        
        assert f"publishedDateFrom={date_from}" in url
        assert f"publishedDateTo={date_to}" in url
        
    def test_build_search_url_with_execution_statuses(self):
        """Test URL builder with execution statuses."""
        scraper = ZakupkiSearchScraper()
        
        url = scraper.build_search_url(
            ktru_code="31.20.11.110",
            execution_statuses=["Исполнение завершено", "Исполнение прекращено"],
        )
        
        assert "executed=on" in url
        assert "terminated=on" in url
        
    def test_build_search_url_with_page(self):
        """Test URL builder with page number."""
        scraper = ZakupkiSearchScraper()
        
        url = scraper.build_search_url(
            ktru_code="31.20.11.110",
            page=2,
        )
        
        assert "pageNumber=2" in url
        
    def test_parse_search_results_empty(self):
        """Test parsing empty HTML."""
        scraper = ZakupkiSearchScraper()
        
        html = "<html><body>No results</body></html>"
        total_found, contracts = scraper.parse_search_results(html)
        
        assert total_found == 0
        assert len(contracts) == 0
        
    def test_parse_search_results_sample(self):
        """Test parsing sample HTML with contract data."""
        scraper = ZakupkiSearchScraper()
        
        # Create a sample HTML with contract data
        html = """
        <html>
            <body>
                <div class="search-results__total">Найдено: 1 234</div>
                <div class="search-registry-entry-block">
                    <div class="registry-entry__header-mid__number">
                        <a class="registry-entry__header-mid__number" href="/epz/order/notice/ea44/view/common-info.html?regNumber=1234567890">
                            1234567890
                        </a>
                    </div>
                    <div class="data-block__value">01.01.2023</div>
                    <div class="price-block__value">1 234 567,89 руб.</div>
                </div>
            </body>
        </html>
        """
        
        total_found, contracts = scraper.parse_search_results(html)
        
        assert total_found == 1234
        assert len(contracts) == 1
        
        contract = contracts[0]
        assert contract['reestr_number'] == '1234567890'
        assert 'zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=1234567890' in contract['link']
        assert contract['date'] == '01.01.2023'
        assert contract['price'] == 1234567.89
        assert contract['currency'] == 'RUB'
        
    def test_parse_contract_element_missing_data(self):
        """Test parsing contract element with missing data."""
        scraper = ZakupkiSearchScraper()
        
        # Create element with missing required data
        from bs4 import BeautifulSoup
        html = """
        <div class="search-registry-entry-block">
            <div>No contract data here</div>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        element = soup.find('div', class_='search-registry-entry-block')
        
        contract = scraper._parse_contract_element(element)
        assert contract is None
        
    @pytest.mark.asyncio
    async def test_make_request_with_retry_mock(self):
        """Test retry logic with mock client."""
        # This would require mocking httpx.AsyncClient
        # For now, just test that the method exists
        scraper = ZakupkiSearchScraper()
        assert hasattr(scraper, '_make_request_with_retry')
        
    def test_default_dates(self):
        """Test that default dates are set correctly."""
        scraper = ZakupkiSearchScraper()
        
        # Get URL without specifying dates
        url = scraper.build_search_url(ktru_code="31.20.11.110")
        
        # Should have date parameters
        assert "publishedDateFrom=" in url
        assert "publishedDateTo=" in url
        
        # Extract dates from URL
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        
        # Check date format
        date_from = params.get('publishedDateFrom', [''])[0]
        date_to = params.get('publishedDateTo', [''])[0]
        
        assert len(date_from) == 10  # YYYY-MM-DD
        assert len(date_to) == 10    # YYYY-MM-DD
        
        # Date_to should be today or recent
        today = datetime.now().strftime("%Y-%m-%d")
        assert date_to == today
        
    def test_region_mapping(self):
        """Test region code mapping."""
        scraper = ZakupkiSearchScraper()
        
        # Test СЗФО mapping
        url = scraper.build_search_url(ktru_code="31.20.11.110", region="СЗФО")
        assert "regions=78000000000" in url
        
        # Test default for unknown region
        url = scraper.build_search_url(ktru_code="31.20.11.110", region="UNKNOWN")
        assert "regions=78000000000" in url  # Should default to СЗФО


if __name__ == "__main__":
    pytest.main([__file__, "-v"])