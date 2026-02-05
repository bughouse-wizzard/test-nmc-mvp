"""
Normalization and Heuristic Matching Engine.

This module implements:
1. Normalization: Lowercase, unit standardization (e.g., '100ml' -> {val: 100, unit: 'ml'})
2. Comparison Logic: Exact match for numbers (within tolerance), Levenshtein/Fuzzy match for strings
3. Manufacturer Check: Compare target manufacturer vs found manufacturer
4. Combine Heuristic results with AI results to populate the SpecComparisonRow model
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import math


class MatchStatus(str, Enum):
    """Match status enumeration."""
    MATCH = "MATCH"
    DIFF = "DIFF"
    UNKNOWN = "UNKNOWN"


class MatchType(str, Enum):
    """Match type enumeration."""
    IDENTICAL = "IDENTICAL"
    HOMOGENEOUS = "HOMOGENEOUS"
    NO_MATCH = "NO_MATCH"


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


class NormalizationEngine:
    """Handles normalization of text and unit values."""
    
    # Common unit patterns and their standard forms
    UNIT_PATTERNS = {
        r'\b(ml|milliliter|millilitre)s?\b': 'ml',
        r'\b(l|liter|litre)s?\b': 'l',
        r'\b(g|gram|grams)\b': 'g',
        r'\b(kg|kilogram|kilograms)\b': 'kg',
        r'\b(mg|milligram|milligrams)\b': 'mg',
        r'\b(mm|millimeter|millimetre)s?\b': 'mm',
        r'\b(cm|centimeter|centimetre)s?\b': 'cm',
        r'\b(m|meter|metre)s?\b': 'm',
        r'\b(km|kilometer|kilometre)s?\b': 'km',
        r'\b(%|percent|percentage)\b': '%',
        r'\b(°c|celsius)\b': '°C',
        r'\b(°f|fahrenheit)\b': '°F',
        r'\b(k|thousand)\b': 'k',
        r'\b(m|million)\b': 'M',
        r'\b(b|billion)\b': 'B',
    }
    
    # Synonyms for common parameters
    PARAMETER_SYNONYMS = {
        'плотность': ['граммаж', 'вес', 'масса на единицу площади'],
        'белизна': ['cie', 'яркость', 'светлота'],
        'прочность': ['прочность на разрыв', 'разрывная нагрузка'],
        'толщина': ['толщина листа', 'калибр'],
        'размер': ['габариты', 'размеры', 'формат'],
    }
    
    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Normalize text by:
        1. Converting to lowercase
        2. Trimming whitespace
        3. Replacing commas with dots for decimal numbers
        4. Standardizing common abbreviations
        """
        if not text:
            return ""
        
        # Convert to lowercase and trim
        normalized = text.lower().strip()
        
        # Replace commas with dots for decimal numbers
        normalized = re.sub(r'(\d),(\d)', r'\1.\2', normalized)
        
        # Standardize common abbreviations
        normalized = re.sub(r'\s+', ' ', normalized)  # Collapse multiple spaces
        
        return normalized
    
    @classmethod
    def extract_numeric_value(cls, text: str) -> Optional[Tuple[float, Optional[str]]]:
        """
        Extract numeric value and unit from text.
        Returns (value, unit) or None if no numeric value found.
        
        Examples:
        - "100ml" -> (100.0, "ml")
        - "80 г/м2" -> (80.0, "г/м2")
        - "160%" -> (160.0, "%")
        - "500 мл" -> (500.0, "мл")
        """
        if not text:
            return None
        
        # Pattern to match numbers with optional units
        # Matches: 100, 100.5, 100,5, 100ml, 100 ml, 80 г/м2, 160%, etc.
        pattern = r'([-+]?\d*[.,]?\d+)\s*([a-zA-Zа-яА-Я/%°²³µ]*\S*)?'
        
        match = re.search(pattern, text)
        if not match:
            return None
        
        value_str = match.group(1)
        unit = match.group(2) if match.group(2) else None
        
        # Clean value string (replace comma with dot)
        value_str = value_str.replace(',', '.')
        
        try:
            value = float(value_str)
            
            # Standardize unit if present
            if unit:
                unit = cls._standardize_unit(unit)
            
            return value, unit
        except ValueError:
            return None
    
    @classmethod
    def _standardize_unit(cls, unit: str) -> str:
        """Standardize unit to common form."""
        if not unit:
            return unit
        
        unit_lower = unit.lower().strip()
        
        # Apply unit patterns
        for pattern, standard in cls.UNIT_PATTERNS.items():
            if re.search(pattern, unit_lower):
                return standard
        
        return unit_lower
    
    @classmethod
    def normalize_value(cls, value: str) -> NormalizedValue:
        """
        Fully normalize a value, extracting numeric components if present.
        """
        normalized_text = cls.normalize_text(value)
        
        # Try to extract numeric value
        numeric_result = cls.extract_numeric_value(normalized_text)
        
        if numeric_result:
            numeric_value, unit = numeric_result
            return NormalizedValue(
                original=value,
                normalized=normalized_text,
                numeric_value=numeric_value,
                unit=unit,
                is_numeric=True
            )
        else:
            return NormalizedValue(
                original=value,
                normalized=normalized_text,
                is_numeric=False
            )


class ComparisonEngine:
    """Handles comparison logic for values."""
    
    # Default tolerance for numeric comparisons (percentage)
    DEFAULT_NUMERIC_TOLERANCE = 0.05  # 5%
    
    # Default similarity threshold for fuzzy string matching
    DEFAULT_SIMILARITY_THRESHOLD = 0.8  # 80%
    
    @classmethod
    def levenshtein_distance(cls, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        """
        if len(s1) < len(s2):
            return cls.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @classmethod
    def string_similarity(cls, s1: str, s2: str) -> float:
        """
        Calculate similarity between two strings (0.0 to 1.0).
        Uses Levenshtein distance normalized by string length.
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        
        distance = cls.levenshtein_distance(s1, s2)
        return 1.0 - (distance / max_len)
    
    @classmethod
    def compare_numeric_values(
        cls, 
        target_value: float, 
        actual_value: float, 
        tolerance: float = None,
        target_unit: str = None,
        actual_unit: str = None
    ) -> ComparisonResult:
        """
        Compare two numeric values with optional tolerance and unit checking.
        """
        if tolerance is None:
            tolerance = cls.DEFAULT_NUMERIC_TOLERANCE
        
        # Check units first
        unit_match = True
        unit_details = {}
        
        if target_unit and actual_unit:
            unit_similarity = cls.string_similarity(target_unit, actual_unit)
            unit_match = unit_similarity >= cls.DEFAULT_SIMILARITY_THRESHOLD
            unit_details = {
                "target_unit": target_unit,
                "actual_unit": actual_unit,
                "unit_similarity": unit_similarity,
                "unit_match": unit_match
            }
        
        # Calculate relative difference
        if target_value == 0 and actual_value == 0:
            relative_diff = 0.0
        elif target_value == 0:
            relative_diff = abs(actual_value)  # Handle division by zero
        else:
            relative_diff = abs(actual_value - target_value) / abs(target_value)
        
        # Determine match status
        if relative_diff <= tolerance and unit_match:
            match_status = MatchStatus.MATCH
            confidence = 1.0 - (relative_diff / tolerance)
        else:
            match_status = MatchStatus.DIFF
            confidence = max(0.0, 1.0 - relative_diff)
        
        details = {
            "relative_difference": relative_diff,
            "tolerance": tolerance,
            "target_value": target_value,
            "actual_value": actual_value,
            **unit_details
        }
        
        return ComparisonResult(
            target_value=str(target_value) + (f" {target_unit}" if target_unit else ""),
            actual_value=str(actual_value) + (f" {actual_unit}" if actual_unit else ""),
            match_status=match_status,
            confidence=confidence,
            details=details
        )
    
    @classmethod
    def compare_string_values(
        cls, 
        target_value: str, 
        actual_value: str,
        similarity_threshold: float = None
    ) -> ComparisonResult:
        """
        Compare two string values using fuzzy matching.
        """
        if similarity_threshold is None:
            similarity_threshold = cls.DEFAULT_SIMILARITY_THRESHOLD
        
        similarity = cls.string_similarity(target_value, actual_value)
        
        if similarity >= similarity_threshold:
            match_status = MatchStatus.MATCH
        else:
            match_status = MatchStatus.DIFF
        
        details = {
            "similarity": similarity,
            "similarity_threshold": similarity_threshold
        }
        
        return ComparisonResult(
            target_value=target_value,
            actual_value=actual_value,
            match_status=match_status,
            confidence=similarity,
            details=details
        )
    
    @classmethod
    def compare_values(
        cls, 
        target_value: str, 
        actual_value: str,
        numeric_tolerance: float = None,
        string_similarity_threshold: float = None
    ) -> ComparisonResult:
        """
        Compare two values, automatically detecting type and applying appropriate comparison.
        """
        # Normalize both values
        normalizer = NormalizationEngine()
        target_norm = normalizer.normalize_value(target_value)
        actual_norm = normalizer.normalize_value(actual_value)
        
        # If both have numeric values, compare numerically
        if target_norm.is_numeric and actual_norm.is_numeric:
            return cls.compare_numeric_values(
                target_value=target_norm.numeric_value,
                actual_value=actual_norm.numeric_value,
                tolerance=numeric_tolerance,
                target_unit=target_norm.unit,
                actual_unit=actual_norm.unit
            )
        
        # Otherwise, compare as strings
        return cls.compare_string_values(
            target_value=target_norm.normalized,
            actual_value=actual_norm.normalized,
            similarity_threshold=string_similarity_threshold
        )


class ManufacturerComparator:
    """Handles manufacturer comparison logic."""
    
    @classmethod
    def compare_manufacturers(
        cls, 
        target_manufacturer: Optional[str], 
        found_manufacturer: Optional[str]
    ) -> Dict[str, Any]:
        """
        Compare target manufacturer with found manufacturer.
        
        Returns dictionary with:
        - match: boolean indicating if manufacturers match
        - confidence: similarity score (0.0 to 1.0)
        - details: additional comparison details
        """
        if not target_manufacturer or not found_manufacturer:
            return {
                "match": None,
                "confidence": 0.0,
                "details": {
                    "target_manufacturer": target_manufacturer,
                    "found_manufacturer": found_manufacturer,
                    "reason": "Missing manufacturer information"
                }
            }
        
        # Normalize manufacturer names
        normalizer = NormalizationEngine()
        target_norm = normalizer.normalize_text(target_manufacturer)
        found_norm = normalizer.normalize_text(found_manufacturer)
        
        # Calculate similarity
        comparator = ComparisonEngine()
        similarity = comparator.string_similarity(target_norm, found_norm)
        
        # Determine match (using higher threshold for manufacturers)
        match = similarity >= 0.9  # 90% similarity for manufacturers
        
        return {
            "match": match,
            "confidence": similarity,
            "details": {
                "target_manufacturer": target_manufacturer,
                "found_manufacturer": found_manufacturer,
                "target_normalized": target_norm,
                "found_normalized": found_norm,
                "similarity": similarity,
                "match_threshold": 0.9
            }
        }


class MatchingEngine:
    """
    Main engine that combines heuristic matching with AI results
    to populate SpecComparisonRow models.
    """
    
    def __init__(
        self,
        numeric_tolerance: float = None,
        string_similarity_threshold: float = None
    ):
        self.numeric_tolerance = numeric_tolerance or ComparisonEngine.DEFAULT_NUMERIC_TOLERANCE
        self.string_similarity_threshold = string_similarity_threshold or ComparisonEngine.DEFAULT_SIMILARITY_THRESHOLD
        
        self.normalizer = NormalizationEngine()
        self.comparator = ComparisonEngine()
        self.manufacturer_comparator = ManufacturerComparator()
    
    def create_spec_comparison_rows(
        self,
        target_specs: Dict[str, str],
        contract_specs: Dict[str, str],
        ai_results: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Create specification comparison rows by combining heuristic matching with AI results.
        
        Args:
            target_specs: Dictionary of target specifications {name: value}
            contract_specs: Dictionary of contract specifications {name: value}
            ai_results: Optional AI analysis results
            
        Returns:
            List of dictionaries ready for SpecComparisonRow creation
        """
        comparison_rows = []
        
        # Get all unique specification names
        all_spec_names = set(target_specs.keys()) | set(contract_specs.keys())
        
        for spec_name in all_spec_names:
            target_value = target_specs.get(spec_name, "")
            actual_value = contract_specs.get(spec_name, "")
            
            # Apply heuristic matching
            comparison_result = self.comparator.compare_values(
                target_value=target_value,
                actual_value=actual_value,
                numeric_tolerance=self.numeric_tolerance,
                string_similarity_threshold=self.string_similarity_threshold
            )
            
            # Combine with AI results if available
            weight = 1  # Default weight
            if ai_results and spec_name in ai_results:
                ai_confidence = ai_results.get(spec_name, {}).get("confidence", 0.5)
                # Adjust confidence based on AI input
                comparison_result.confidence = (comparison_result.confidence + ai_confidence) / 2
            
            # Determine match status
            match_status = comparison_result.match_status
            
            # Create row dictionary
            row = {
                "name": spec_name,
                "target_value": target_value,
                "actual_value": actual_value,
                "match_status": match_status.value,
                "weight": weight,
                "confidence": comparison_result.confidence,
                "details": comparison_result.details
            }
            
            comparison_rows.append(row)
        
        return comparison_rows
    
    def determine_match_type(
        self,
        comparison_rows: List[Dict[str, Any]],
        manufacturer_match: Optional[bool] = None
    ) -> MatchType:
        """
        Determine overall match type based on comparison rows and manufacturer check.
        
        Rules:
        - IDENTICAL: All critical specifications match
        - HOMOGENEOUS: >= 70% of specifications match and no critical conflicts
        - NO_MATCH: Otherwise
        """
        if not comparison_rows:
            return MatchType.NO_MATCH
        
        # Calculate match statistics
        total_rows = len(comparison_rows)
        matched_rows = sum(1 for row in comparison_rows if row["match_status"] == MatchStatus.MATCH.value)
        match_percentage = matched_rows / total_rows if total_rows > 0 else 0.0
        
        # Check for critical specifications (could be extended with config)
        critical_specs = ["наименование", "код ктру", "производитель"]
        critical_matched = all(
            any(row["name"].lower() == crit_spec and row["match_status"] == MatchStatus.MATCH.value 
                for row in comparison_rows)
            for crit_spec in critical_specs
        )
        
        # Apply manufacturer check
        if manufacturer_match is False:
            # Manufacturer mismatch downgrades match type
            if critical_matched and match_percentage >= 0.9:
                return MatchType.HOMOGENEOUS
            elif match_percentage >= 0.7:
                return MatchType.HOMOGENEOUS
            else:
                return MatchType.NO_MATCH
        
        # Determine match type based on rules
        if critical_matched and match_percentage >= 0.95:
            return MatchType.IDENTICAL
        elif match_percentage >= 0.7:
            return MatchType.HOMOGENEOUS
        else:
            return MatchType.NO_MATCH
    
    def process_contract_comparison(
        self,
        target_specs: Dict[str, str],
        contract_specs: Dict[str, str],
        target_manufacturer: Optional[str] = None,
        found_manufacturer: Optional[str] = None,
        ai_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete contract comparison processing.
        
        Returns:
            Dictionary with comparison results including:
            - comparison_rows: List of specification comparison rows
            - match_type: Overall match type (IDENTICAL/HOMOGENEOUS/NO_MATCH)
            - manufacturer_comparison: Results of manufacturer comparison
            - summary: Match statistics
        """
        # Create specification comparison rows
        comparison_rows = self.create_spec_comparison_rows(
            target_specs=target_specs,
            contract_specs=contract_specs,
            ai_results=ai_results
        )
        
        # Compare manufacturers
        manufacturer_comparison = self.manufacturer_comparator.compare_manufacturers(
            target_manufacturer=target_manufacturer,
            found_manufacturer=found_manufacturer
        )
        
        # Determine overall match type
        match_type = self.determine_match_type(
            comparison_rows=comparison_rows,
            manufacturer_match=manufacturer_comparison["match"]
        )
        
        # Calculate summary statistics
        total_rows = len(comparison_rows)
        matched_rows = sum(1 for row in comparison_rows if row["match_status"] == MatchStatus.MATCH.value)
        avg_confidence = sum(row["confidence"] for row in comparison_rows) / total_rows if total_rows > 0 else 0.0
        
        return {
            "comparison_rows": comparison_rows,
            "match_type": match_type.value,
            "manufacturer_comparison": manufacturer_comparison,
            "summary": {
                "total_specifications": total_rows,
                "matched_specifications": matched_rows,
                "match_percentage": matched_rows / total_rows if total_rows > 0 else 0.0,
                "average_confidence": avg_confidence,
                "manufacturer_match": manufacturer_comparison["match"]
            }
        }