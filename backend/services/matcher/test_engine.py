"""
Test file for the matcher engine.
"""

import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from backend.services.matcher.engine import (
    NormalizationEngine,
    ComparisonEngine,
    MatcherEngine,
    MatchStatus,
    NormalizedValue
)


def test_normalization_engine():
    """Test normalization functionality."""
    print("Testing NormalizationEngine...")
    
    # Test text normalization
    assert NormalizationEngine.normalize_text("  Hello WORLD  ") == "hello world"
    assert NormalizationEngine.normalize_text("") == ""
    assert NormalizationEngine.normalize_text(None) == ""
    
    # Test number and unit extraction
    result = NormalizationEngine.extract_number_and_unit("100ml")
    assert result.value == 100.0
    assert result.unit == "ml"
    assert result.original == "100ml"
    
    result = NormalizationEngine.extract_number_and_unit("500 g")
    assert result.value == 500.0
    assert result.unit == "g"
    
    result = NormalizationEngine.extract_number_and_unit("2.5 liters")
    assert result.value == 2.5
    assert result.unit == "l"
    
    result = NormalizationEngine.extract_number_and_unit("just text")
    assert result.value == "just text"
    assert result.unit is None
    
    # Test manufacturer normalization
    # Note: "ООО" should be removed from the beginning
    result = NormalizationEngine.normalize_manufacturer("ООО Рога и Копыта")
    assert result == "рога и копыта", f"Expected 'рога и копыта', got '{result}'"
    
    result = NormalizationEngine.normalize_manufacturer("Apple Inc.")
    assert result == "apple", f"Expected 'apple', got '{result}'"
    
    # Test that "Company" is also removed as it's a common suffix
    result = NormalizationEngine.normalize_manufacturer("LLC Test Company")
    assert result == "test", f"Expected 'test', got '{result}'"
    
    # Test that "Corp" is also removed
    result = NormalizationEngine.normalize_manufacturer("GmbH German Corp")
    assert result == "german", f"Expected 'german', got '{result}'"
    
    assert NormalizationEngine.normalize_manufacturer("") == ""
    
    print("✓ NormalizationEngine tests passed!")


def test_comparison_engine():
    """Test comparison functionality."""
    print("\nTesting ComparisonEngine...")
    
    # Test number comparison
    status, similarity = ComparisonEngine.compare_numbers(100, 105, tolerance=0.05)
    assert status == MatchStatus.MATCH
    assert similarity > 0.95
    
    status, similarity = ComparisonEngine.compare_numbers(100, 150, tolerance=0.05)
    assert status == MatchStatus.DIFF
    assert similarity < 0.7
    
    # Test string comparison
    status, similarity = ComparisonEngine.compare_strings("hello", "hello")
    assert status == MatchStatus.MATCH
    assert similarity == 1.0
    
    status, similarity = ComparisonEngine.compare_strings("hello", "helo")
    assert status == MatchStatus.MATCH  # Should match with default threshold (0.8)
    assert similarity >= 0.8  # Similarity is exactly 0.8 for this case
    
    status, similarity = ComparisonEngine.compare_strings("hello", "world")
    assert status == MatchStatus.DIFF
    assert similarity < 0.5
    
    # Test normalized value comparison
    target = NormalizedValue(value=100, unit="ml")
    actual = NormalizedValue(value=105, unit="ml")
    status, similarity = ComparisonEngine.compare_normalized_values(target, actual)
    assert status == MatchStatus.MATCH
    
    target = NormalizedValue(value=100, unit="ml")
    actual = NormalizedValue(value=100, unit="g")
    status, similarity = ComparisonEngine.compare_normalized_values(target, actual)
    assert status == MatchStatus.DIFF
    
    # Test manufacturer comparison
    match, similarity = ComparisonEngine.compare_manufacturers(
        "ООО Рога и Копыта", 
        "Рога и Копыта ООО"
    )
    assert match is True
    assert similarity > 0.8
    
    match, similarity = ComparisonEngine.compare_manufacturers(
        "Apple Inc.",
        "Microsoft Corp."
    )
    assert match is False
    
    print("✓ ComparisonEngine tests passed!")


def test_matcher_engine():
    """Test the main matcher engine."""
    print("\nTesting MatcherEngine...")
    
    matcher = MatcherEngine(
        numeric_tolerance=0.05,
        string_threshold=0.8,
        manufacturer_threshold=0.7
    )
    
    # Test creating spec comparison row
    row = matcher.create_spec_comparison_row(
        name="Объем",
        target_value="100ml",
        actual_value="105ml",
        weight=2
    )
    
    assert row["name"] == "Объем"
    assert row["target_value"] == "100ml"
    assert row["actual_value"] == "105ml"
    assert row["match_status"] in ["MATCH", "DIFF", "UNKNOWN"]
    assert row["weight"] == 2
    assert "similarity_score" in row
    assert "normalized_target" in row
    assert "normalized_actual" in row
    
    # Test manufacturer comparison
    manufacturer_result = matcher.compare_manufacturers(
        target_manufacturer="ООО Рога и Копыта",
        found_manufacturer="Рога и Копыта"
    )
    
    assert "target_manufacturer" in manufacturer_result
    assert "found_manufacturer" in manufacturer_result
    assert "match" in manufacturer_result
    assert "similarity_score" in manufacturer_result
    
    # Test combining with AI results
    heuristic_results = {
        "comparison_rows": [row],
        "manufacturer_comparison": manufacturer_result,
        "overall_similarity": 0.85
    }
    
    ai_results = {
        "confidence_score": 90,
        "ai_match_type": "IDENTICAL"
    }
    
    combined = matcher.combine_with_ai_results(heuristic_results, ai_results)
    
    assert "spec_comparison_rows" in combined
    assert "manufacturer_comparison" in combined
    assert "overall_match_score" in combined
    assert "heuristic_weight" in combined
    assert "ai_weight" in combined
    
    # Verify the combined score calculation
    expected_score = 0.85 * 0.4 + 0.9 * 0.6  # 0.85 * 0.4 + 0.9 * 0.6
    assert abs(combined["overall_match_score"] - expected_score) < 0.01
    
    print("✓ MatcherEngine tests passed!")


def test_integration_with_spec_comparison_row():
    """Test that the output can be used with SpecComparisonRow model."""
    print("\nTesting integration with SpecComparisonRow model...")
    
    matcher = MatcherEngine()
    
    # Create sample comparison data
    rows = []
    test_cases = [
        ("Объем", "100ml", "105ml", 2),
        ("Вес", "500g", "500g", 1),
        ("Цвет", "красный", "красный", 1),
        ("Производитель", "ООО Тест", "Тест ООО", 3),
    ]
    
    for name, target, actual, weight in test_cases:
        row = matcher.create_spec_comparison_row(name, target, actual, weight)
        rows.append(row)
    
    # Verify the structure matches what SpecComparisonRow expects
    for row in rows:
        # Check required fields for SpecComparisonRow
        assert "name" in row
        assert "target_value" in row
        assert "actual_value" in row
        assert "match_status" in row
        assert "weight" in row
        
        # Verify match_status is one of the expected values
        assert row["match_status"] in ["MATCH", "DIFF", "UNKNOWN"]
        
        # Verify weight is positive integer
        assert isinstance(row["weight"], int)
        assert row["weight"] >= 1
    
    print("✓ Integration with SpecComparisonRow model tests passed!")


if __name__ == "__main__":
    print("Running matcher engine tests...")
    print("=" * 50)
    
    test_normalization_engine()
    test_comparison_engine()
    test_matcher_engine()
    test_integration_with_spec_comparison_row()
    
    print("\n" + "=" * 50)
    print("All tests passed successfully!")