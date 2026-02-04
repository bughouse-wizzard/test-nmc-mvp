#!/usr/bin/env python3
"""
Example usage of the Zakupki Search Scraper.

This script demonstrates how to use the scraper to search for contracts
on zakupki.gov.ru with the required parameters:
- 44-FZ law
- Status: Executed
- Region: SZFO (Northwestern Federal District)
- Date range: Last 3 years
- KTRU classification

NOTE: This is a demonstration script that shows the API usage.
For actual scraping, you would need to handle authentication,
rate limiting, and ensure compliance with the website's terms of service.
"""

import asyncio
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Example usage of the scraper."""
    print("=== Zakupki Search Scraper Example ===\n")
    
    # Example KTRU code (Medical equipment category)
    ktru_code = "31.20.11.110"  # Example: Medical equipment
    
    # Calculate date range: last 3 years
    date_to = datetime.now()
    date_from = date_to - timedelta(days=3*365)
    
    print(f"Search parameters:")
    print(f"  KTRU Code: {ktru_code}")
    print(f"  Law: 44-FZ")
    print(f"  Status: Executed contracts")
    print(f"  Region: SZFO (Northwestern Federal District)")
    print(f"  Date range: {date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}")
    print(f"  Max pages: 2 (for demonstration)")
    print()
    
    # Demonstrate URL building
    print("Example URL that would be generated:")
    from app.services.scraper.search import ZakupkiSearchScraper
    scraper = ZakupkiSearchScraper()
    example_url = scraper.build_search_url(
        ktru_code=ktru_code,
        date_from=date_from,
        date_to=date_to,
        law="44",
        execution_status="Исполнение завершено",
        region="СЗФО",
        page=1,
        page_size=50,
    )
    print(f"  {example_url[:100]}...")
    print()
    
    # Show example of what would be returned
    print("Example of data that would be extracted:")
    print()
    
    # Mock data for demonstration
    mock_contracts = [
        {
            "reestr_number": "123456789",
            "contract_url": "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=123456789",
            "sign_date": "2023-05-15T00:00:00",
            "price": 1250000.50,
            "currency": "RUB"
        },
        {
            "reestr_number": "987654321",
            "contract_url": "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=987654321",
            "sign_date": "2023-08-22T00:00:00",
            "price": 875430.75,
            "currency": "RUB"
        },
        {
            "reestr_number": "456789123/2023",
            "contract_url": "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html?regNumber=456789123",
            "sign_date": "2024-01-10T00:00:00",
            "price": 2345678.90,
            "currency": "RUB"
        }
    ]
    
    print(f"Total contracts found: 42 (example)")
    print(f"Contracts retrieved: {len(mock_contracts)} (sample)")
    print()
    
    print("Sample contracts:")
    for i, contract in enumerate(mock_contracts, 1):
        print(f"\nContract {i}:")
        print(f"  Reestr Number: {contract['reestr_number']}")
        print(f"  URL: {contract['contract_url']}")
        print(f"  Date: {contract['sign_date']}")
        print(f"  Price: {contract['price']:,.2f} {contract['currency']}")
    
    # Show summary statistics
    total_price = sum(c['price'] for c in mock_contracts)
    avg_price = total_price / len(mock_contracts)
    print(f"\nSummary (based on sample):")
    print(f"  Total value: {total_price:,.2f} RUB")
    print(f"  Average price: {avg_price:,.2f} RUB")
    
    print("\n=== Example completed ===")
    
    # Close the scraper
    await scraper.close()


if __name__ == "__main__":
    # Note: This example won't make actual HTTP requests in this test environment
    # To actually run it against the real website, you would need to:
    # 1. Remove or modify the MockScraper in test_search_scraper.py
    # 2. Be aware of rate limiting and terms of service
    # 3. Add proper error handling for network issues
    
    print("Note: This is a demonstration script.")
    print("To run against the actual zakupki.gov.ru website,")
    print("you would need to handle authentication, rate limiting,")
    print("and ensure compliance with the website's terms of service.")
    print()
    
    # Run the example
    asyncio.run(main())