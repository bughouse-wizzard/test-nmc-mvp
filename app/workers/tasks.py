import asyncio
from datetime import datetime
from typing import Dict, Any, List
from uuid import UUID
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.search import SearchRequest
from app.models.contract import ContractResult
from app.core.config import settings


@shared_task(bind=True, max_retries=3)
def search_contracts(self, search_id: str) -> Dict[str, Any]:
    """Search for contracts in the registry."""
    try:
        # Convert string to UUID
        search_uuid = UUID(search_id)
        
        # Run async function in sync context
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_search_contracts_async(search_uuid))
    except Exception as exc:
        # Retry the task
        raise self.retry(exc=exc, countdown=60)


async def _search_contracts_async(search_id: UUID) -> Dict[str, Any]:
    """Async function to search for contracts."""
    async with AsyncSessionLocal() as session:
        # Get search request
        result = await session.execute(
            select(SearchRequest).where(SearchRequest.id == search_id)
        )
        search_request = result.scalar_one_or_none()
        
        if not search_request:
            return {"error": "Search request not found"}
        
        # Update status
        search_request.status = "RUNNING"
        await session.commit()
        
        try:
            # Import the scraper
            from app.services.scraper.search import search_contracts
            
            # Convert dates from string to datetime
            from datetime import datetime
            date_from = datetime.strptime(search_request.date_from, "%Y-%m-%d")
            date_to = datetime.strptime(search_request.date_to, "%Y-%m-%d")
            
            # Get execution statuses
            execution_statuses = search_request.get_execution_statuses()
            
            # Search for contracts using the scraper
            search_result = await search_contracts(
                ktru_code=search_request.ktru_code,
                date_from=date_from,
                date_to=date_to,
                law=search_request.law,
                customer_region=search_request.customer_region,
                execution_statuses=execution_statuses,
                max_pages=3  # Limit to 3 pages for MVP
            )
            
            # Update search request with results
            search_request.found_total = search_result["found_total"]
            search_request.processed_count = 0
            search_request.status = "DONE"
            await session.commit()
            
            # TODO: Store contract results in database
            # For now, just return the search results
            
            return {
                "search_id": str(search_id),
                "found_total": search_result["found_total"],
                "contracts_found": len(search_result["contracts"]),
                "status": "completed",
            }
            
        except Exception as e:
            search_request.status = "ERROR"
            search_request.error_message = str(e)
            await session.commit()
            raise


@shared_task(bind=True, max_retries=3)
def parse_contract(self, search_id: str, contract_url: str) -> Dict[str, Any]:
    """Parse a single contract."""
    try:
        # Convert string to UUID
        search_uuid = UUID(search_id)
        
        # Run async function in sync context
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_parse_contract_async(search_uuid, contract_url))
    except Exception as exc:
        # Retry the task
        raise self.retry(exc=exc, countdown=30)


async def _parse_contract_async(search_id: UUID, contract_url: str) -> Dict[str, Any]:
    """Async function to parse a contract."""
    async with AsyncSessionLocal() as session:
        # TODO: Implement actual contract parsing logic
        # This is a placeholder for the actual implementation
        
        # Simulate parsing
        await asyncio.sleep(1)
        
        # Create contract result
        contract_result = ContractResult(
            search_id=search_id,
            reestr_number="1234567890",  # Example
            contract_url=contract_url,
            sign_date=datetime(2024, 1, 15),  # Example
            unit_price=1000.0,  # Example
            match_type="HOMOGENEOUS",  # Example
            ai_score=85,  # Example
            raw_data_json={"parsed_data": "example"},
        )
        
        session.add(contract_result)
        await session.commit()
        
        return {
            "contract_id": str(contract_result.id),
            "reestr_number": contract_result.reestr_number,
            "status": "parsed",
        }


@shared_task(bind=True, max_retries=3)
def analyze_with_ai(self, contract_id: str, target_specs: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze contract with AI."""
    try:
        # Convert string to UUID
        contract_uuid = UUID(contract_id)
        
        # Run async function in sync context
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_analyze_with_ai_async(contract_uuid, target_specs))
    except Exception as exc:
        # Retry the task
        raise self.retry(exc=exc, countdown=30)


async def _analyze_with_ai_async(contract_id: UUID, target_specs: Dict[str, Any]) -> Dict[str, Any]:
    """Async function to analyze contract with AI."""
    async with AsyncSessionLocal() as session:
        # Get contract result
        result = await session.execute(
            select(ContractResult).where(ContractResult.id == contract_id)
        )
        contract_result = result.scalar_one_or_none()
        
        if not contract_result:
            return {"error": "Contract not found"}
        
        # TODO: Implement actual AI analysis logic
        # This is a placeholder for the actual implementation
        
        # Check if DeepSeek API key is configured
        if not settings.DEEPSEEK_API_KEY:
            return {"error": "DeepSeek API key not configured"}
        
        # Simulate AI analysis
        await asyncio.sleep(2)
        
        # Update contract result with AI analysis
        contract_result.ai_score = 92  # Example
        contract_result.match_type = "IDENTICAL"  # Example
        contract_result.accepted_for_nmc = True  # Example
        
        await session.commit()
        
        return {
            "contract_id": str(contract_id),
            "ai_score": contract_result.ai_score,
            "match_type": contract_result.match_type,
            "status": "analyzed",
        }