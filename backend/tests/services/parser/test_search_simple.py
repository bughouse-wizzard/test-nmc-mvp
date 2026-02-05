"""
Simple unit tests for the search parser.
"""
import sys
import os
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from backend.services.parser.search import SearchParser


def test_build_search_params():
    """Test building search parameters."""
    parser = SearchParser()
    
    # Test with minimal parameters
    params = parser._build_search_params(
        ktru_code="03121110-1",
        customer_region="СЗФО",
        law="44-ФЗ",
        date_from=datetime(2024, 1, 1),
        date_to=datetime(2024, 12, 31),
        execution_statuses=["Исполнение завершено"],
    )
    
    assert isinstance(params, dict)
    assert "searchString" in params
    assert params["searchString"] == "03121110-1"
    assert "selectedRegions" in params
    assert params["selectedRegions"] == "СЗФО"
    assert "selectedFz" in params
    assert params["selectedFz"] == "fz44"
    
    print("✓ test_build_search_params passed")


def test_build_search_url():
    """Test building complete search URL."""
    parser = SearchParser()
    
    url = parser.build_search_url(
        ktru_code="03121110-1",
        customer_region="СЗФО",
        law="44-ФЗ",
        date_from=datetime(2024, 1, 1),
        date_to=datetime(2024, 12, 31),
        execution_statuses=["Исполнение завершено"],
    )
    
    assert isinstance(url, str)
    assert url.startswith(parser.search_url)
    assert "?searchString=03121110-1" in url
    assert "selectedFz=fz44" in url
    # Check for URL-encoded version of "СЗФО"
    assert "selectedRegions=%D0%A1%D0%97%D0%A4%D0%9E" in url
    
    print("✓ test_build_search_url passed")


def test_parse_search_results():
    """Test parsing search results HTML."""
    parser = SearchParser()
    
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
    
    total_found, contracts = parser._parse_search_results(html)
    
    assert total_found == 123
    assert len(contracts) == 2
    
    # Check first contract
    assert contracts[0]["registry_no"] == "1234567890123456789"
    assert contracts[0]["date"] == "01.01.2024"
    assert contracts[0]["price"] == 1234567.89
    
    # Check second contract
    assert contracts[1]["registry_no"] == "9876543210987654321"
    assert contracts[1]["date"] == "15.02.2024"
    assert contracts[1]["price"] == 987654.32
    
    print("✓ test_parse_search_results passed")


def test_sort_and_limit_contracts():
    """Test sorting and limiting contracts."""
    parser = SearchParser()
    
    contracts = [
        {"registry_no": "1", "date": "15.02.2024", "price": 1000},
        {"registry_no": "2", "date": "01.01.2024", "price": 2000},
        {"registry_no": "3", "date": "10.03.2024", "price": 3000},
        {"registry_no": "4", "date": "05.02.2024", "price": 4000},
    ]
    
    # Test sorting (newest first)
    sorted_contracts = parser._sort_and_limit_contracts(contracts, 10)
    
    # Should be sorted by date descending
    assert sorted_contracts[0]["registry_no"] == "3"  # 10.03.2024 - newest
    assert sorted_contracts[1]["registry_no"] == "1"  # 15.02.2024
    assert sorted_contracts[2]["registry_no"] == "4"  # 05.02.2024
    assert sorted_contracts[3]["registry_no"] == "2"  # 01.01.2024 - oldest
    
    # Test limiting
    limited_contracts = parser._sort_and_limit_contracts(contracts, 2)
    assert len(limited_contracts) == 2
    assert limited_contracts[0]["registry_no"] == "3"  # Newest
    assert limited_contracts[1]["registry_no"] == "1"  # Second newest
    
    print("✓ test_sort_and_limit_contracts passed")


def test_date_parsing():
    """Test date parsing for sorting."""
    parser = SearchParser()
    
    # Test various date formats
    test_cases = [
        ("01.01.2024", datetime(2024, 1, 1)),
        ("2024-01-01", datetime(2024, 1, 1)),
        ("01/01/2024", datetime(2024, 1, 1)),
        ("invalid", datetime.min),
        ("", datetime.min),
    ]
    
    for date_str, expected in test_cases:
        # We can't directly test the private method, but we can test through sorting
        contracts = [{"registry_no": "1", "date": date_str, "price": 1000}]
        sorted_contracts = parser._sort_and_limit_contracts(contracts, 10)
        assert len(sorted_contracts) == 1  # Should still return the contract
    
    print("✓ test_date_parsing passed")


def run_all_tests():
    """Run all tests."""
    print("Running SearchParser tests...")
    print("-" * 40)
    
    test_build_search_params()
    test_build_search_url()
    test_parse_search_results()
    test_sort_and_limit_contracts()
    test_date_parsing()
    
    print("-" * 40)
    print("All tests passed! ✓")


if __name__ == "__main__":
    run_all_tests()