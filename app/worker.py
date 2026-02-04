"""Celery worker tasks for search processing."""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.db import AsyncSessionLocal
from app.models.search_request import SearchRequest, SearchStatus
from app.models.contract_result import ContractResult, MatchType


@shared_task(bind=True, max_retries=3)
def run_search_task(self, search_id: str) -> Dict[str, Any]:
    """Run search task: fetch SearchRequest, update status, call scraper, save ContractResult rows.
    
    Args:
        search_id: UUID of the search request
        
    Returns:
        Dictionary with task results
    """
    try:
        # Convert string to UUID
        search_uuid = UUID(search_id)
        
        # Run async function in sync context
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_run_search_task_async(search_uuid))
    except Exception as exc:
        # Retry the task
        raise self.retry(exc=exc, countdown=60)


async def _run_search_task_async(search_id: UUID) -> Dict[str, Any]:
    """Async function to run search task."""
    async with AsyncSessionLocal() as session:
        # Get search request
        result = await session.execute(
            select(SearchRequest).where(SearchRequest.id == search_id)
        )
        search_request = result.scalar_one_or_none()
        
        if not search_request:
            return {"error": "Search request not found"}
        
        # Update status to RUNNING if not already
        if search_request.status != SearchStatus.RUNNING:
            search_request.status = SearchStatus.RUNNING
            await session.commit()
        
        try:
            # Call scraper to get contract data
            # This is a placeholder - in real implementation, this would call actual scraper
            contracts_data = await _call_scraper(search_request)
            
            # Save initial ContractResult rows with basic info
            saved_count = await _save_contract_results(session, search_id, contracts_data)
            
            # Update search request with results
            search_request.found_total = len(contracts_data)
            search_request.processed_count = saved_count
            
            # Check if search was stopped during processing
            # Refresh the search request to get latest status
            await session.refresh(search_request)
            
            if search_request.status == SearchStatus.STOPPED:
                return {
                    "search_id": str(search_id),
                    "status": "stopped",
                    "found_total": len(contracts_data),
                    "processed_count": saved_count,
                    "message": "Search was stopped during processing"
                }
            
            # Mark as DONE if all contracts processed
            if saved_count >= len(contracts_data):
                search_request.status = SearchStatus.DONE
            else:
                search_request.status = SearchStatus.RUNNING
            
            await session.commit()
            
            return {
                "search_id": str(search_id),
                "status": "completed" if search_request.status == SearchStatus.DONE else "running",
                "found_total": len(contracts_data),
                "processed_count": saved_count,
            }
            
        except Exception as e:
            search_request.status = SearchStatus.ERROR
            search_request.error_message = str(e)
            await session.commit()
            raise


async def _call_scraper(search_request: SearchRequest) -> List[Dict[str, Any]]:
    """Call scraper to get contract data.
    
    This is a placeholder function that simulates scraper results.
    In a real implementation, this would call an actual web scraper.
    
    Args:
        search_request: Search request object
        
    Returns:
        List of contract data dictionaries
    """
    # Simulate scraper delay
    await asyncio.sleep(2)
    
    # Generate mock contract data based on search parameters
    contracts = []
    for i in range(10):  # Generate 10 mock contracts
        contract = {
            "reestr_number": f"1234567890{i:02d}",
            "contract_url": f"https://zakupki.gov.ru/contract/{1234567890 + i}",
            "sign_date": datetime(2024, 1, 15 + i).strftime("%Y-%m-%d"),
            "unit_price": 1000.0 + (i * 100),
            "currency": "RUB",
            "manufacturer_found": f"Manufacturer {i+1}",
            "raw_data": {
                "object_name": search_request.object_name,
                "ktru_code": search_request.ktru_code,
                "customer": f"Customer {i+1}",
                "region": search_request.customer_region,
            }
        }
        contracts.append(contract)
    
    return contracts


async def _save_contract_results(
    session: AsyncSession, 
    search_id: UUID, 
    contracts_data: List[Dict[str, Any]]
) -> int:
    """Save contract results to database.
    
    Args:
        session: Database session
        search_id: Search request ID
        contracts_data: List of contract data dictionaries
        
    Returns:
        Number of contracts saved
    """
    saved_count = 0
    
    for i, contract_data in enumerate(contracts_data):
        # Check if we should stop (simulate stop logic check)
        # In real implementation, this would check a flag in the database
        if i > 0 and i % 3 == 0:  # Check every 3rd contract
            # Check if search was stopped
            result = await session.execute(
                select(SearchRequest.status).where(SearchRequest.id == search_id)
            )
            status = result.scalar_one_or_none()
            
            if status == SearchStatus.STOPPED:
                break
        
        # Create ContractResult object
        contract_result = ContractResult(
            search_id=str(search_id),
            reestr_number=contract_data["reestr_number"],
            contract_url=contract_data["contract_url"],
            sign_date=contract_data["sign_date"],
            unit_price=contract_data["unit_price"],
            currency=contract_data["currency"],
            match_type=MatchType.HOMOGENEOUS,  # Default match type
            ai_score=70 + (i % 30),  # Random score between 70-99
            manufacturer_found=contract_data.get("manufacturer_found"),
            manufacturer_match=False,  # Default
            is_2025_plus=False,  # Default
            accepted_for_nmc=False,  # Default
            raw_data_json=contract_data.get("raw_data", {}),
        )
        
        session.add(contract_result)
        saved_count += 1
    
    # Commit all saved contracts
    if saved_count > 0:
        await session.commit()
    
    return saved_count


async def check_and_stop_search(search_id: UUID) -> bool:
    """Check if search should be stopped and update status if needed.
    
    Args:
        search_id: Search request ID
        
    Returns:
        True if search was stopped, False otherwise
    """
    async with AsyncSessionLocal() as session:
        # Get search request
        result = await session.execute(
            select(SearchRequest).where(SearchRequest.id == search_id)
        )
        search_request = result.scalar_one_or_none()
        
        if not search_request:
            return False
        
        # Check if search should be stopped
        # In real implementation, this might check additional conditions
        if search_request.status == SearchStatus.STOPPED:
            return True
        
        return False