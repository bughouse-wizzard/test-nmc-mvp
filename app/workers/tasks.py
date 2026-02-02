import asyncio
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models.contract import ContractResult
from app.models.search import SearchRequest


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
            # TODO: Implement actual contract search logic
            # This is a placeholder for the actual implementation

            # Simulate searching
            await asyncio.sleep(2)

            # Update search request with results
            search_request.found_total = 10  # Example value
            search_request.processed_count = 0
            search_request.status = "DONE"
            await session.commit()

            return {
                "search_id": str(search_id),
                "found_total": 10,
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
def analyze_with_ai(
    self, contract_id: str, target_specs: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyze contract with AI."""
    try:
        # Convert string to UUID
        contract_uuid = UUID(contract_id)

        # Run async function in sync context
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            _analyze_with_ai_async(contract_uuid, target_specs)
        )
    except Exception as exc:
        # Retry the task
        raise self.retry(exc=exc, countdown=30)


async def _analyze_with_ai_async(
    contract_id: UUID, target_specs: Dict[str, Any]
) -> Dict[str, Any]:
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
