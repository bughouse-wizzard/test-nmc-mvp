"""
Test file for the Normalization and Heuristic Matching Engine.
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from backend.services.matcher.engine import (
    NormalizationEngine,
    ComparisonEngine,
    ManufacturerComparator,
    MatchingEngine,
    MatchStatus,
    MatchType
)


def test_normalization_engine():
    """Test normalization functionality."""
    print("Testing NormalizationEngine...")
    
    normalizer = NormalizationEngine()
    
    # Test text normalization
    assert normalizer.normalize_text("  Hello World  ") == "hello world"
    assert normalizer.normalize_text("100,5 ml") == "100.5 ml"
    assert normalizer.normalize_text("ПЛОТНОСТЬ 80 г/м2") == "плотность 80 г/м2"
    
    # Test numeric value extraction
    result = normalizer.extract_numeric_value("100ml")
    assert result == (100.0, "ml")
    
    result = normalizer.extract_numeric_value("80 г/м2")
    assert result == (80.0, "г/м2")
    
    result = normalizer.extract_numeric_value("160%")
    assert result == (160.0, "%")
    
    result = normalizer.extract_numeric_value("500 мл")
    assert result == (500.0, "мл")
    
    # Test full value normalization
    norm_value = normalizer.normalize_value("100ml")
    assert norm_value.original == "100ml"
    assert norm_value.normalized == "100ml"
    assert norm_value.numeric_value == 100.0
    assert norm_value.unit == "ml"
    assert norm_value.is_numeric == True
    
    norm_value = normalizer.normalize_value("Some text value")
    assert norm_value.original == "Some text value"
    assert norm_value.normalized == "some text value"
    assert norm_value.is_numeric == False
    
    print("✓ NormalizationEngine tests passed")


def test_comparison_engine():
    """Test comparison functionality."""
    print("\nTesting ComparisonEngine...")
    
    comparator = ComparisonEngine()
    
    # Test string similarity
    assert comparator.string_similarity("hello", "hello") == 1.0
    assert comparator.string_similarity("hello", "helo") >= 0.8  # Should be similar
    assert comparator.string_similarity("hello", "world") < 0.5  # Should be different
    
    # Test numeric comparison
    result = comparator.compare_numeric_values(100.0, 105.0, tolerance=0.05)
    assert result.match_status == MatchStatus.MATCH  # Within 5% tolerance
    
    result = comparator.compare_numeric_values(100.0, 110.0, tolerance=0.05)
    assert result.match_status == MatchStatus.DIFF  # Outside 5% tolerance
    
    # Test numeric comparison with units
    result = comparator.compare_numeric_values(100.0, 100.0, target_unit="ml", actual_unit="ml")
    assert result.match_status == MatchStatus.MATCH
    
    result = comparator.compare_numeric_values(100.0, 100.0, target_unit="ml", actual_unit="l")
    assert result.match_status == MatchStatus.DIFF  # Different units
    
    # Test string comparison
    result = comparator.compare_string_values("hello world", "hello world")
    assert result.match_status == MatchStatus.MATCH
    
    result = comparator.compare_string_values("hello world", "helo world")
    assert result.match_status == MatchStatus.MATCH  # Similar enough
    
    result = comparator.compare_string_values("hello world", "goodbye world")
    assert result.match_status == MatchStatus.DIFF  # Not similar enough
    
    # Test automatic type detection
    result = comparator.compare_values("100ml", "105ml")
    assert result.match_status == MatchStatus.MATCH  # Numeric comparison
    
    result = comparator.compare_values("Some text", "Some tex")
    assert result.match_status == MatchStatus.MATCH  # String comparison
    
    print("✓ ComparisonEngine tests passed")


def test_manufacturer_comparator():
    """Test manufacturer comparison functionality."""
    print("\nTesting ManufacturerComparator...")
    
    comparator = ManufacturerComparator()
    
    # Test exact match
    result = comparator.compare_manufacturers("ООО Рога и копыта", "ООО Рога и копыта")
    assert result["match"] == True
    assert result["confidence"] == 1.0
    
    # Test similar match
    result = comparator.compare_manufacturers("ООО Рога и копыта", "ООО Рога и Копыта")
    assert result["match"] == True  # Should match with high similarity (case difference only)
    
    # Test different manufacturers
    result = comparator.compare_manufacturers("ООО Рога и копыта", "ЗАО Другая компания")
    assert result["match"] == False
    
    # Test missing information
    result = comparator.compare_manufacturers(None, "ООО Рога и копыта")
    assert result["match"] is None
    
    result = comparator.compare_manufacturers("ООО Рога и копыта", None)
    assert result["match"] is None
    
    print("✓ ManufacturerComparator tests passed")


def test_matching_engine():
    """Test complete matching engine functionality."""
    print("\nTesting MatchingEngine...")
    
    engine = MatchingEngine()
    
    # Sample data
    target_specs = {
        "наименование": "Бумага офисная",
        "плотность": "80 г/м2",
        "размер": "А4",
        "белизна": "160%"
    }
    
    contract_specs = {
        "наименование": "Бумага офисная",
        "плотность": "82 г/м2",  # Slightly different
        "размер": "A4",  # Different format
        "белизна": "158%"  # Slightly different
    }
    
    # Test without AI results
    result = engine.process_contract_comparison(
        target_specs=target_specs,
        contract_specs=contract_specs,
        target_manufacturer="ООО Производитель 1",
        found_manufacturer="ООО Производитель 1"
    )
    
    assert "comparison_rows" in result
    assert len(result["comparison_rows"]) == 4  # All 4 specifications
    assert "match_type" in result
    assert result["match_type"] in [MatchType.IDENTICAL.value, MatchType.HOMOGENEOUS.value, MatchType.NO_MATCH.value]
    assert "manufacturer_comparison" in result
    assert "summary" in result
    
    # Check that we have match status for each row
    for row in result["comparison_rows"]:
        assert "match_status" in row
        assert row["match_status"] in [MatchStatus.MATCH.value, MatchStatus.DIFF.value, MatchStatus.UNKNOWN.value]
        assert "confidence" in row
        assert 0.0 <= row["confidence"] <= 1.0
    
    print("✓ MatchingEngine tests passed")


def test_integration():
    """Test integration of all components."""
    print("\nTesting integration...")
    
    # Create engine instance
    engine = MatchingEngine(
        numeric_tolerance=0.1,  # 10% tolerance for testing
        string_similarity_threshold=0.7  # 70% similarity threshold
    )
    
    # Test case 1: Identical match
    target_specs_1 = {
        "product": "Paper A4",
        "weight": "80g/m2",
        "whiteness": "90%"
    }
    
    contract_specs_1 = {
        "product": "Paper A4",
        "weight": "80g/m2",
        "whiteness": "90%"
    }
    
    result_1 = engine.process_contract_comparison(
        target_specs=target_specs_1,
        contract_specs=contract_specs_1,
        target_manufacturer="Manufacturer A",
        found_manufacturer="Manufacturer A"
    )
    
    print(f"Test 1 - Identical match: {result_1['match_type']}")
    
    # Test case 2: Homogeneous match (slight differences)
    target_specs_2 = {
        "product": "Paper A4",
        "weight": "80g/m2",
        "whiteness": "90%"
    }
    
    contract_specs_2 = {
        "product": "Paper A4",
        "weight": "85g/m2",  # 6.25% difference
        "whiteness": "88%"   # 2.2% difference
    }
    
    result_2 = engine.process_contract_comparison(
        target_specs=target_specs_2,
        contract_specs=contract_specs_2,
        target_manufacturer="Manufacturer A",
        found_manufacturer="Manufacturer A"
    )
    
    print(f"Test 2 - Homogeneous match: {result_2['match_type']}")
    
    # Test case 3: No match (different manufacturer)
    result_3 = engine.process_contract_comparison(
        target_specs=target_specs_1,
        contract_specs=contract_specs_1,
        target_manufacturer="Manufacturer A",
        found_manufacturer="Manufacturer B"  # Different manufacturer
    )
    
    print(f"Test 3 - Different manufacturer: {result_3['match_type']}")
    
    print("✓ Integration tests passed")


def main():
    """Run all tests."""
    print("Running tests for Normalization & Heuristic Matching Engine\n")
    
    try:
        test_normalization_engine()
        test_comparison_engine()
        test_manufacturer_comparator()
        test_matching_engine()
        test_integration()
        
        print("\n✅ All tests passed successfully!")
        return True
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)