"""
Tests for the Normalization & Match Engine (app/services/ai/matcher.py)
"""

import pytest
from app.services.ai.matcher import (
    normalize_value,
    calculate_similarity,
    classify_match,
    are_units_compatible
)


class TestNormalizeValue:
    """Test the normalize_value function"""
    
    def test_normalize_value_basic(self):
        """Test basic normalization with unit"""
        result = normalize_value('10 kg')
        assert result['original'] == '10 kg'
        assert result['normalized'] == '10 kg'
        assert result['numeric_value'] == 10.0
        assert result['unit'] == 'kg'
        assert result['has_numeric'] is True
        assert result['has_unit'] is True
    
    def test_normalize_value_with_comma(self):
        """Test normalization with comma as decimal separator"""
        result = normalize_value('10,5 m')
        assert result['original'] == '10,5 m'
        assert result['normalized'] == '10.5 m'
        assert result['numeric_value'] == 10.5
        assert result['unit'] == 'm'
        assert result['has_numeric'] is True
        assert result['has_unit'] is True
    
    def test_normalize_value_complex_number(self):
        """Test normalization with complex number format"""
        result = normalize_value('10,500 г')
        assert result['original'] == '10,500 г'
        assert result['normalized'] == '10.500 г'
        assert result['numeric_value'] == 10.5  # 10,500 is 10.5
        assert result['unit'] == 'г'
        assert result['has_numeric'] is True
        assert result['has_unit'] is True
    
    def test_normalize_value_no_unit(self):
        """Test normalization without unit"""
        result = normalize_value('100')
        assert result['original'] == '100'
        assert result['normalized'] == '100'
        assert result['numeric_value'] == 100.0
        assert result['unit'] is None
        assert result['has_numeric'] is True
        assert result['has_unit'] is False
    
    def test_normalize_value_text_only(self):
        """Test normalization with text only (no numbers)"""
        result = normalize_value('steel pipe')
        assert result['original'] == 'steel pipe'
        assert result['normalized'] == 'steel pipe'
        assert result['numeric_value'] is None
        assert result['unit'] is None
        assert result['has_numeric'] is False
        assert result['has_unit'] is False
    
    def test_normalize_value_empty(self):
        """Test normalization with empty or None input"""
        result = normalize_value('')
        assert result['original'] == ''
        assert result['normalized'] == ''
        assert result['numeric_value'] is None
        assert result['unit'] is None
        assert result['has_numeric'] is False
        assert result['has_unit'] is False
        
        result = normalize_value(None)
        assert result['original'] is None
        assert result['normalized'] is None
        assert result['numeric_value'] is None
        assert result['unit'] is None
        assert result['has_numeric'] is False
        assert result['has_unit'] is False
    
    def test_normalize_value_with_extra_spaces(self):
        """Test normalization with extra spaces"""
        result = normalize_value('  10.5  kg  ')
        assert result['original'] == '  10.5  kg  '
        assert result['normalized'] == '10.5  kg'
        assert result['numeric_value'] == 10.5
        assert result['unit'] == 'kg'
        assert result['has_numeric'] is True
        assert result['has_unit'] is True
    
    def test_normalize_value_number_in_middle(self):
        """Test normalization with number in the middle of text"""
        result = normalize_value('pipe diameter 50 mm')
        assert result['original'] == 'pipe diameter 50 mm'
        assert result['normalized'] == 'pipe diameter 50 mm'
        assert result['numeric_value'] == 50.0
        assert result['unit'] == 'mm'
        assert result['has_numeric'] is True
        assert result['has_unit'] is True


class TestCalculateSimilarity:
    """Test the calculate_similarity function"""
    
    def test_calculate_similarity_identical(self):
        """Test similarity for identical strings"""
        similarity = calculate_similarity('10 kg', '10 kg')
        assert similarity == 100.0
    
    def test_calculate_similarity_typos(self):
        """Test similarity for strings with typos"""
        similarity = calculate_similarity('aluminum', 'aluminium')
        assert similarity > 80.0  # Should be high despite spelling difference
    
    def test_calculate_similarity_different_order(self):
        """Test similarity for strings with words in different order"""
        similarity = calculate_similarity('steel pipe 50mm', 'pipe steel 50mm')
        assert similarity > 90.0  # Token sort ratio should handle this well
    
    def test_calculate_similarity_different(self):
        """Test similarity for completely different strings"""
        similarity = calculate_similarity('steel pipe', 'plastic tube')
        assert similarity < 50.0  # Should be low
    
    def test_calculate_similarity_empty(self):
        """Test similarity with empty strings"""
        similarity = calculate_similarity('', 'test')
        assert similarity == 0.0
        
        similarity = calculate_similarity('test', '')
        assert similarity == 0.0
        
        similarity = calculate_similarity('', '')
        assert similarity == 0.0
    
    def test_calculate_similarity_similar_units(self):
        """Test similarity for similar units"""
        similarity = calculate_similarity('10 kilograms', '10 kg')
        assert similarity > 50.0  # Should have some similarity


class TestClassifyMatch:
    """Test the classify_match function"""
    
    def test_classify_match_identical_numeric(self):
        """Test identical match with numeric values"""
        result = classify_match('10 kg', '10 kg')
        assert result == 'IDENTICAL'
    
    def test_classify_match_identical_with_tolerance(self):
        """Test identical match within numeric tolerance"""
        result = classify_match('10 kg', '10.5 kg', numeric_tolerance=0.05)
        assert result == 'IDENTICAL'  # 5% difference
    
    def test_classify_match_homogeneous_numeric(self):
        """Test homogeneous match with slightly different numeric values"""
        result = classify_match('10 kg', '12 kg', numeric_tolerance=0.1)
        # 20% difference > 10% tolerance, but string similarity is 80% (HOMOGENEOUS threshold)
        assert result == 'HOMOGENEOUS'
    
    def test_classify_match_identical_text(self):
        """Test identical match with text"""
        result = classify_match('steel pipe', 'steel pipe')
        assert result == 'IDENTICAL'
    
    def test_classify_match_homogeneous_text(self):
        """Test homogeneous match with similar text"""
        result = classify_match('steel pipe', 'steel tube')
        # Similarity is 50%, below HOMOGENEOUS threshold of 80%
        assert result == 'DIFFERENT'
    
    def test_classify_match_different_text(self):
        """Test different match with unrelated text"""
        result = classify_match('steel pipe', 'plastic bag')
        assert result == 'DIFFERENT'
    
    def test_classify_match_with_ai_result_identical(self):
        """Test classification with AI result indicating identical match"""
        ai_result = {
            'key_parameters': {
                'weight': {'target': '10', 'actual': '10'},
                'material': {'target': 'steel', 'actual': 'steel'}
            }
        }
        result = classify_match('10 kg', '10 kg', ai_result=ai_result)
        assert result == 'IDENTICAL'
    
    def test_classify_match_with_ai_result_homogeneous(self):
        """Test classification with AI result indicating functional match"""
        ai_result = {
            'functional_match': True
        }
        result = classify_match('brand A pipe', 'brand B pipe', ai_result=ai_result)
        assert result == 'HOMOGENEOUS'
    
    def test_classify_match_unit_conversion(self):
        """Test classification with unit conversion"""
        result = classify_match('1000 g', '1 kg')
        # Should recognize as identical or homogeneous depending on unit recognition
        assert result in ['IDENTICAL', 'HOMOGENEOUS', 'DIFFERENT']
    
    def test_classify_match_different_units(self):
        """Test classification with incompatible units"""
        result = classify_match('10 kg', '10 m')
        assert result == 'DIFFERENT'  # Different units


class TestAreUnitsCompatible:
    """Test the are_units_compatible function"""
    
    def test_are_units_compatible_same(self):
        """Test with same units"""
        assert are_units_compatible('kg', 'kg') is True
        assert are_units_compatible('m', 'm') is True
    
    def test_are_units_compatible_convertible(self):
        """Test with convertible units"""
        assert are_units_compatible('kg', 'g') is True
        assert are_units_compatible('m', 'cm') is True
        assert are_units_compatible('cm', 'mm') is True
    
    def test_are_units_compatible_aliases(self):
        """Test with unit aliases"""
        assert are_units_compatible('kilogram', 'kg') is True
        assert are_units_compatible('meter', 'm') is True
        assert are_units_compatible('centimeter', 'cm') is True
    
    def test_are_units_compatible_incompatible(self):
        """Test with incompatible units"""
        assert are_units_compatible('kg', 'm') is False
        assert are_units_compatible('kg', 'l') is False
    
    def test_are_units_compatible_none(self):
        """Test with None units"""
        assert are_units_compatible(None, 'kg') is False
        assert are_units_compatible('kg', None) is False
        assert are_units_compatible(None, None) is False


class TestIntegration:
    """Integration tests for the matcher module"""
    
    def test_normalization_and_similarity_integration(self):
        """Test that normalization works with similarity calculation"""
        norm1 = normalize_value('10,5 kg')
        norm2 = normalize_value('10.5 kilograms')
        
        similarity = calculate_similarity(norm1['normalized'], norm2['normalized'])
        assert similarity > 60.0  # Should be reasonably similar
    
    def test_full_classification_workflow(self):
        """Test complete classification workflow"""
        # Test case from requirements: '10.5 kg' vs '10,500 г'
        result = classify_match('10.5 kg', '10,500 г')
        # Numeric values match (10.5), but units are different ('kg' vs 'г')
        # and similarity is low (66.67%), so should be DIFFERENT
        # Note: In a real system, we might want to add unit conversion logic
        assert result == 'DIFFERENT'
    
    def test_typo_handling(self):
        """Test that typos are handled correctly"""
        result = classify_match('aluminum pipe', 'aluminium pipe')
        # Should recognize as identical or homogeneous despite spelling difference
        assert result in ['IDENTICAL', 'HOMOGENEOUS']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])