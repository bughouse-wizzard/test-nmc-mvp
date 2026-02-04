#!/usr/bin/env python3
"""Test script to verify database models work correctly"""

import sys
import os
from datetime import datetime, timezone
from uuid import uuid4

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.nmc_mvp.database.database import SessionLocal, engine
from src.nmc_mvp.models import (
    SearchRequest, ContractResult, SpecComparisonRow,
    SearchStatus, InputSource, MatchStatus
)


def test_models():
    """Test that models can be created and have correct relationships"""
    print("Testing database models...")
    
    # Create a test session
    db = SessionLocal()
    
    try:
        # Test 1: Create a SearchRequest
        print("\n1. Testing SearchRequest creation...")
        search_request = SearchRequest(
            input_source=InputSource.MANUAL,
            object_name="Бумага офисная",
            ktru_code="24.11.11.110",
            okpd2_code="17.12.14.110",
            customer_region="СЗФО",
            date_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2026, 1, 1, tzinfo=timezone.utc),
            limit_contracts=30,
            found_total=150,
            processed_count=10,
            nmc_value=12500.50,
            selected_contract_ids=[str(uuid4()), str(uuid4()), str(uuid4())],
            runtime_ms=5000,
            search_parameters_json={
                "object_name": "Бумага офисная",
                "ktru_code": "24.11.11.110",
                "region": "СЗФО"
            }
        )
        
        print(f"   Created SearchRequest: {search_request}")
        print(f"   Status: {search_request.status}")
        print(f"   Input source: {search_request.input_source}")
        print(f"   Object name: {search_request.object_name}")
        print(f"   KTRU code: {search_request.ktru_code}")
        print(f"   Found total: {search_request.found_total}")
        print(f"   NMC value: {search_request.nmc_value}")
        
        # Test 2: Create a ContractResult
        print("\n2. Testing ContractResult creation...")
        contract_result = ContractResult(
            search_id=search_request.id,
            reestr_number="0373200004523000010",
            contract_url="https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber=0373200004523000010",
            sign_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            unit_price=12000.75,
            currency="RUB",
            match_type="IDENTICAL",
            ai_score=95,
            manufacturer_target="Xerox",
            manufacturer_found="Xerox",
            manufacturer_match=True,
            is_2025_plus=False,
            accepted_for_nmc=True,
            contract_price=36022.25,
            customer_name="ГУП 'Тест'",
            supplier_name="ООО 'Поставщик'",
            raw_data_json={
                "contract_number": "0373200004523000010",
                "price": 36022.25,
                "customer": "ГУП 'Тест'"
            }
        )
        
        print(f"   Created ContractResult: {contract_result}")
        print(f"   Reestr number: {contract_result.reestr_number}")
        print(f"   Match type: {contract_result.match_type}")
        print(f"   AI Score: {contract_result.ai_score}")
        print(f"   Unit price: {contract_result.unit_price}")
        print(f"   Accepted for NMC: {contract_result.accepted_for_nmc}")
        
        # Test 3: Create SpecComparisonRow
        print("\n3. Testing SpecComparisonRow creation...")
        spec_row = SpecComparisonRow(
            contract_result_id=contract_result.id,
            name="Плотность",
            target_value="80 г/м²",
            actual_value="80 г/м²",
            match_status=MatchStatus.MATCH,
            weight=1.0,
            unit="г/м²",
            notes="Точное совпадение"
        )
        
        print(f"   Created SpecComparisonRow: {spec_row}")
        print(f"   Name: {spec_row.name}")
        print(f"   Target value: {spec_row.target_value}")
        print(f"   Actual value: {spec_row.actual_value}")
        print(f"   Match status: {spec_row.match_status}")
        print(f"   Weight: {spec_row.weight}")
        
        # Test 4: Test relationships
        print("\n4. Testing relationships...")
        search_request.contract_results = [contract_result]
        contract_result.spec_comparisons = [spec_row]
        
        print(f"   SearchRequest has {len(search_request.contract_results)} contract results")
        print(f"   ContractResult has {len(contract_result.spec_comparisons)} spec comparison rows")
        
        # Test 5: Verify enum values
        print("\n5. Testing enum values...")
        print(f"   SearchStatus values: {[status.value for status in SearchStatus]}")
        print(f"   InputSource values: {[source.value for source in InputSource]}")
        print(f"   MatchStatus values: {[status.value for status in MatchStatus]}")
        
        print("\n✅ All model tests passed!")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()
    
    return True


def test_schema_creation():
    """Test that tables can be created from models"""
    print("\n\nTesting schema creation from models...")
    
    try:
        # This would normally create tables in a database
        # For now, just verify the metadata is correct
        from src.nmc_mvp.database.database import Base
        
        tables = list(Base.metadata.tables.keys())
        print(f"   Tables in metadata: {tables}")
        
        expected_tables = ['search_request', 'contract_result', 'spec_comparison_row']
        for table in expected_tables:
            if table in tables:
                print(f"   ✓ Table '{table}' found in metadata")
            else:
                print(f"   ✗ Table '{table}' NOT found in metadata")
                return False
        
        print("\n✅ Schema creation test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error during schema test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Database Models Test Suite")
    print("=" * 60)
    
    success = True
    
    # Run model tests
    if not test_models():
        success = False
    
    # Run schema tests
    if not test_schema_creation():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed successfully!")
    else:
        print("❌ Some tests failed")
    print("=" * 60)
    
    sys.exit(0 if success else 1)