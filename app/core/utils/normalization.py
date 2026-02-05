"""
Data normalization utilities for cleaning and standardizing user input and scraped data.

This module provides functions to:
1. Clean strings (trim, lower, remove extra spaces)
2. Normalize numbers (comma to dot conversion, extract numeric values)
3. Standardize units (convert common units to standard forms)
4. Apply comprehensive normalization to both user input and scraped data
"""

import re
from typing import Optional, Union, Dict, Any, Tuple
from decimal import Decimal, InvalidOperation


# Common unit mappings for standardization
UNIT_MAPPINGS = {
    # Weight units
    'кг': 'kg',
    'килограмм': 'kg',
    'килограммов': 'kg',
    'г': 'g',
    'грамм': 'g',
    'граммов': 'g',
    'т': 't',
    'тонн': 't',
    'тонна': 't',
    'тонны': 't',
    'mg': 'mg',
    'milligram': 'mg',
    'milligrams': 'mg',
    
    # Length units
    'м': 'm',
    'метр': 'm',
    'метра': 'm',
    'метров': 'm',
    'см': 'cm',
    'сантиметр': 'cm',
    'сантиметра': 'cm',
    'сантиметров': 'cm',
    'мм': 'mm',
    'миллиметр': 'mm',
    'миллиметра': 'mm',
    'миллиметров': 'mm',
    'km': 'km',
    'kilometer': 'km',
    'kilometers': 'km',
    
    # Volume units
    'л': 'l',
    'литр': 'l',
    'литров': 'l',
    'мл': 'ml',
    'миллилитр': 'ml',
    'миллилитров': 'ml',
    'm³': 'm3',
    'куб.м': 'm3',
    'кубометр': 'm3',
    'кубометров': 'm3',
    
    # Area units
    'м²': 'm2',
    'кв.м': 'm2',
    'квадратный метр': 'm2',
    'квадратных метров': 'm2',
    'га': 'ha',
    'гектар': 'ha',
    'гектаров': 'ha',
    
    # Currency units
    'руб': 'RUB',
    'рубль': 'RUB',
    'рублей': 'RUB',
    'р.': 'RUB',
    '₽': 'RUB',
    'usd': 'USD',
    'доллар': 'USD',
    'долларов': 'USD',
    '$': 'USD',
    'eur': 'EUR',
    'евро': 'EUR',
    '€': 'EUR',
    
    # Time units
    'ч': 'h',
    'час': 'h',
    'часов': 'h',
    'мин': 'min',
    'минута': 'min',
    'минут': 'min',
    'сек': 's',
    'секунда': 's',
    'секунд': 's',
    
    # Power units
    'вт': 'W',
    'ватт': 'W',
    'ваттов': 'W',
    'квт': 'kW',
    'киловатт': 'kW',
    'киловаттов': 'kW',
    
    # Other common units
    'шт': 'pcs',
    'штук': 'pcs',
    'штука': 'pcs',
    'ед': 'unit',
    'единица': 'unit',
    'единиц': 'unit',
    'пач': 'pack',
    'пачка': 'pack',
    'пачек': 'pack',
    'уп': 'pack',
    'упаковка': 'pack',
    'упаковок': 'pack',
}

# Unit conversion factors for standardization to base units
UNIT_CONVERSION = {
    'g': 0.001,  # grams to kg
    'mg': 0.000001,  # milligrams to kg
    't': 1000,  # tons to kg
    'cm': 0.01,  # cm to m
    'mm': 0.001,  # mm to m
    'km': 1000,  # km to m
    'ml': 0.001,  # ml to l
    'm3': 1000,  # m3 to l
    'm2': 1,  # base area unit
    'ha': 10000,  # ha to m2
    'min': 1/60,  # minutes to hours
    's': 1/3600,  # seconds to hours
    'kW': 1000,  # kW to W
}


def clean_string(value: str) -> str:
    """
    Clean and normalize a string.
    
    Args:
        value: Input string to clean
        
    Returns:
        Cleaned string with trimmed whitespace, normalized spaces, and lowercase
    """
    if not value or not isinstance(value, str):
        return value if value is not None else ""
    
    # Trim whitespace
    cleaned = value.strip()
    
    # Replace multiple spaces with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Convert to lowercase for consistency
    cleaned = cleaned.lower()
    
    return cleaned


def normalize_number(value: Union[str, int, float, Decimal]) -> Optional[float]:
    """
    Normalize a number from various string formats.
    
    Handles:
    - Comma as decimal separator (European format)
    - Thousand separators (spaces, dots, commas)
    - Non-numeric characters mixed with numbers
    
    Args:
        value: Input value to normalize
        
    Returns:
        Normalized float value or None if cannot parse
    """
    if value is None:
        return None
    
    # If already a number, return as float
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    
    if not isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    # Clean the string
    cleaned = clean_string(value)
    
    # Extract the numeric part more carefully
    # Look for number patterns in the string
    # This regex matches:
    # - Optional sign
    # - Digits with optional thousand separators (spaces, dots, commas)
    # - Optional decimal part (comma or dot followed by digits)
    # First try pattern with thousand separators
    number_pattern = r'[-+]?(?:\d{1,3}(?:[ \.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)'
    match = re.search(number_pattern, cleaned)
    
    if not match:
        return None
    
    number_str = match.group(0)
    
    # Now normalize the extracted number string
    # Remove spaces (thousand separators)
    number_str = number_str.replace(' ', '')
    
    # Handle European format where comma is decimal separator
    if ',' in number_str and '.' in number_str:
        # If comma comes after dot, comma is decimal (e.g., "1.234,56")
        if number_str.rfind(',') > number_str.rfind('.'):
            # Remove dots (thousand separators) and replace comma with dot
            number_str = number_str.replace('.', '').replace(',', '.')
        else:
            # Dot is decimal, comma is thousand separator
            number_str = number_str.replace(',', '')
    elif ',' in number_str:
        # Only comma exists - check if it's decimal or thousand separator
        parts = number_str.split(',')
        if len(parts) == 2 and len(parts[1]) <= 3:
            # Likely decimal separator (e.g., "1234,56")
            number_str = number_str.replace(',', '.')
        else:
            # Likely thousand separator (e.g., "1,234")
            number_str = number_str.replace(',', '')
    elif '.' in number_str:
        # Only dot exists - check if it's decimal or thousand separator
        parts = number_str.split('.')
        if len(parts) > 2:
            # Multiple dots, likely thousand separators (e.g., "1.234.567")
            number_str = number_str.replace('.', '')
        elif len(parts) == 2 and len(parts[1]) > 3:
            # Single dot with more than 3 decimal places, likely thousand separator
            number_str = number_str.replace('.', '')
        # Otherwise, dot is likely decimal separator
    
    # Try to convert to float
    try:
        return float(number_str)
    except (ValueError, TypeError):
        return None


def extract_number_and_unit(value: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extract number and unit from a string.
    
    Args:
        value: Input string containing number and unit (e.g., "10 кг", "5.5 m")
        
    Returns:
        Tuple of (number, unit) or (None, None) if cannot parse
    """
    if not value or not isinstance(value, str):
        return None, None
    
    cleaned = clean_string(value)
    
    # Try to find number at the beginning (most common case)
    # Match patterns like: "123", "1 234", "1,234.56", "1 234,56"
    # The regex looks for digits with optional separators
    match = re.match(r'^([-+]?(?:\d{1,3}(?:[ \.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?))\s*(.*)$', cleaned)
    if match:
        number_str, unit_str = match.groups()
        number = normalize_number(number_str)
        unit = standardize_unit(unit_str) if unit_str else None
        return number, unit
    
    # Try to find number anywhere in the string
    # Use the same pattern as normalize_number
    number_pattern = r'[-+]?(?:\d{1,3}(?:[ \.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)'
    match = re.search(number_pattern, cleaned)
    
    if match:
        number_str = match.group(0)
        number = normalize_number(number_str)
        # Extract unit by removing the number from the string
        unit_str = cleaned.replace(number_str, '', 1).strip()
        unit = standardize_unit(unit_str) if unit_str else None
        return number, unit
    
    return None, None


def standardize_unit(unit: str) -> Optional[str]:
    """
    Standardize a unit string using the unit mappings.
    
    Args:
        unit: Input unit string
        
    Returns:
        Standardized unit or None if not recognized
    """
    if not unit or not isinstance(unit, str):
        return None
    
    cleaned = clean_string(unit)
    
    # Check for exact match first (most specific)
    if cleaned in UNIT_MAPPINGS:
        return UNIT_MAPPINGS[cleaned]
    
    # Check for common variations
    
    # Remove trailing dots
    cleaned_no_dots = cleaned.rstrip('.')
    if cleaned_no_dots in UNIT_MAPPINGS:
        return UNIT_MAPPINGS[cleaned_no_dots]
    
    # Handle Russian plural forms
    # Common endings: -ов, -ев, -ей, -а, -я, -и
    if cleaned.endswith('ов'):
        base_form = cleaned[:-2]
        if base_form in UNIT_MAPPINGS:
            return UNIT_MAPPINGS[base_form]
    elif cleaned.endswith('ев'):
        base_form = cleaned[:-2]
        if base_form in UNIT_MAPPINGS:
            return UNIT_MAPPINGS[base_form]
    elif cleaned.endswith('ей'):
        base_form = cleaned[:-2]
        if base_form in UNIT_MAPPINGS:
            return UNIT_MAPPINGS[base_form]
    elif cleaned.endswith('а'):
        base_form = cleaned[:-1]
        if base_form in UNIT_MAPPINGS:
            return UNIT_MAPPINGS[base_form]
    elif cleaned.endswith('я'):
        base_form = cleaned[:-1]
        if base_form in UNIT_MAPPINGS:
            return UNIT_MAPPINGS[base_form]
    elif cleaned.endswith('и'):
        base_form = cleaned[:-1]
        if base_form in UNIT_MAPPINGS:
            return UNIT_MAPPINGS[base_form]
    
    # Check for English plural forms
    if cleaned.endswith('s'):
        singular_form = cleaned[:-1]
        if singular_form in UNIT_MAPPINGS:
            return UNIT_MAPPINGS[singular_form]
    
    # Try to match by checking if any unit mapping key is in the cleaned string
    # But be more strict - only match if the mapping key is a significant part of the string
    for key, value in UNIT_MAPPINGS.items():
        # Check if the key is a standalone word in the unit string
        # This prevents "метра" matching "т" (ton) because "т" is in "метра"
        if key == cleaned:
            return value
        # Check if key is a word boundary match
        if re.search(r'\b' + re.escape(key) + r'\b', cleaned):
            return value
    
    return None


def normalize_value_with_unit(value: str) -> Dict[str, Any]:
    """
    Normalize a value that may contain both number and unit.
    
    Args:
        value: Input string (e.g., "10 кг", "5,5 м", "100.50 руб")
        
    Returns:
        Dictionary with keys: original, normalized_value, unit, base_value, base_unit
    """
    result = {
        'original': value,
        'normalized_value': None,
        'unit': None,
        'base_value': None,
        'base_unit': None,
        'is_normalized': False
    }
    
    if not value or not isinstance(value, str):
        return result
    
    # Extract number and unit
    number, unit = extract_number_and_unit(value)
    
    if number is not None:
        result['normalized_value'] = number
        result['unit'] = unit
        result['is_normalized'] = True
        
        # Convert to base unit if possible
        if unit:
            if unit in UNIT_CONVERSION:
                result['base_value'] = number * UNIT_CONVERSION[unit]
                # Determine base unit
                if unit in ['g', 'mg', 't']:
                    result['base_unit'] = 'kg'
                elif unit in ['cm', 'mm', 'km']:
                    result['base_unit'] = 'm'
                elif unit in ['ml', 'm3']:
                    result['base_unit'] = 'l'
                elif unit in ['ha']:
                    result['base_unit'] = 'm2'
                elif unit in ['min', 's']:
                    result['base_unit'] = 'h'
                elif unit in ['kW']:
                    result['base_unit'] = 'W'
                else:
                    result['base_unit'] = unit
            else:
                # Unit is already a base unit or not in conversion table
                result['base_value'] = number
                result['base_unit'] = unit
    
    return result


def normalize_specification_value(value: str) -> str:
    """
    Normalize a specification value for comparison.
    
    This is a convenience function that returns a standardized string
    representation of a value with unit.
    
    Args:
        value: Input specification value
        
    Returns:
        Normalized string representation
    """
    normalized = normalize_value_with_unit(value)
    
    if normalized['is_normalized']:
        # Format number without unnecessary decimal places
        number = normalized['normalized_value']
        # Check if number is essentially an integer (within small tolerance)
        if abs(number - round(number)) < 0.0001:
            formatted_number = str(int(round(number)))
        else:
            # Keep up to 3 decimal places
            formatted_number = f"{number:.3f}".rstrip('0').rstrip('.')
        
        if normalized['unit']:
            return f"{formatted_number} {normalized['unit']}"
        else:
            return formatted_number
    else:
        # Return cleaned string if cannot normalize as number
        return clean_string(value)


def normalize_user_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize user input data for search requests.
    
    Args:
        data: Dictionary of user input data
        
    Returns:
        Normalized dictionary
    """
    normalized = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            # Clean string fields
            normalized[key] = clean_string(value)
            
            # Special handling for specific fields
            if key in ['object_name', 'customer_region', 'manufacturer_target', 'manufacturer_found']:
                # These are pure string fields, just clean them
                pass
            elif key in ['ktru_code', 'okpd2_code']:
                # These might have specific formats, clean but preserve case for codes
                normalized[key] = value.strip()
            elif 'value' in key.lower() or 'price' in key.lower():
                # Try to normalize as number
                num_value = normalize_number(value)
                if num_value is not None:
                    normalized[key] = num_value
        elif isinstance(value, (int, float, Decimal)):
            normalized[key] = float(value)
        else:
            normalized[key] = value
    
    return normalized


def normalize_scraped_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize scraped data from procurement portals.
    
    Args:
        data: Dictionary of scraped data
        
    Returns:
        Normalized dictionary
    """
    normalized = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            # Clean all string fields
            cleaned = clean_string(value)
            
            # Special handling for different field types
            if any(price_key in key.lower() for price_key in ['price', 'cost', 'value', 'сумма', 'цена', 'стоимость']):
                # Price fields - extract number
                num_value = normalize_number(cleaned)
                if num_value is not None:
                    normalized[key] = num_value
                else:
                    normalized[key] = cleaned
            elif any(unit_key in key.lower() for unit_key in ['unit', 'единица', 'измерен']):
                # Unit fields - standardize
                normalized[key] = standardize_unit(cleaned) or cleaned
            elif any(qty_key in key.lower() for qty_key in ['quantity', 'количество', 'кол-во']):
                # Quantity fields - extract number
                num_value = normalize_number(cleaned)
                if num_value is not None:
                    normalized[key] = num_value
                else:
                    normalized[key] = cleaned
            else:
                # General string fields
                normalized[key] = cleaned
        elif isinstance(value, (int, float, Decimal)):
            normalized[key] = float(value)
        else:
            normalized[key] = value
    
    return normalized


def compare_normalized_values(value1: str, value2: str, tolerance: float = 0.01) -> bool:
    """
    Compare two values after normalization.
    
    Args:
        value1: First value to compare
        value2: Second value to compare
        tolerance: Relative tolerance for numeric comparison
        
    Returns:
        True if values are considered equal after normalization
    """
    # Normalize both values
    norm1 = normalize_value_with_unit(value1)
    norm2 = normalize_value_with_unit(value2)
    
    # If either couldn't be normalized as number, compare as strings
    if not norm1['is_normalized'] or not norm2['is_normalized']:
        return clean_string(value1) == clean_string(value2)
    
    # Get comparable values in the same unit
    val1_to_compare = norm1['base_value'] if norm1['base_value'] is not None else norm1['normalized_value']
    val2_to_compare = norm2['base_value'] if norm2['base_value'] is not None else norm2['normalized_value']
    
    # Get the units for comparison
    unit1 = norm1['base_unit'] if norm1['base_unit'] is not None else norm1['unit']
    unit2 = norm2['base_unit'] if norm2['base_unit'] is not None else norm2['unit']
    
    # If units are the same (or both None), compare values
    if unit1 == unit2:
        return abs(val1_to_compare - val2_to_compare) <= tolerance * max(abs(val1_to_compare), abs(val2_to_compare), 1)
    else:
        # Cannot compare numerically, compare as strings
        return clean_string(value1) == clean_string(value2)