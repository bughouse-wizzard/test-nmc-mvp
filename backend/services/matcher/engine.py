"""
Normalization & Heuristic Matching Engine for NMCK Calculation System.

This module implements:
1. Normalization: Lowercase, unit standardization (e.g., '100ml' -> {val: 100, unit: 'ml'})
2. Comparison Logic: Exact match for numbers (within tolerance), Levenshtein/Fuzzy match for strings
3. Manufacturer Check: Compare target manufacturer vs found manufacturer
4. Combine Heuristic results with AI results to populate the SpecComparisonRow model
"""

import re
import math
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz, process


class MatchStatus(str, Enum):
    """Match status for specification comparison."""
    MATCH = "MATCH"
    DIFF = "DIFF"
    UNKNOWN = "UNKNOWN"


@dataclass
class NormalizedValue:
    """Represents a normalized value with extracted numeric and unit components."""
    original: str
    normalized: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    is_numeric: bool = False


@dataclass
class ComparisonResult:
    """Result of comparing two values."""
    target_value: str
    actual_value: str
    match_status: MatchStatus
    confidence: float  # 0.0 to 1.0
    details: Dict[str, Any]


class MatcherEngine:
    """Engine for normalization and heuristic matching of specification values."""
    
    # Common unit mappings for standardization (including Cyrillic)
    UNIT_MAPPINGS = {
        # Volume units
        'ml': 'ml', 'milliliter': 'ml', 'milliliters': 'ml', 'мл': 'ml', 'миллилитр': 'ml', 'миллилитров': 'ml',
        'l': 'l', 'liter': 'l', 'liters': 'l', 'litre': 'l', 'litres': 'l', 'л': 'l', 'литр': 'l', 'литров': 'l',
        'm3': 'm3', 'cubic meter': 'm3', 'cubic meters': 'm3', 'м3': 'm3', 'куб.м': 'm3', 'кубический метр': 'm3',
        
        # Weight units
        'g': 'g', 'gram': 'g', 'grams': 'g', 'г': 'g', 'грамм': 'g',
        'kg': 'kg', 'kilogram': 'kg', 'kilograms': 'kg', 'кг': 'kg', 'килограмм': 'kg', 'килограммов': 'kg',
        't': 't', 'ton': 't', 'tons': 't', 'tonne': 't', 'tonnes': 't', 'т': 't', 'тонна': 't', 'тонн': 't',
        
        # Length units
        'mm': 'mm', 'millimeter': 'mm', 'millimeters': 'mm', 'мм': 'mm', 'миллиметр': 'mm', 'миллиметров': 'mm',
        'cm': 'cm', 'centimeter': 'cm', 'centimeters': 'cm', 'см': 'cm', 'сантиметр': 'cm', 'сантиметров': 'cm',
        'm': 'm', 'meter': 'm', 'meters': 'm', 'metre': 'm', 'metres': 'm', 'м': 'm', 'метр': 'm', 'метров': 'm',
        'km': 'km', 'kilometer': 'km', 'kilometers': 'km', 'км': 'km', 'километр': 'km', 'километров': 'km',
        
        # Area units
        'm2': 'm2', 'square meter': 'm2', 'square meters': 'm2', 'м2': 'm2', 'кв.м': 'm2', 'квадратный метр': 'm2',
        'sqm': 'm2', 'sq.m': 'm2',
        
        # Count units
        'pcs': 'pcs', 'pc': 'pcs', 'piece': 'pcs', 'pieces': 'pcs', 'шт': 'pcs', 'штук': 'pcs', 'штука': 'pcs',
        'unit': 'unit', 'units': 'unit', 'ед': 'unit', 'единица': 'unit', 'единиц': 'unit',
        'set': 'set', 'sets': 'set', 'компл': 'set', 'комплект': 'set', 'комплектов': 'set',
        
        # Time units
        'h': 'h', 'hour': 'h', 'hours': 'h', 'ч': 'h', 'час': 'h', 'часов': 'h',
        'day': 'day', 'days': 'day', 'д': 'day', 'день': 'day', 'дней': 'day',
        'week': 'week', 'weeks': 'week', 'нед': 'week', 'неделя': 'week', 'недель': 'week',
        'month': 'month', 'months': 'month', 'мес': 'month', 'месяц': 'month', 'месяцев': 'month',
        'year': 'year', 'years': 'year', 'год': 'year', 'лет': 'year', 'года': 'year',
    }
    
    # Numeric tolerance for comparison (percentage)
    NUMERIC_TOLERANCE = 0.01  # 1%
    
    # String similarity threshold for fuzzy matching
    STRING_SIMILARITY_THRESHOLD = 0.8  # 80%
    
    # Manufacturer similarity threshold
    MANUFACTURER_SIMILARITY_THRESHOLD = 0.7  # 70%
    
    def __init__(self, numeric_tolerance: float = None, string_threshold: float = None):
        """
        Initialize the matcher engine.
        
        Args:
            numeric_tolerance: Tolerance for numeric comparisons (default: 0.01 = 1%)
            string_threshold: Threshold for string similarity (default: 0.8 = 80%)
        """
        if numeric_tolerance is not None:
            self.NUMERIC_TOLERANCE = numeric_tolerance
        if string_threshold is not None:
            self.STRING_SIMILARITY_THRESHOLD = string_threshold
    
    def normalize_value(self, value: str) -> NormalizedValue:
        """
        Normalize a value by:
        1. Converting to lowercase
        2. Extracting numeric value and unit if present
        3. Standardizing units
        
        Args:
            value: The input value string
            
        Returns:
            NormalizedValue object with extracted components
        """
        if not value or not isinstance(value, str):
            return NormalizedValue(
                original=str(value) if value else "",
                normalized="",
                is_numeric=False
            )
        
        # Convert to lowercase and strip whitespace
        normalized = value.lower().strip()
        original = value
        
        # Try to extract numeric value and unit
        numeric_value = None
        unit = None
        is_numeric = False
        
        # Pattern for values like "100ml", "5.5 kg", "10-20 m", ">50 g" (including Cyrillic)
        numeric_patterns = [
            # Pattern for values like "100ml", "5.5kg", "100мл", "5.5кг"
            r'^([\d\.,]+)\s*([a-zA-Zа-яА-ЯёЁ°²³μ]+[\d]*)$',
            # Pattern for values like "100 ml", "5.5 kg", "100 мл", "5.5 кг"
            r'^([\d\.,]+)\s+([a-zA-Zа-яА-ЯёЁ°²³μ]+[\d]*)$',
            # Pattern for ranges like "10-20 m", "5.5-7.5 kg", "10-20 м", "5.5-7.5 кг"
            r'^([\d\.,]+)\s*[-–]\s*([\d\.,]+)\s*([a-zA-Zа-яА-ЯёЁ°²³μ]+[\d]*)$',
            # Pattern for comparisons like ">50 g", "<100 ml", ">50 г", "<100 мл"
            r'^([<>≤≥])\s*([\d\.,]+)\s*([a-zA-Zа-яА-ЯёЁ°²³μ]+[\d]*)$',
        ]
        
        for pattern in numeric_patterns:
            match = re.match(pattern, normalized)
            if match:
                if len(match.groups()) == 2:
                    # Simple case: "100ml" or "100 ml"
                    num_str = match.group(1)
                    unit_str = match.group(2)
                    
                    # Clean numeric string
                    num_str_clean = num_str.replace(',', '.')
                    try:
                        numeric_value = float(num_str_clean)
                        is_numeric = True
                        
                        # Standardize unit
                        unit = self._standardize_unit(unit_str)
                    except ValueError:
                        pass
                elif len(match.groups()) == 3:
                    # Range or comparison case
                    if '[-–]' in pattern:
                        # Range: take the average
                        num1_str = match.group(1).replace(',', '.')
                        num2_str = match.group(2).replace(',', '.')
                        unit_str = match.group(3)
                        
                        try:
                            num1 = float(num1_str)
                            num2 = float(num2_str)
                            numeric_value = (num1 + num2) / 2
                            is_numeric = True
                            unit = self._standardize_unit(unit_str)
                        except ValueError:
                            pass
                    else:
                        # Comparison: use the value
                        num_str = match.group(2).replace(',', '.')
                        unit_str = match.group(3)
                        
                        try:
                            numeric_value = float(num_str)
                            is_numeric = True
                            unit = self._standardize_unit(unit_str)
                        except ValueError:
                            pass
                break
        
        # If no unit pattern matched, check if it's just a number
        if not is_numeric:
            # Try to extract just a number
            num_match = re.search(r'([\d\.,]+)', normalized)
            if num_match:
                num_str = num_match.group(1).replace(',', '.')
                try:
                    numeric_value = float(num_str)
                    is_numeric = True
                except ValueError:
                    pass
        
        return NormalizedValue(
            original=original,
            normalized=normalized,
            numeric_value=numeric_value,
            unit=unit,
            is_numeric=is_numeric
        )
    
    def _standardize_unit(self, unit: str) -> str:
        """
        Standardize a unit string using the UNIT_MAPPINGS.
        
        Args:
            unit: The unit string to standardize
            
        Returns:
            Standardized unit string
        """
        # Remove any non-alphanumeric characters except °²³μ and Cyrillic
        cleaned = re.sub(r'[^a-zA-Zа-яА-ЯёЁ°²³μ\d]', '', unit.lower())
        
        # Check exact match first (highest priority)
        if cleaned in self.UNIT_MAPPINGS:
            return self.UNIT_MAPPINGS[cleaned]
        
        # Sort keys by length (longest first) to avoid partial matches
        # when longer matches are available
        sorted_keys = sorted(self.UNIT_MAPPINGS.keys(), key=len, reverse=True)
        
        # Check for full word matches
        for key in sorted_keys:
            # Check if key is a full word in the cleaned unit
            if re.search(r'\b' + re.escape(key) + r'\b', cleaned):
                return self.UNIT_MAPPINGS[key]
        
        # Check for partial matches as fallback (but prefer longer matches)
        for key in sorted_keys:
            if key in cleaned:
                return self.UNIT_MAPPINGS[key]
        
        # Return original if no mapping found
        return cleaned
    
    def compare_values(self, target: str, actual: str) -> ComparisonResult:
        """
        Compare two values using heuristic matching.
        
        Args:
            target: Target value from requirements
            actual: Actual value from contract
            
        Returns:
            ComparisonResult with match status and confidence
        """
        # Normalize both values
        norm_target = self.normalize_value(target)
        norm_actual = self.normalize_value(actual)
        
        # Initialize result
        result = ComparisonResult(
            target_value=target,
            actual_value=actual,
            match_status=MatchStatus.UNKNOWN,
            confidence=0.0,
            details={
                'target_normalized': norm_target.normalized,
                'actual_normalized': norm_actual.normalized,
                'target_numeric': norm_target.numeric_value,
                'actual_numeric': norm_actual.numeric_value,
                'target_unit': norm_target.unit,
                'actual_unit': norm_actual.unit,
                'target_is_numeric': norm_target.is_numeric,
                'actual_is_numeric': norm_actual.is_numeric,
            }
        )
        
        # Case 1: Both are numeric values
        if norm_target.is_numeric and norm_actual.is_numeric:
            confidence = self._compare_numeric(
                norm_target.numeric_value, 
                norm_actual.numeric_value,
                norm_target.unit,
                norm_actual.unit
            )
            result.confidence = confidence
            result.match_status = MatchStatus.MATCH if confidence >= 0.8 else MatchStatus.DIFF
        
        # Case 2: At least one is not numeric, use string comparison
        else:
            confidence = self._compare_strings(
                norm_target.normalized,
                norm_actual.normalized
            )
            result.confidence = confidence
            result.match_status = MatchStatus.MATCH if confidence >= self.STRING_SIMILARITY_THRESHOLD else MatchStatus.DIFF
        
        # Update details with comparison method
        result.details['comparison_method'] = 'numeric' if norm_target.is_numeric and norm_actual.is_numeric else 'string'
        result.details['confidence'] = confidence
        
        return result
    
    def _compare_numeric(self, target_val: float, actual_val: float, 
                        target_unit: Optional[str], actual_unit: Optional[str]) -> float:
        """
        Compare two numeric values with unit consideration.
        
        Args:
            target_val: Target numeric value
            actual_val: Actual numeric value
            target_unit: Target unit (optional)
            actual_unit: Actual unit (optional)
            
        Returns:
            Confidence score from 0.0 to 1.0
        """
        # Check unit compatibility
        unit_match = self._compare_units(target_unit, actual_unit)
        if not unit_match:
            return 0.0
        
        # Calculate relative difference
        if target_val == 0 and actual_val == 0:
            return 1.0
        elif target_val == 0 or actual_val == 0:
            return 0.0
        
        relative_diff = abs(target_val - actual_val) / max(abs(target_val), abs(actual_val))
        
        # Convert to confidence (1.0 when identical, 0.0 when difference > tolerance)
        if relative_diff <= self.NUMERIC_TOLERANCE:
            confidence = 1.0 - (relative_diff / self.NUMERIC_TOLERANCE)
        else:
            confidence = max(0.0, 1.0 - (relative_diff - self.NUMERIC_TOLERANCE))
        
        return confidence
    
    def _compare_units(self, unit1: Optional[str], unit2: Optional[str]) -> bool:
        """
        Compare two units for compatibility.
        
        Args:
            unit1: First unit
            unit2: Second unit
            
        Returns:
            True if units are compatible, False otherwise
        """
        if unit1 is None and unit2 is None:
            return True
        if unit1 is None or unit2 is None:
            return False
        
        # Check if units are the same
        if unit1 == unit2:
            return True
        
        # Check for unit conversions (simplified)
        unit_conversions = {
            # Volume conversions
            ('ml', 'l'): 1000,
            ('l', 'ml'): 0.001,
            ('l', 'm3'): 0.001,
            ('m3', 'l'): 1000,
            
            # Weight conversions
            ('g', 'kg'): 1000,
            ('kg', 'g'): 0.001,
            ('kg', 't'): 1000,
            ('t', 'kg'): 0.001,
            
            # Length conversions
            ('mm', 'cm'): 10,
            ('cm', 'mm'): 0.1,
            ('cm', 'm'): 100,
            ('m', 'cm'): 0.01,
            ('m', 'km'): 1000,
            ('km', 'm'): 0.001,
        }
        
        # Check if we have a conversion factor
        if (unit1, unit2) in unit_conversions or (unit2, unit1) in unit_conversions:
            return True
        
        return False
    
    def _compare_strings(self, str1: str, str2: str) -> float:
        """
        Compare two strings using fuzzy matching.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score from 0.0 to 1.0
        """
        if not str1 and not str2:
            return 1.0
        if not str1 or not str2:
            return 0.0
        
        # Use rapidfuzz for fuzzy string matching
        # Try different comparison methods and take the best score
        methods = [
            fuzz.ratio,
            fuzz.partial_ratio,
            fuzz.token_sort_ratio,
            fuzz.token_set_ratio
        ]
        
        best_score = 0.0
        for method in methods:
            score = method(str1, str2) / 100.0  # Convert from 0-100 to 0.0-1.0
            best_score = max(best_score, score)
        
        return best_score
    
    def compare_manufacturers(self, target_manufacturer: str, found_manufacturer: str) -> Dict[str, Any]:
        """
        Compare manufacturer names.
        
        Args:
            target_manufacturer: Target manufacturer from requirements
            found_manufacturer: Manufacturer found in contract
            
        Returns:
            Dictionary with match result and details
        """
        if not target_manufacturer or not found_manufacturer:
            return {
                'match': False,
                'confidence': 0.0,
                'target': target_manufacturer,
                'found': found_manufacturer,
                'details': 'Missing manufacturer information'
            }
        
        # Normalize manufacturer names
        norm_target = self.normalize_value(target_manufacturer).normalized
        norm_found = self.normalize_value(found_manufacturer).normalized
        
        # Calculate similarity
        similarity = self._compare_strings(norm_target, norm_found)
        
        # Determine match
        match = similarity >= self.MANUFACTURER_SIMILARITY_THRESHOLD
        
        return {
            'match': match,
            'confidence': similarity,
            'target': target_manufacturer,
            'found': found_manufacturer,
            'target_normalized': norm_target,
            'found_normalized': norm_found,
            'similarity': similarity,
            'threshold': self.MANUFACTURER_SIMILARITY_THRESHOLD
        }
    
    def create_spec_comparison_rows(self, 
                                   target_specs: Dict[str, str],
                                   actual_specs: Dict[str, str],
                                   ai_scores: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """
        Create specification comparison rows by combining heuristic and AI results.
        
        Args:
            target_specs: Dictionary of target specifications {name: value}
            actual_specs: Dictionary of actual specifications {name: value}
            ai_scores: Optional dictionary of AI confidence scores {name: score}
            
        Returns:
            List of dictionaries ready for SpecComparisonRow population
        """
        comparison_rows = []
        
        # Get all unique specification names
        all_spec_names = set(target_specs.keys()) | set(actual_specs.keys())
        
        for spec_name in all_spec_names:
            target_value = target_specs.get(spec_name, "")
            actual_value = actual_specs.get(spec_name, "")
            
            # Get heuristic comparison result
            heuristic_result = self.compare_values(target_value, actual_value)
            
            # Get AI score if available
            ai_score = ai_scores.get(spec_name, 0.0) if ai_scores else 0.0
            
            # Combine heuristic and AI results
            # Weight: 70% heuristic, 30% AI (adjustable)
            heuristic_weight = 0.7
            ai_weight = 0.3
            
            combined_confidence = (heuristic_result.confidence * heuristic_weight) + (ai_score * ai_weight)
            
            # Determine final match status
            if combined_confidence >= 0.7:  # Combined threshold
                final_status = MatchStatus.MATCH
            elif combined_confidence >= 0.3:  # Partial match threshold
                final_status = MatchStatus.UNKNOWN
            else:
                final_status = MatchStatus.DIFF
            
            # Create row data
            row_data = {
                'name': spec_name,
                'target_value': target_value,
                'actual_value': actual_value,
                'match_status': final_status,
                'weight': 1,  # Default weight, can be customized
                'confidence': combined_confidence,
                'heuristic_confidence': heuristic_result.confidence,
                'ai_score': ai_score,
                'details': {
                    'heuristic_details': heuristic_result.details,
                    'comparison_method': heuristic_result.details.get('comparison_method', 'unknown')
                }
            }
            
            comparison_rows.append(row_data)
        
        return comparison_rows
    
    def match_specifications(self,
                            target_specs: Dict[str, str],
                            actual_specs: Dict[str, str],
                            target_manufacturer: Optional[str] = None,
                            found_manufacturer: Optional[str] = None,
                            ai_scores: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Complete specification matching including manufacturer comparison.
        
        Args:
            target_specs: Dictionary of target specifications
            actual_specs: Dictionary of actual specifications
            target_manufacturer: Target manufacturer name
            found_manufacturer: Found manufacturer name
            ai_scores: Optional AI confidence scores
            
        Returns:
            Complete matching results including spec comparisons and manufacturer match
        """
        # Create specification comparison rows
        spec_rows = self.create_spec_comparison_rows(target_specs, actual_specs, ai_scores)
        
        # Calculate overall match score
        if spec_rows:
            total_confidence = sum(row['confidence'] for row in spec_rows)
            avg_confidence = total_confidence / len(spec_rows)
            
            # Count matches
            match_count = sum(1 for row in spec_rows if row['match_status'] == MatchStatus.MATCH)
            diff_count = sum(1 for row in spec_rows if row['match_status'] == MatchStatus.DIFF)
            unknown_count = sum(1 for row in spec_rows if row['match_status'] == MatchStatus.UNKNOWN)
        else:
            avg_confidence = 0.0
            match_count = diff_count = unknown_count = 0
        
        # Compare manufacturers if provided
        manufacturer_result = None
        if target_manufacturer and found_manufacturer:
            manufacturer_result = self.compare_manufacturers(target_manufacturer, found_manufacturer)
        
        return {
            'spec_comparisons': spec_rows,
            'manufacturer_comparison': manufacturer_result,
            'summary': {
                'total_specs': len(spec_rows),
                'match_count': match_count,
                'diff_count': diff_count,
                'unknown_count': unknown_count,
                'avg_confidence': avg_confidence,
                'manufacturer_match': manufacturer_result['match'] if manufacturer_result else None,
                'manufacturer_confidence': manufacturer_result['confidence'] if manufacturer_result else None
            }
        }