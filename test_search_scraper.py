#!/usr/bin/env python3
"""
Test script for Zakupki Search Scraper.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from app.services.scraper.search import ZakupkiSearchScraper, search_contracts_async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_url_building():
    """Test URL building functionality."""
    print("=== Testing URL Building ===")
    
    scraper = ZakupkiSearchScraper()
    
    # Test 1: Basic URL with default parameters
    url1 = scraper.build_search_url(
        ktru_code="31.20.11.110",
        date_from=datetime.now() - timedelta(days=3*365),
        date_to=datetime.now(),
    )
    print(f"Test 1 - Basic URL:\n{url1}\n")
    
    # Test 2: URL with specific dates
    url2 = scraper.build_search_url(
        ktru_code="31.20.11.110",
        date_from=datetime(2023, 1, 1),
        date_to=datetime(2023, 12, 31),
        page=2,
        page_size=100,
    )
    print(f"Test 2 - Specific dates (page 2):\n{url2}\n")
    
    # Test 3: URL with 223-FZ law
    url3 = scraper.build_search_url(
        ktru_code="31.20.11.110",
        law="223",
    )
    print(f"Test 3 - 223-FZ law:\n{url3}\n")
    
    await scraper.close()
    
    return True


async def test_robots_check():
    """Test robots.txt checking."""
    print("=== Testing Robots.txt Check ===")
    
    async with ZakupkiSearchScraper() as scraper:
        crawl_delay = await scraper.check_robots_txt()
        print(f"Crawl delay from robots.txt: {crawl_delay}")
    
    return True


async def test_search_simulation():
    """Test search functionality (simulated - won't make actual requests)."""
    print("=== Testing Search Simulation ===")
    
    # Create a mock scraper for testing
    class MockScraper(ZakupkiSearchScraper):
        async def _make_request_with_retry(self, url: str):
            # Return mock HTML response
            mock_html = """
            <html>
                <body>
                    <div class="search-results__total">Найдено: 1 234</div>
                    <div class="search-registry-entry-block">
                        <div class="registry-entry__header-mid__number">
                            <a class="registry-entry__header-mid__number" href="/epz/order/notice/ea44/view/common-info.html?regNumber=123456789">№ 123456789</a>
                        </div>
                        <div class="data-block__value">15.01.2023</div>
                        <div class="price-block__value">1 234 567,89 руб.</div>
                    </div>
                    <div class="search-registry-entry-block">
                        <div class="registry-entry__header-mid__number">
                            <a class="registry-entry__header-mid__number" href="/epz/order/notice/ea44/view/common-info.html?regNumber=987654321">№ 987654321</a>
                        </div>
                        <div class="data-block__value">20.02.2023</div>
                        <div class="price-block__value">987 654,32 руб.</div>
                    </div>
                </body>
            </html>
            """
            return httpx.Response(200, content=mock_html.encode('utf-8'))
    
    async with MockScraper() as scraper:
        # Test parsing
        test_html = """
        <div class="search-results__total">Найдено: 2</div>
        <div class="search-registry-entry-block">
            <div class="registry-entry__header-mid__number">
                <a class="registry-entry__header-mid__number" href="/test/123">№ 123456789</a>
            </div>
            <div class="data-block__value">15.01.2023</div>
            <div class="price-block__value">1 234 567,89 руб.</div>
        </div>
        <div class="search-registry-entry-block">
            <div class="registry-entry__header-mid__number">
                <a class="registry-entry__header-mid__number" href="/test/456">№ 987/654</a>
            </div>
            <div class="data-block__value">20.02.2023</div>
            <div class="price-block__value">987 654,32 ₽</div>
        </div>
        """
        
        contracts, total = scraper._parse_search_results(test_html)
        print(f"Parsed {len(contracts)} contracts, total found: {total}")
        
        for i, contract in enumerate(contracts, 1):
            print(f"Contract {i}:")
            print(f"  Reestr Number: {contract['reestr_number']}")
            print(f"  URL: {contract['contract_url']}")
            print(f"  Date: {contract['sign_date']}")
            print(f"  Price: {contract['price']} {contract['currency']}")
            print()
    
    return True


async def main():
    """Run all tests."""
    print("Starting Zakupki Search Scraper tests...\n")
    
    try:
        # Test URL building
        await test_url_building()
        
        # Test robots.txt check (will make actual request)
        # await test_robots_check()
        
        # Test search simulation
        await test_search_simulation()
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    
    return True


if __name__ == "__main__":
    # Import httpx for mock test
    import httpx
    
    success = asyncio.run(main())
    exit(0 if success else 1)