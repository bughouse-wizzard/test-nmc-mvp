"""
Normalization & Match Engine for NMCK calculation system.

This module provides functions for normalizing values, calculating similarity,
and classifying matches between target and actual specification values.
"""

import re
from typing import Dict, Optional, Tuple, Any
from rapidfuzz import fuzz


def normalize_value(value: str) -> Dict[str, Optional[Any]]:
    """
    Normalize a string value by extracting numeric value and unit.
    
    Args:
        value: Input string value (e.g., '10 kg', '10,5 m', '100.5cm')
        
    Returns:
        Dictionary with keys:
        - 'original': Original input string
        - 'normalized': Lowercase version with commas replaced by dots
        - 'numeric_value': Extracted numeric value as float or None
        - 'unit': Extracted unit string or None
        - 'has_numeric': Boolean indicating if numeric value was found
        - 'has_unit': Boolean indicating if unit was found
    
    Examples:
        >>> normalize_value('10 kg')
        {'original': '10 kg', 'normalized': '10 kg', 'numeric_value': 10.0, 'unit': 'kg', 'has_numeric': True, 'has_unit': True}
        
        >>> normalize_value('10,500 г')
        {'original': '10,500 г', 'normalized': '10.500 г', 'numeric_value': 10.5, 'unit': 'г', 'has_numeric': True, 'has_unit': True}
        
        >>> normalize_value('text only')
        {'original': 'text only', 'normalized': 'text only', 'numeric_value': None, 'unit': None, 'has_numeric': False, 'has_unit': False}
    """
    if not value or not isinstance(value, str):
        return {
            'original': value,
            'normalized': value,
            'numeric_value': None,
            'unit': None,
            'has_numeric': False,
            'has_unit': False
        }
    
    # Step 1: Convert to lowercase and replace commas with dots
    normalized = value.lower().strip()
    normalized = normalized.replace(',', '.')
    
    # Step 2: Try to extract numeric value and unit
    numeric_value = None
    unit = None
    
    # Pattern to match numbers (including decimals and scientific notation)
    # and optional unit after the number
    number_pattern = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'
    
    # Try to find number at the beginning
    match = re.match(f'^({number_pattern})\\s*(.*)$', normalized)
    if match:
        try:
            numeric_value = float(match.group(1))
            unit = match.group(2).strip() if match.group(2).strip() else None
        except (ValueError, TypeError):
            pass
    
    # If no match at beginning, try to find number anywhere
    if numeric_value is None:
        match = re.search(f'({number_pattern})', normalized)
        if match:
            try:
                numeric_value = float(match.group(1))
                # Try to extract unit after the number
                after_num = normalized[match.end():].strip()
                if after_num:
                    # Take first word as unit
                    unit_match = re.match(r'^(\S+)', after_num)
                    if unit_match:
                        unit = unit_match.group(1)
            except (ValueError, TypeError):
                pass
    
    return {
        'original': value,
        'normalized': normalized,
        'numeric_value': numeric_value,
        'unit': unit,
        'has_numeric': numeric_value is not None,
        'has_unit': unit is not None and unit != ''
    }


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Calculate similarity between two strings using fuzzy matching.
    
    Args:
        str1: First string
        str2: Second string
        
    Returns:
        Similarity score between 0 and 100
        
    Examples:
        >>> calculate_similarity('10 kg', '10 kilograms')
        85.0  # approximate value
        
        >>> calculate_similarity('steel pipe', 'steel tube')
        90.0  # approximate value
    """
    if not str1 or not str2:
        return 0.0
    
    # Use token sort ratio which is good for strings with same words in different order
    return fuzz.token_sort_ratio(str1, str2)


def classify_match(
    target: str, 
    actual: str, 
    ai_result: Optional[Dict[str, Any]] = None,
    numeric_tolerance: float = 0.1,
    similarity_threshold_identical: float = 95.0,
    similarity_threshold_homogeneous: float = 80.0
) -> str:
    """
    Classify match between target and actual values.
    
    Args:
        target: Target value from requirements
        actual: Actual value from contract
        ai_result: Optional JSON result from AI analysis with additional metadata
        numeric_tolerance: Tolerance for numeric comparisons (relative difference)
        similarity_threshold_identical: Threshold for IDENTICAL classification
        similarity_threshold_homogeneous: Threshold for HOMOGENEOUS classification
        
    Returns:
        Match classification: 'IDENTICAL', 'HOMOGENEOUS', or 'DIFFERENT'
        
    Logic:
    1. If AI result has specific key parameters that match within tolerance -> IDENTICAL
    2. If functional parameters match -> HOMOGENEOUS
    3. Otherwise use fuzzy matching with thresholds
    """
    # Normalize both values
    target_norm = normalize_value(target)
    actual_norm = normalize_value(actual)
    
    # Check if AI result provides classification
    if ai_result:
        # Check for specific key parameters match (e.g., dimensions, weight, material)
        key_params_match = _check_key_parameters_match(ai_result, numeric_tolerance)
        if key_params_match:
            return 'IDENTICAL'
        
        # Check for functional parameters match
        functional_match = _check_functional_match(ai_result)
        if functional_match:
            return 'HOMOGENEOUS'
    
    # If both have numeric values, compare them
    if target_norm['has_numeric'] and actual_norm['has_numeric']:
        target_val = target_norm['numeric_value']
        actual_val = actual_norm['numeric_value']
        
        if target_val is not None and actual_val is not None:
            # Calculate relative difference
            if target_val == 0 and actual_val == 0:
                numeric_match = True
            elif target_val == 0 or actual_val == 0:
                numeric_match = False
            else:
                rel_diff = abs(target_val - actual_val) / max(abs(target_val), abs(actual_val))
                numeric_match = rel_diff <= numeric_tolerance
            
            # If numeric values match within tolerance and units are compatible
            if numeric_match:
                # Check units
                if target_norm['unit'] and actual_norm['unit']:
                    # Simple unit compatibility check (could be enhanced)
                    unit_similarity = calculate_similarity(
                        target_norm['unit'] or '', 
                        actual_norm['unit'] or ''
                    )
                    if unit_similarity >= similarity_threshold_identical:
                        return 'IDENTICAL'
                    elif unit_similarity >= similarity_threshold_homogeneous:
                        return 'HOMOGENEOUS'
                else:
                    # No units or one missing, consider identical if numeric match
                    return 'IDENTICAL'
    
    # Use fuzzy matching on normalized strings
    similarity = calculate_similarity(target_norm['normalized'], actual_norm['normalized'])
    
    if similarity >= similarity_threshold_identical:
        return 'IDENTICAL'
    elif similarity >= similarity_threshold_homogeneous:
        return 'HOMOGENEOUS'
    else:
        return 'DIFFERENT'


def _check_key_parameters_match(ai_result: Dict[str, Any], tolerance: float) -> bool:
    """
    Check if specific key parameters match within tolerance.
    
    Key parameters are things like dimensions, weight, material specifications
    that must match exactly or within small tolerance.
    """
    if not ai_result or 'key_parameters' not in ai_result:
        return False
    
    key_params = ai_result.get('key_parameters', {})
    
    # Example: Check if all key parameters match
    for param_name, param_value in key_params.items():
        if isinstance(param_value, dict) and 'target' in param_value and 'actual' in param_value:
            target_val = param_value['target']
            actual_val = param_value['actual']
            
            # Try to parse as numbers
            try:
                target_num = float(target_val)
                actual_num = float(actual_val)
                
                # Check if within tolerance
                if target_num == 0 and actual_num == 0:
                    continue
                elif target_num == 0 or actual_num == 0:
                    return False
                
                rel_diff = abs(target_num - actual_num) / max(abs(target_num), abs(actual_num))
                if rel_diff > tolerance:
                    return False
            except (ValueError, TypeError):
                # Not numeric, use string comparison
                if str(target_val).lower() != str(actual_val).lower():
                    return False
    
    return True


def _check_functional_match(ai_result: Dict[str, Any]) -> bool:
    """
    Check if functional parameters match.
    
    Functional parameters are things that serve the same purpose
    even if specifications differ (e.g., different brands of same component).
    """
    if not ai_result or 'functional_match' not in ai_result:
        return False
    
    return bool(ai_result.get('functional_match', False))


# Unit conversion helper (simplified)
_UNIT_CONVERSIONS = {
    'kg': {'g': 1000, 'mg': 1000000},
    'g': {'kg': 0.001, 'mg': 1000},
    'mg': {'kg': 0.000001, 'g': 0.001},
    'm': {'cm': 100, 'mm': 1000},
    'cm': {'m': 0.01, 'mm': 10},
    'mm': {'m': 0.001, 'cm': 0.1},
    'l': {'ml': 1000},
    'ml': {'l': 0.001},
}


def are_units_compatible(unit1: Optional[str], unit2: Optional[str]) -> bool:
    """
    Check if two units are compatible (can be converted).
    
    Args:
        unit1: First unit
        unit2: Second unit
        
    Returns:
        True if units are compatible, False otherwise
    """
    if not unit1 or not unit2:
        return False
    
    unit1_lower = unit1.lower()
    unit2_lower = unit2.lower()
    
    # Direct match
    if unit1_lower == unit2_lower:
        return True
    
    # Check if convertible
    if unit1_lower in _UNIT_CONVERSIONS and unit2_lower in _UNIT_CONVERSIONS[unit1_lower]:
        return True
    if unit2_lower in _UNIT_CONVERSIONS and unit1_lower in _UNIT_CONVERSIONS[unit2_lower]:
        return True
    
    # Check common aliases
    unit_aliases = {
        'kg': ['kilogram', 'kilograms', 'kilo'],
        'g': ['gram', 'grams'],
        'm': ['meter', 'meters', 'metre', 'metres'],
        'cm': ['centimeter', 'centimeters', 'centimetre', 'centimetres'],
        'mm': ['millimeter', 'millimeters', 'millimetre', 'millimetres'],
    }
    
    for base_unit, aliases in unit_aliases.items():
        if unit1_lower in aliases or unit1_lower == base_unit:
            if unit2_lower in aliases or unit2_lower == base_unit:
                return True
    
    return False