"""
Test module for ContractParser.
"""

import asyncio
import logging
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from contract import ContractParser, create_contract_parser
except ImportError:
    # For direct execution
    from .contract import ContractParser, create_contract_parser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_contract_parser_basic():
    """Test basic functionality of ContractParser."""
    print("Testing ContractParser basic functionality...")
    
    # Create parser instance
    parser = ContractParser(
        base_url="https://zakupki.gov.ru",
        temp_dir="/tmp/test_contract_parser"
    )
    
    try:
        # Test URL construction
        test_url = "https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber=123456"
        common_info_url = parser._get_common_info_url(test_url)
        print(f"Common info URL: {common_info_url}")
        
        # Test year extraction
        test_common_info = {"sign_date": "15.12.2023"}
        year = parser._extract_contract_year(test_common_info)
        print(f"Extracted year: {year}")
        assert year == 2023, f"Expected 2023, got {year}"
        
        # Test currency extraction
        test_prices = [
            ("100 USD", "USD"),
            ("200 €", "EUR"),
            ("300 РУБ", "RUB"),
            ("400 ₽", "RUB"),
            ("500", "RUB"),  # Default
        ]
        
        for price_str, expected_currency in test_prices:
            currency = parser._extract_currency(price_str)
            print(f"Price: {price_str} -> Currency: {currency}")
            assert currency == expected_currency, f"Expected {expected_currency}, got {currency}"
        
        print("✓ Basic tests passed!")
        
    finally:
        # Cleanup
        await parser.cleanup()


async def test_factory_function():
    """Test the factory function."""
    print("\nTesting factory function...")
    
    parser = await create_contract_parser(
        temp_dir="/tmp/test_factory_parser",
        year_threshold=2024
    )
    
    try:
        assert parser.base_url == "https://zakupki.gov.ru"
        assert parser.year_threshold == 2024
        assert parser.http_client is not None
        print("✓ Factory function test passed!")
        
    finally:
        await parser.cleanup()


async def test_parser_structure():
    """Test that parser has all required methods."""
    print("\nTesting parser structure...")
    
    parser = ContractParser()
    
    required_methods = [
        'parse_contract',
        '_get_common_info_url',
        '_parse_common_info',
        '_parse_specification',
        '_identify_attachments',
        '_download_printed_form',
        '_extract_unit_prices',
        '_extract_contract_year',
        '_extract_currency',
        '_fetch_html',
        '_download_file',
        'cleanup'
    ]
    
    for method_name in required_methods:
        assert hasattr(parser, method_name), f"Missing method: {method_name}"
        print(f"✓ Method present: {method_name}")
    
    print("✓ Parser structure test passed!")
    
    await parser.cleanup()


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Running ContractParser tests")
    print("=" * 60)
    
    try:
        await test_parser_structure()
        await test_contract_parser_basic()
        await test_factory_function()
        
        print("\n" + "=" * 60)
        print("All tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())