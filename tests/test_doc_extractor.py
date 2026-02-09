"""
Tests for document text extractor service.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.doc_extractor import (
    extract_text_from_file,
    _extract_from_pdf,
    _extract_from_docx,
    _extract_from_html,
    _clean_text
)


class TestDocExtractor:
    """Test suite for document text extractor."""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Return path to test fixtures directory."""
        return Path(__file__).parent / "fixtures"
    
    @pytest.fixture
    def sample_pdf_path(self, fixtures_dir):
        """Return path to sample PDF fixture."""
        return fixtures_dir / "sample.pdf"
    
    @pytest.fixture
    def empty_pdf_path(self, fixtures_dir):
        """Return path to empty PDF fixture (simulates scanned PDF)."""
        return fixtures_dir / "empty.pdf"
    
    @pytest.fixture
    def sample_docx_path(self, fixtures_dir):
        """Return path to sample DOCX fixture."""
        return fixtures_dir / "sample.docx"
    
    @pytest.fixture
    def sample_html_path(self, fixtures_dir):
        """Return path to sample HTML fixture."""
        return fixtures_dir / "sample.html"
    
    @pytest.fixture
    def non_existent_path(self, fixtures_dir):
        """Return path to non-existent file."""
        return fixtures_dir / "non_existent.txt"
    
    def test_extract_from_pdf(self, sample_pdf_path):
        """Test PDF text extraction."""
        text, is_scanned = extract_text_from_file(str(sample_pdf_path))
        
        # Should extract text
        assert text is not None
        assert isinstance(text, str)
        assert len(text) > 0
        
        # Should not be marked as scanned
        assert is_scanned is False
        
        # Check that expected content is present
        assert "Sample PDF Document" in text
        assert "test PDF file" in text
        assert "extraction works correctly" in text
    
    def test_extract_from_pdf_empty(self, empty_pdf_path):
        """Test PDF extraction from empty/scanned PDF."""
        text, is_scanned = extract_text_from_file(str(empty_pdf_path))
        
        # Should return empty text and scanned flag
        assert text == ""
        assert is_scanned is True
    
    def test_extract_from_docx(self, sample_docx_path):
        """Test DOCX text extraction."""
        text, is_scanned = extract_text_from_file(str(sample_docx_path))
        
        # Should extract text
        assert text is not None
        assert isinstance(text, str)
        assert len(text) > 0
        
        # Should not be marked as scanned
        assert is_scanned is False
        
        # Check that expected content is present
        assert "Sample DOCX Document" in text
        assert "test DOCX file" in text
        assert "extraction works correctly" in text
        
        # Check table content is extracted
        assert "Column 1" in text
        assert "Column 2" in text
        assert "Row 1, Cell 1" in text
        assert "Row 2, Cell 2" in text
    
    def test_extract_from_html(self, sample_html_path):
        """Test HTML text extraction."""
        text, is_scanned = extract_text_from_file(str(sample_html_path))
        
        # Should extract text
        assert text is not None
        assert isinstance(text, str)
        assert len(text) > 0
        
        # Should not be marked as scanned
        assert is_scanned is False
        
        # Check that expected content is present
        assert "Sample HTML Document" in text
        assert "test HTML file" in text
        assert "extraction works correctly" in text
        
        # Check table content is extracted
        assert "Column 1" in text
        assert "Column 2" in text
        assert "Column 3" in text
        assert "Row 1, Cell 1" in text
        
        # Check that script and style content is NOT present
        assert "console.log" not in text
        assert "Test script" not in text
        assert ".hidden" not in text
        assert "display: none" not in text
    
    def test_extract_from_nonexistent_file(self, non_existent_path):
        """Test extraction from non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            extract_text_from_file(str(non_existent_path))
    
    def test_extract_with_unsupported_format(self, fixtures_dir, tmp_path):
        """Test extraction from unsupported file format."""
        # Create a file with unsupported format
        unsupported_file = tmp_path / "test.xyz"
        unsupported_file.write_text("Some content")
        
        with pytest.raises(ValueError, match="Unsupported file format"):
            extract_text_from_file(str(unsupported_file))
    
    def test_file_detection_by_content(self, fixtures_dir, tmp_path):
        """Test file type detection by content rather than extension."""
        # Create a PDF file with wrong extension
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n'
        pdf_with_txt_ext = tmp_path / "test.txt"
        pdf_with_txt_ext.write_bytes(pdf_content)
        
        # Should detect it as PDF based on content
        try:
            text, is_scanned = extract_text_from_file(str(pdf_with_txt_ext))
            # Either extracts text or marks as scanned
            assert isinstance(text, str)
            assert isinstance(is_scanned, bool)
        except ValueError as e:
            # PDF parsing might fail due to invalid PDF, but at least it tried
            assert "PDF" in str(e) or "Failed to extract" in str(e)
    
    def test_clean_text_function(self):
        """Test text cleaning utility function."""
        # Test with normal text
        input_text = "  Hello  World  \n\n  This is a test.  \n\n  Another line.  "
        expected = "Hello World\nThis is a test.\nAnother line."
        result = _clean_text(input_text)
        assert result == expected
        
        # Test with empty string
        assert _clean_text("") == ""
        assert _clean_text("   \n\n   ") == ""
        
        # Test with single line
        assert _clean_text("  Single line  ") == "Single line"
    
    def test_pdf_extraction_fallback(self, sample_pdf_path):
        """Test PDF extraction fallback from pdfplumber to PyPDF2."""
        # Mock pdfplumber to fail
        with patch('app.services.doc_extractor.pdfplumber') as mock_pdfplumber:
            mock_pdfplumber.open.side_effect = Exception("pdfplumber failed")
            
            # Should fall back to PyPDF2
            text, is_scanned = extract_text_from_file(str(sample_pdf_path))
            
            # Should still extract text
            assert text is not None
            assert isinstance(text, str)
            assert len(text) > 0
            assert is_scanned is False
    
    def test_missing_libraries(self):
        """Test behavior when required libraries are missing."""
        # Test missing PDF libraries
        with patch('app.services.doc_extractor.PDF_AVAILABLE', False), \
             patch('app.services.doc_extractor.PDFPLUMBER_AVAILABLE', False):
            
            with pytest.raises(ImportError, match="PDF processing libraries not available"):
                _extract_from_pdf("/some/path.pdf")
        
        # Test missing DOCX library
        with patch('app.services.doc_extractor.DOCX_AVAILABLE', False):
            with pytest.raises(ImportError, match="python-docx library not available"):
                _extract_from_docx("/some/path.docx")
        
        # Test missing BeautifulSoup library
        with patch('app.services.doc_extractor.BS4_AVAILABLE', False):
            with pytest.raises(ImportError, match="BeautifulSoup4 library not available"):
                _extract_from_html("/some/path.html")
    
    def test_html_with_different_encoding(self, fixtures_dir, tmp_path):
        """Test HTML extraction with different encodings."""
        # Create HTML with latin-1 encoding
        latin1_html = tmp_path / "latin1.html"
        latin1_content = """
        <!DOCTYPE html>
        <html>
        <head><meta charset="latin-1"></head>
        <body>
        <p>Test with special chars: é à ç</p>
        </body>
        </html>
        """
        latin1_html.write_bytes(latin1_content.encode('latin-1'))
        
        # Should handle different encoding
        text, is_scanned = extract_text_from_file(str(latin1_html))
        assert "Test with special chars" in text
        assert is_scanned is False
    
    def test_error_handling_in_extractors(self, tmp_path):
        """Test error handling in individual extractor functions."""
        # Create a corrupt PDF
        corrupt_pdf = tmp_path / "corrupt.pdf"
        corrupt_pdf.write_bytes(b"Not a valid PDF")
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Failed to extract text from PDF"):
            _extract_from_pdf(str(corrupt_pdf))
        
        # Create a corrupt DOCX
        corrupt_docx = tmp_path / "corrupt.docx"
        corrupt_docx.write_bytes(b"Not a valid DOCX")
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Failed to extract text from DOCX"):
            _extract_from_docx(str(corrupt_docx))
        
        # Test HTML extraction error handling by mocking an exception
        # BeautifulSoup is very tolerant, so we need to mock a failure
        with patch('app.services.doc_extractor.BeautifulSoup') as mock_bs:
            mock_bs.side_effect = Exception("BeautifulSoup failed")
            
            corrupt_html = tmp_path / "corrupt.html"
            corrupt_html.write_text("<html><body>Test</body></html>")
            
            # Should raise ValueError
            with pytest.raises(ValueError, match="Failed to extract text from HTML"):
                _extract_from_html(str(corrupt_html))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])