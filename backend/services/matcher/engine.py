"""
Normalization & Heuristic Matching Engine.

This module implements:
1. Normalization: Lowercase, unit standardization (e.g., '100ml' -> {val: 100, unit: 'ml'})
2. Comparison Logic: Exact match for numbers (within tolerance), Levenshtein/Fuzzy match for strings
3. Manufacturer Check: Compare target manufacturer vs found manufacturer
4. Combine Heuristic results with AI results to populate the SpecComparisonRow model
"""

import re
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import Levenshtein


class MatchStatus(str, Enum):
    """Match status enumeration."""
    MATCH = "MATCH"
    DIFF = "DIFF"
    UNKNOWN = "UNKNOWN"


@dataclass
class NormalizedValue:
    """Represents a normalized value with optional unit."""
    value: Optional[Union[float, str]]
    unit: Optional[str] = None
    original: Optional[str] = None
    
    def __str__(self) -> str:
        if self.value is None:
            return self.original or ""
        if self.unit:
            return f"{self.value}{self.unit}"
        return str(self.value)


class NormalizationEngine:
    """Handles normalization of values for comparison."""
    
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
        r'\b(pc|piece|pieces|шт|штук|штуки)\b': 'pc',
        r'\b(pack|packs|упаковок?|уп)\b': 'pack',
        r'\b(box|boxes|коробок?|кор)\b': 'box',
    }
    
    # Number extraction pattern
    NUMBER_PATTERN = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'
    
    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Normalize text by converting to lowercase and removing extra whitespace.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text
        """
        if not text or not isinstance(text, str):
            return ""
        return text.lower().strip()
    
    @classmethod
    def extract_number_and_unit(cls, text: str) -> NormalizedValue:
        """
        Extract number and unit from text like '100ml' -> {val: 100, unit: 'ml'}.
        
        Args:
            text: Input text containing number and optional unit
            
        Returns:
            NormalizedValue object
        """
        if not text or not isinstance(text, str):
            return NormalizedValue(value=None, original=text)
        
        text_lower = text.lower().strip()
        
        # Try to find a number in the text
        numbers = re.findall(cls.NUMBER_PATTERN, text_lower)
        if not numbers:
            # No number found, return as string
            return NormalizedValue(value=text_lower, original=text)
        
        # Use the first number found
        number_str = numbers[0]
        try:
            number = float(number_str)
        except ValueError:
            number = text_lower
        
        # Find unit by looking for unit patterns
        unit = None
        remaining_text = text_lower.replace(number_str, '', 1).strip()
        
        for pattern, standard_unit in cls.UNIT_PATTERNS.items():
            if re.search(pattern, remaining_text, re.IGNORECASE):
                unit = standard_unit
                break
        
        # If no unit pattern found but there's text after the number, use it as unit
        if not unit and remaining_text:
            unit = remaining_text
        
        return NormalizedValue(value=number, unit=unit, original=text)
    
    @classmethod
    def normalize_manufacturer(cls, manufacturer: str) -> str:
        """
        Normalize manufacturer name for comparison.
        
        Args:
            manufacturer: Manufacturer name
            
        Returns:
            Normalized manufacturer name
        """
        if not manufacturer:
            return ""
        
        normalized = cls.normalize_text(manufacturer)
        
        # First remove punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Remove common suffixes and legal forms (at beginning or end)
        patterns = [
            # English suffixes at end
            r'\s+(llc|inc|corp|corporation|company|co|gmbh|ag|oy|ab|s\.?a\.?|ltd|limited)\s*$',
            # Russian suffixes at end
            r'\s+(ооо|зао|оао|ао|пао|ип)\s*$',
            # English suffixes at beginning
            r'^\s*(llc|inc|corp|corporation|company|co|gmbh|ag|oy|ab|s\.?a\.?|ltd|limited)\s+',
            # Russian suffixes at beginning
            r'^\s*(ооо|зао|оао|ао|пао|ип)\s+',
        ]
        
        for pattern in patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized


class ComparisonEngine:
    """Handles comparison logic for normalized values."""
    
    # Default tolerance for numeric comparisons (percentage)
    DEFAULT_NUMERIC_TOLERANCE = 0.05  # 5%
    
    # Default similarity threshold for string matching
    DEFAULT_SIMILARITY_THRESHOLD = 0.8  # 80%
    
    @classmethod
    def compare_numbers(
        cls, 
        target: Union[float, int, str], 
        actual: Union[float, int, str],
        tolerance: float = DEFAULT_NUMERIC_TOLERANCE
    ) -> Tuple[MatchStatus, float]:
        """
        Compare numbers with tolerance.
        
        Args:
            target: Target number
            actual: Actual number to compare
            tolerance: Tolerance as percentage (0.05 = 5%)
            
        Returns:
            Tuple of (MatchStatus, similarity_score)
        """
        try:
            target_num = float(target) if not isinstance(target, (int, float)) else float(target)
            actual_num = float(actual) if not isinstance(actual, (int, float)) else float(actual)
        except (ValueError, TypeError):
            return MatchStatus.UNKNOWN, 0.0
        
        if target_num == 0 and actual_num == 0:
            return MatchStatus.MATCH, 1.0
        
        if target_num == 0 or actual_num == 0:
            return MatchStatus.DIFF, 0.0
        
        ratio = min(target_num, actual_num) / max(target_num, actual_num)
        similarity = ratio
        
        if ratio >= (1 - tolerance):
            return MatchStatus.MATCH, similarity
        else:
            return MatchStatus.DIFF, similarity
    
    @classmethod
    def compare_strings(
        cls,
        target: str,
        actual: str,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> Tuple[MatchStatus, float]:
        """
        Compare strings using Levenshtein distance.
        
        Args:
            target: Target string
            actual: Actual string to compare
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            Tuple of (MatchStatus, similarity_score)
        """
        if not target and not actual:
            return MatchStatus.MATCH, 1.0
        
        if not target or not actual:
            return MatchStatus.UNKNOWN, 0.0
        
        # Normalize strings
        target_norm = NormalizationEngine.normalize_text(target)
        actual_norm = NormalizationEngine.normalize_text(actual)
        
        # Exact match after normalization
        if target_norm == actual_norm:
            return MatchStatus.MATCH, 1.0
        
        # Calculate Levenshtein similarity
        distance = Levenshtein.distance(target_norm, actual_norm)
        max_len = max(len(target_norm), len(actual_norm))
        
        if max_len == 0:
            similarity = 1.0
        else:
            similarity = 1.0 - (distance / max_len)
        
        if similarity >= threshold:
            return MatchStatus.MATCH, similarity
        else:
            return MatchStatus.DIFF, similarity
    
    @classmethod
    def compare_normalized_values(
        cls,
        target: NormalizedValue,
        actual: NormalizedValue,
        numeric_tolerance: float = DEFAULT_NUMERIC_TOLERANCE,
        string_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> Tuple[MatchStatus, float]:
        """
        Compare normalized values (handles both numbers and strings).
        
        Args:
            target: Target NormalizedValue
            actual: Actual NormalizedValue to compare
            numeric_tolerance: Tolerance for numeric comparison
            string_threshold: Threshold for string comparison
            
        Returns:
            Tuple of (MatchStatus, similarity_score)
        """
        # If both have units, they must match
        if target.unit and actual.unit and target.unit != actual.unit:
            return MatchStatus.DIFF, 0.0
        
        # If one has unit and other doesn't, it's likely different
        if (target.unit and not actual.unit) or (not target.unit and actual.unit):
            return MatchStatus.UNKNOWN, 0.0
        
        # Compare values
        if isinstance(target.value, (int, float)) and isinstance(actual.value, (int, float)):
            return cls.compare_numbers(target.value, actual.value, numeric_tolerance)
        else:
            # Convert to strings for comparison
            target_str = str(target.value) if target.value is not None else ""
            actual_str = str(actual.value) if actual.value is not None else ""
            return cls.compare_strings(target_str, actual_str, string_threshold)
    
    @classmethod
    def compare_manufacturers(
        cls,
        target_manufacturer: str,
        found_manufacturer: str,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> Tuple[bool, float]:
        """
        Compare manufacturer names.
        
        Args:
            target_manufacturer: Target manufacturer name
            found_manufacturer: Found manufacturer name
            threshold: Similarity threshold
            
        Returns:
            Tuple of (match_bool, similarity_score)
        """
        if not target_manufacturer or not found_manufacturer:
            return False, 0.0
        
        # Normalize manufacturer names
        target_norm = NormalizationEngine.normalize_manufacturer(target_manufacturer)
        found_norm = NormalizationEngine.normalize_manufacturer(found_manufacturer)
        
        # Compare using string similarity
        status, similarity = cls.compare_strings(target_norm, found_norm, threshold)
        
        return status == MatchStatus.MATCH, similarity


class MatcherEngine:
    """
    Main matcher engine that combines heuristic and AI results.
    """
    
    def __init__(
        self,
        numeric_tolerance: float = 0.05,
        string_threshold: float = 0.8,
        manufacturer_threshold: float = 0.7
    ):
        """
        Initialize the matcher engine.
        
        Args:
            numeric_tolerance: Tolerance for numeric comparisons
            string_threshold: Threshold for string similarity
            manufacturer_threshold: Threshold for manufacturer similarity
        """
        self.numeric_tolerance = numeric_tolerance
        self.string_threshold = string_threshold
        self.manufacturer_threshold = manufacturer_threshold
        
        self.normalization_engine = NormalizationEngine()
        self.comparison_engine = ComparisonEngine()
    
    def create_spec_comparison_row(
        self,
        name: str,
        target_value: str,
        actual_value: str,
        weight: int = 1
    ) -> Dict[str, Any]:
        """
        Create a specification comparison row with match status.
        
        Args:
            name: Name of the characteristic
            target_value: Target value from requirements
            actual_value: Actual value from contract
            weight: Importance weight
            
        Returns:
            Dictionary representing SpecComparisonRow
        """
        # Normalize values
        target_norm = self.normalization_engine.extract_number_and_unit(target_value)
        actual_norm = self.normalization_engine.extract_number_and_unit(actual_value)
        
        # Compare values
        match_status, similarity = self.comparison_engine.compare_normalized_values(
            target_norm, actual_norm,
            numeric_tolerance=self.numeric_tolerance,
            string_threshold=self.string_threshold
        )
        
        return {
            "name": name,
            "target_value": target_value,
            "actual_value": actual_value,
            "match_status": match_status.value,
            "weight": weight,
            "similarity_score": similarity,
            "normalized_target": str(target_norm),
            "normalized_actual": str(actual_norm)
        }
    
    def compare_manufacturers(
        self,
        target_manufacturer: str,
        found_manufacturer: str
    ) -> Dict[str, Any]:
        """
        Compare manufacturer names.
        
        Args:
            target_manufacturer: Target manufacturer name
            found_manufacturer: Found manufacturer name
            
        Returns:
            Dictionary with comparison results
        """
        match, similarity = self.comparison_engine.compare_manufacturers(
            target_manufacturer, found_manufacturer, self.manufacturer_threshold
        )
        
        return {
            "target_manufacturer": target_manufacturer,
            "found_manufacturer": found_manufacturer,
            "match": match,
            "similarity_score": similarity,
            "normalized_target": self.normalization_engine.normalize_manufacturer(target_manufacturer),
            "normalized_found": self.normalization_engine.normalize_manufacturer(found_manufacturer)
        }
    
    def combine_with_ai_results(
        self,
        heuristic_results: Dict[str, Any],
        ai_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Combine heuristic matching results with AI results.
        
        Args:
            heuristic_results: Results from heuristic matching
            ai_results: Results from AI analysis
            
        Returns:
            Combined results ready for SpecComparisonRow population
        """
        combined = {
            "spec_comparison_rows": [],
            "manufacturer_comparison": None,
            "overall_match_score": 0.0,
            "heuristic_weight": 0.4,  # Weight for heuristic results
            "ai_weight": 0.6,  # Weight for AI results
        }
        
        # Add heuristic comparison rows
        if "comparison_rows" in heuristic_results:
            combined["spec_comparison_rows"].extend(heuristic_results["comparison_rows"])
        
        # Add manufacturer comparison
        if "manufacturer_comparison" in heuristic_results:
            combined["manufacturer_comparison"] = heuristic_results["manufacturer_comparison"]
        
        # Calculate overall match score
        heuristic_score = heuristic_results.get("overall_similarity", 0.0)
        ai_score = ai_results.get("confidence_score", 0.0) / 100.0  # Convert 0-100 to 0.0-1.0
        
        combined["overall_match_score"] = (
            heuristic_score * combined["heuristic_weight"] +
            ai_score * combined["ai_weight"]
        )
        
        return combined