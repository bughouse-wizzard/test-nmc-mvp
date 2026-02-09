#!/usr/bin/env python3
"""
Test script for database connection and operations.
Verifies that the SQLAlchemy models work correctly with the database.
"""

import asyncio
import sys
import os
from datetime import datetime
from decimal import Decimal

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.db.base import Base
from backend.app.models.search import SearchRequest, SearchStatus, InputSource
from backend.app.models.contract import ContractResult, MatchType
from backend.app.models.spec_comparison import SpecComparisonRow, MatchStatus


def test_database_connection():
    """Test database connection and basic operations."""
    print("Testing database connection...")
    
    # Create SQLite engine (using the same database as the application)
    engine = create_engine('sqlite:///nmck.db', echo=False)
    
    # Create a session
    with Session(engine) as session:
        print("✓ Database connection established")
        
        # Test 1: Create a SearchRequest
        print("\nTest 1: Creating SearchRequest...")
        search_request = SearchRequest(
            status=SearchStatus.RUNNING,
            input_source=InputSource.MANUAL,
            ktru_code="123456",
            object_name="Test Object",
            limit_contracts=30,
            nmc_value=Decimal("100000.50"),
            selected_contract_ids=["contract1", "contract2"]
        )
        
        session.add(search_request)
        session.commit()
        print(f"✓ SearchRequest created with ID: {search_request.id}")
        
        # Test 2: Create a ContractResult linked to the SearchRequest
        print("\nTest 2: Creating ContractResult...")
        contract_result = ContractResult(
            search_id=search_request.id,
            reestr_number="123-456-789",
            contract_url="https://example.com/contract/123",
            sign_date=datetime.now(),
            price=Decimal("95000.00"),
            unit_price=Decimal("950.00"),
            match_type=MatchType.IDENTICAL,
            ai_score=85,
            is_2025_plus=True,
            raw_data_json={"key": "value", "nested": {"field": "data"}}
        )
        
        session.add(contract_result)
        session.commit()
        print(f"✓ ContractResult created with ID: {contract_result.id}")
        
        # Test 3: Create a SpecComparisonRow linked to the ContractResult
        print("\nTest 3: Creating SpecComparisonRow...")
        spec_row = SpecComparisonRow(
            contract_result_id=contract_result.id,
            name="Material Quality",
            target_value="Grade A",
            actual_value="Grade A+",
            match_status=MatchStatus.DIFF,
            weight=0.8
        )
        
        session.add(spec_row)
        session.commit()
        print(f"✓ SpecComparisonRow created with ID: {spec_row.id}")
        
        # Test 4: Query the SearchRequest with relationships
        print("\nTest 4: Querying data with relationships...")
        stmt = select(SearchRequest).where(SearchRequest.id == search_request.id)
        queried_search = session.scalar(stmt)
        
        if queried_search:
            print(f"✓ Found SearchRequest: {queried_search.object_name}")
            print(f"  Status: {queried_search.status}")
            print(f"  Input Source: {queried_search.input_source}")
            print(f"  NMC Value: {queried_search.nmc_value}")
            print(f"  Created at: {queried_search.created_at}")
            
            # Access relationships
            print(f"  Number of contract results: {len(queried_search.contract_results)}")
            
            for contract in queried_search.contract_results:
                print(f"  - Contract: {contract.reestr_number}")
                print(f"    Price: {contract.price}, Unit Price: {contract.unit_price}")
                print(f"    Match Type: {contract.match_type}, AI Score: {contract.ai_score}")
                print(f"    Is 2025+: {contract.is_2025_plus}")
                
                # Access spec comparison rows
                print(f"    Number of spec rows: {len(contract.spec_comparison_rows)}")
                for spec in contract.spec_comparison_rows:
                    print(f"    * Spec: {spec.name}")
                    print(f"      Target: {spec.target_value}, Actual: {spec.actual_value}")
                    print(f"      Match Status: {spec.match_status}, Weight: {spec.weight}")
        
        # Test 5: Update a record
        print("\nTest 5: Updating SearchRequest status...")
        queried_search.status = SearchStatus.DONE
        queried_search.nmc_value = Decimal("105000.75")
        session.commit()
        print(f"✓ Updated SearchRequest status to {queried_search.status}")
        
        # Test 6: Delete records (cleanup)
        print("\nTest 6: Cleaning up test data...")
        session.delete(spec_row)
        session.delete(contract_result)
        session.delete(queried_search)
        session.commit()
        print("✓ Test data cleaned up")
        
        # Verify deletion
        stmt = select(SearchRequest).where(SearchRequest.id == search_request.id)
        deleted_search = session.scalar(stmt)
        if not deleted_search:
            print("✓ SearchRequest successfully deleted")
        
        print("\n" + "="*50)
        print("All tests passed successfully!")
        print("="*50)


if __name__ == "__main__":
    try:
        test_database_connection()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)