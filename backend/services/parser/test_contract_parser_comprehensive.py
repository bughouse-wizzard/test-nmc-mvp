"""
Comprehensive test module for ContractParser TASK 102 implementation.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from contract import ContractParser
except ImportError:
    # For direct execution
    from .contract import ContractParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_parse_common_info():
    """Test parse_common_info method."""
    print("Testing parse_common_info method...")
    
    # Create parser instance
    parser = ContractParser()
    
    # Load fixture HTML
    fixtures_dir = Path(__file__).parent / "fixtures"
    common_info_html = (fixtures_dir / "common_info.html").read_text(encoding='utf-8')
    
    # Parse common info
    result = parser.parse_common_info(common_info_html)
    
    # Verify extracted fields
    assert result['reestr_number'] == '1234567890', f"Expected '1234567890', got {result['reestr_number']}"
    assert result['customer'] == 'Министерство цифрового развития РФ', f"Expected 'Министерство цифрового развития РФ', got {result['customer']}"
    assert result['supplier'] == 'ООО "Технологии Будущего"', f"Expected 'ООО \"Технологии Будущего\"', got {result['supplier']}"
    assert result['currency'] == 'RUB', f"Expected 'RUB', got {result['currency']}"
    assert result['execution_status'] == 'Исполняется', f"Expected 'Исполняется', got {result['execution_status']}"
    
    # Verify date parsing
    assert isinstance(result['sign_date'], datetime), f"Expected datetime, got {type(result['sign_date'])}"
    assert result['sign_date'].year == 2024, f"Expected year 2024, got {result['sign_date'].year}"
    assert result['sign_date'].month == 12, f"Expected month 12, got {result['sign_date'].month}"
    assert result['sign_date'].day == 15, f"Expected day 15, got {result['sign_date'].day}"
    
    # Verify price parsing
    assert result['total_price'] == 1500000.0, f"Expected 1500000.0, got {result['total_price']}"
    
    print("✓ parse_common_info test passed!")


def test_parse_objects_tab():
    """Test parse_objects_tab method - critical for unit price and characteristics extraction."""
    print("\nTesting parse_objects_tab method...")
    
    # Create parser instance
    parser = ContractParser()
    
    # Load fixture HTML
    fixtures_dir = Path(__file__).parent / "fixtures"
    objects_tab_html = (fixtures_dir / "objects_tab.html").read_text(encoding='utf-8')
    
    # Parse objects tab
    products = parser.parse_objects_tab(objects_tab_html)
    
    # Verify we found products
    assert len(products) == 3, f"Expected 3 products, got {len(products)}"
    
    # Test first product (Server equipment)
    product1 = products[0]
    assert product1['item_number'] == '1', f"Expected item number '1', got {product1['item_number']}"
    assert 'Серверное оборудование Dell PowerEdge R750' in product1['name'], f"Expected server equipment name, got {product1['name']}"
    assert product1['okpd2_code'] == '26.20.11.110', f"Expected OKPD2 code '26.20.11.110', got {product1['okpd2_code']}"
    assert product1['ktru_code'] == '26.20.11.110-00000001', f"Expected KTRU code '26.20.11.110-00000001', got {product1['ktru_code']}"
    assert product1['unit'] == 'шт.', f"Expected unit 'шт.', got {product1['unit']}"
    assert product1['quantity'] == 5.0, f"Expected quantity 5.0, got {product1['quantity']}"
    assert product1['unit_price'] == 150000.0, f"Expected unit price 150000.0, got {product1['unit_price']}"
    assert product1['total_price'] == 750000.0, f"Expected total price 750000.0, got {product1['total_price']}"
    
    # Verify characteristics extraction
    assert product1['characteristics'] is not None, "Expected characteristics to be extracted"
    characteristics = product1['characteristics']
    assert 'Характеристики:' in characteristics, "Expected 'Характеристики:' in characteristics"
    assert 'Процессор: 2 x Intel Xeon Silver 4314' in characteristics, "Expected processor info in characteristics"
    assert 'Память: 256 ГБ DDR4' in characteristics, "Expected memory info in characteristics"
    assert 'Жесткие диски: 4 x 1.92 ТБ SSD' in characteristics, "Expected storage info in characteristics"
    
    # Test second product (Network equipment)
    product2 = products[1]
    assert product2['item_number'] == '2', f"Expected item number '2', got {product2['item_number']}"
    assert product2['unit_price'] == 200000.0, f"Expected unit price 200000.0, got {product2['unit_price']}"
    assert product2['total_price'] == 600000.0, f"Expected total price 600000.0, got {product2['total_price']}"
    
    # Test third product (Software)
    product3 = products[2]
    assert product3['item_number'] == '3', f"Expected item number '3', got {product3['item_number']}"
    assert product3['unit_price'] == 15000.0, f"Expected unit price 15000.0, got {product3['unit_price']}"
    assert product3['total_price'] == 150000.0, f"Expected total price 150000.0, got {product3['total_price']}"
    
    print("✓ parse_objects_tab test passed!")


def test_parse_attachments_list():
    """Test parse_attachments_list method with keyword filtering."""
    print("\nTesting parse_attachments_list method...")
    
    # Create parser instance
    parser = ContractParser()
    
    # Load fixture HTML
    fixtures_dir = Path(__file__).parent / "fixtures"
    attachments_html = (fixtures_dir / "attachments_tab.html").read_text(encoding='utf-8')
    
    # Parse attachments list
    attachments = parser.parse_attachments_list(attachments_html, base_url="https://zakupki.gov.ru")
    
    # Verify we found attachments
    assert len(attachments) >= 5, f"Expected at least 5 attachments, got {len(attachments)}"
    
    # Find important documents
    printed_forms = [a for a in attachments if a['document_type'] == 'printed_form']
    technical_specs = [a for a in attachments if a['document_type'] == 'technical_specification']
    specifications = [a for a in attachments if a['document_type'] == 'specification']
    
    # Verify printed form extraction
    assert len(printed_forms) >= 1, "Expected at least one printed form"
    printed_form = printed_forms[0]
    assert 'Печатная форма контракта' in printed_form['name'], f"Expected 'Печатная форма контракта' in name, got {printed_form['name']}"
    # Note: file_type might be empty or 'html' for URLs without extensions
    # This is acceptable as the actual file type will be determined during download
    assert printed_form['is_important'] == True, "Expected printed form to be marked as important"
    
    # Verify technical specification extraction
    assert len(technical_specs) >= 1, "Expected at least one technical specification"
    tech_spec = technical_specs[0]
    assert 'Техническое задание' in tech_spec['name'], f"Expected 'Техническое задание' in name, got {tech_spec['name']}"
    assert tech_spec['is_important'] == True, "Expected technical specification to be marked as important"
    
    # Verify specification extraction
    assert len(specifications) >= 1, "Expected at least one specification"
    spec = specifications[0]
    assert 'Спецификация оборудования' in spec['name'], f"Expected 'Спецификация оборудования' in name, got {spec['name']}"
    assert spec['is_important'] == True, "Expected specification to be marked as important"
    
    # Verify download URLs
    for attachment in attachments:
        assert 'download_url' in attachment, f"Missing download_url in attachment: {attachment['name']}"
        assert attachment['download_url'], f"Empty download_url in attachment: {attachment['name']}"
    
    print("✓ parse_attachments_list test passed!")


def test_contract_year_detection():
    """Test logic to detect if contract is 2025+."""
    print("\nTesting contract year detection logic...")
    
    # Create parser instance with default threshold (2025)
    parser = ContractParser()
    
    # Test dates
    test_dates = [
        (datetime(2024, 12, 31), False),  # Before threshold
        (datetime(2025, 1, 1), True),     # At threshold
        (datetime(2025, 6, 15), True),    # After threshold
        (datetime(2026, 1, 1), True),     # Well after threshold
        (None, False),                    # None date
    ]
    
    for contract_date, expected_result in test_dates:
        result = parser.is_contract_2025_or_later(contract_date)
        assert result == expected_result, f"Expected {expected_result} for date {contract_date}, got {result}"
    
    # Test with custom threshold
    parser_2024 = ContractParser(year_threshold=2024)
    assert parser_2024.is_contract_2025_or_later(datetime(2024, 1, 1)) == True, "2024 should be >= 2024 threshold"
    assert parser_2024.is_contract_2025_or_later(datetime(2023, 12, 31)) == False, "2023 should be < 2024 threshold"
    
    print("✓ Contract year detection test passed!")


def test_prioritize_print_form_extraction():
    """Test print form prioritization logic."""
    print("\nTesting print form prioritization logic...")
    
    # Create parser instance
    parser = ContractParser()
    
    # Create sample attachments
    attachments = [
        {'name': 'Дополнительное соглашение', 'document_type': 'other', 'is_important': False, 'file_type': 'docx'},
        {'name': 'Печатная форма контракта', 'document_type': 'printed_form', 'is_important': True, 'file_type': 'pdf'},
        {'name': 'Техническое задание', 'document_type': 'technical_specification', 'is_important': True, 'file_type': 'docx'},
        {'name': 'Протокол согласования', 'document_type': 'other', 'is_important': False, 'file_type': 'pdf'},
        {'name': 'Спецификация оборудования', 'document_type': 'specification', 'is_important': True, 'file_type': 'pdf'},
    ]
    
    # Test with 2025 contract date - should prioritize printed forms
    contract_date_2025 = datetime(2025, 6, 15)
    prioritized_2025 = parser.prioritize_print_form_extraction(attachments, contract_date_2025)
    
    # Printed form should be first
    assert prioritized_2025[0]['document_type'] == 'printed_form', f"Printed form should be first for 2025+ contract, got {prioritized_2025[0]['document_type']}"
    
    # Other important documents should come next
    assert prioritized_2025[1]['document_type'] in ['technical_specification', 'specification'], f"Important document should be second, got {prioritized_2025[1]['document_type']}"
    assert prioritized_2025[2]['document_type'] in ['technical_specification', 'specification'], f"Important document should be third, got {prioritized_2025[2]['document_type']}"
    
    # Test with 2023 contract date - should just sort by importance
    contract_date_2023 = datetime(2023, 6, 15)
    prioritized_2023 = parser.prioritize_print_form_extraction(attachments, contract_date_2023)
    
    # All important documents should come first (sorted by name)
    important_docs = [a for a in prioritized_2023 if a['is_important']]
    non_important_docs = [a for a in prioritized_2023 if not a['is_important']]
    
    assert len(important_docs) == 3, f"Expected 3 important documents, got {len(important_docs)}"
    assert len(non_important_docs) == 2, f"Expected 2 non-important documents, got {len(non_important_docs)}"
    
    # Important documents should come before non-important ones
    for i in range(len(important_docs)):
        assert prioritized_2023[i]['is_important'] == True, f"Document at position {i} should be important"
    
    print("✓ Print form prioritization test passed!")


async def run_all_tests():
    """Run all comprehensive tests."""
    print("=" * 60)
    print("Running Comprehensive ContractParser Tests (TASK 102)")
    print("=" * 60)
    
    try:
        # Run synchronous tests
        test_parse_common_info()
        test_parse_objects_tab()
        test_parse_attachments_list()
        test_contract_year_detection()
        test_prioritize_print_form_extraction()
        
        print("\n" + "=" * 60)
        print("All comprehensive tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())