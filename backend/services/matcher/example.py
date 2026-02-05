#!/usr/bin/env python3
"""
Example usage of the MatcherEngine for normalization and heuristic matching.

This script demonstrates how to use the MatcherEngine to:
1. Normalize values with units
2. Compare values using heuristic matching
3. Compare manufacturer names
4. Combine heuristic and AI results for specification comparison
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.matcher.engine import MatcherEngine


def main():
    """Main example function."""
    print("=== MatcherEngine Example ===\n")
    
    # Initialize the matcher engine
    matcher = MatcherEngine()
    
    # Example 1: Basic value normalization
    print("1. Value Normalization Examples:")
    print("-" * 40)
    test_values = [
        "100мл", "5.5 кг", "10-20 м", ">50 г",
        "100 мл", "2 шт", "3 ед", "10-20см", "5,5л"
    ]
    
    for val in test_values:
        norm = matcher.normalize_value(val)
        print(f"  '{val}' ->")
        print(f"    Numeric: {norm.numeric_value}, Unit: '{norm.unit}', Is numeric: {norm.is_numeric}")
    print()
    
    # Example 2: Value comparison
    print("2. Value Comparison Examples:")
    print("-" * 40)
    test_pairs = [
        ("100мл", "100 мл"),
        ("5.5 кг", "5.0 кг"),
        ("10 м", "9.5 м"),
        ("2 шт", "2 штуки"),
        ("сталь", "нержавеющая сталь"),
        ("красный", "синий"),
    ]
    
    for target, actual in test_pairs:
        result = matcher.compare_values(target, actual)
        status_icon = "✓" if result.match_status == 'MATCH' else "✗" if result.match_status == 'DIFF' else "?"
        print(f"  {status_icon} '{target}' vs '{actual}'")
        print(f"    Status: {result.match_status}, Confidence: {result.confidence:.2f}")
    print()
    
    # Example 3: Manufacturer comparison
    print("3. Manufacturer Comparison Examples:")
    print("-" * 40)
    manufacturer_pairs = [
        ("ООО 'Ромашка'", "ООО Ромашка"),
        ("АО 'Технопром'", "Технопром"),
        ("ИП Иванов", "ООО Иванов"),
        ("Siemens AG", "Siemens"),
    ]
    
    for target, found in manufacturer_pairs:
        result = matcher.compare_manufacturers(target, found)
        status_icon = "✓" if result['match'] else "✗"
        print(f"  {status_icon} '{target}' vs '{found}'")
        print(f"    Match: {result['match']}, Confidence: {result['confidence']:.2f}")
    print()
    
    # Example 4: Complete specification matching
    print("4. Complete Specification Matching Example:")
    print("-" * 40)
    
    # Target specifications from requirements
    target_specs = {
        "Объем": "100мл",
        "Вес": "5.5 кг",
        "Материал": "сталь нержавеющая",
        "Цвет": "красный",
        "Количество": "2 шт",
        "Длина": "10 м",
        "Толщина": "5 мм"
    }
    
    # Actual specifications from contract
    actual_specs = {
        "Объем": "100 мл",
        "Вес": "5.0 кг",
        "Материал": "нержавеющая сталь AISI 304",
        "Производитель": "ООО 'Технопром'",
        "Количество": "2 штуки",
        "Длина": "9.5 м",
        "Толщина": "5 миллиметров"
    }
    
    # AI confidence scores (from AI analysis)
    ai_scores = {
        "Объем": 0.95,
        "Вес": 0.85,
        "Материал": 0.75,
        "Количество": 0.90,
        "Длина": 0.80,
        "Толщина": 0.88
    }
    
    # Run complete matching
    result = matcher.match_specifications(
        target_specs=target_specs,
        actual_specs=actual_specs,
        target_manufacturer="ООО 'Технопром'",
        found_manufacturer="Технопром",
        ai_scores=ai_scores
    )
    
    # Print summary
    summary = result['summary']
    print(f"  Summary:")
    print(f"    Total specifications: {summary['total_specs']}")
    print(f"    Matches: {summary['match_count']}")
    print(f"    Differences: {summary['diff_count']}")
    print(f"    Unknown: {summary['unknown_count']}")
    print(f"    Average confidence: {summary['avg_confidence']:.2f}")
    print(f"    Manufacturer match: {summary['manufacturer_match']}")
    print(f"    Manufacturer confidence: {summary['manufacturer_confidence']:.2f}")
    print()
    
    # Print detailed results
    print("  Detailed results:")
    for spec in result['spec_comparisons']:
        status_icon = "✓" if spec['match_status'] == 'MATCH' else "✗" if spec['match_status'] == 'DIFF' else "?"
        target = spec['target_value'] if spec['target_value'] else "(not specified)"
        actual = spec['actual_value'] if spec['actual_value'] else "(not found)"
        print(f"    {status_icon} {spec['name']}: {target} vs {actual}")
        print(f"      Status: {spec['match_status']}, Confidence: {spec['confidence']:.2f}")
    
    print("\n=== Example Complete ===")


if __name__ == "__main__":
    main()