#!/usr/bin/env python3
"""Test script for ZakupkiSearchScraper."""

import asyncio
import logging
from datetime import datetime, timedelta

from app.services.scraper.search import ZakupkiSearchScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_scraper():
    """Test the ZakupkiSearchScraper."""
    scraper = ZakupkiSearchScraper()
    
    try:
        # Test 1: Basic search with SZFO region
        print("Test 1: Basic search with SZFO region")
        search_params = {
            "search_string": "КТРУ",  # KTRU codes
            "status": "EXECUTED",
            "region": "SZFO",
            "date_from": (datetime.now() - timedelta(days=3*365)).strftime("%d.%m.%Y"),
            "date_to": datetime.now().strftime("%d.%m.%Y"),
            "page_number": 1
        }
        
        print(f"Search parameters: {search_params}")
        url = scraper.build_search_url(search_params)
        print(f"Generated URL: {url[:100]}...")  # Print first 100 chars
        
        # Test 2: URL building with different parameters
        print("\nTest 2: URL building with different parameters")
        search_params2 = {
            "search_string": "компьютер",
            "status": "EXECUTED",
            "region": "5277359",  # Saint Petersburg
            "page_number": 2
        }
        
        url2 = scraper.build_search_url(search_params2)
        print(f"Generated URL 2: {url2[:100]}...")
        
        # Test 3: Check SZFO regions are included
        print("\nTest 3: Checking SZFO regions in URL")
        # URL encode the region parameter
        import urllib.parse
        encoded_region = urllib.parse.quote("5277335")
        if f"regions%5B1%5D={encoded_region}" in url:  # First SZFO region (URL encoded)
            print("✓ SZFO regions are correctly included in URL")
        else:
            print("✗ SZFO regions not found in URL")
            print(f"Looking for: regions%5B1%5D={encoded_region}")
            print(f"In URL: {url[:200]}...")
        
        # Test 4: Check 44-FZ parameter
        if "fz44=on" in url:
            print("✓ 44-FZ parameter is correctly set")
        else:
            print("✗ 44-FZ parameter not found")
        
        # Test 5: Check status parameter
        if "contractStage=EXECUTED" in url:
            print("✓ Status=EXECUTED parameter is correctly set")
        else:
            print("✗ Status parameter not found")
        
        # Note: We're not making actual HTTP requests in this test
        # to avoid hitting the website during testing
        print("\nNote: Actual HTTP requests are disabled in this test")
        print("to avoid hitting the zakupki.gov.ru website.")
        print("The scraper implementation includes:")
        print("- URL building with all required parameters")
        print("- HTTP client with retry/backoff logic")
        print("- HTML parsing for contract extraction")
        print("- Robots.txt compliance (1 second delay between requests)")
        
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(test_scraper())