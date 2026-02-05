"""
Celery tasks for background processing.
Implements the complete workflow for processing search requests.
"""
import asyncio
import time
import logging
import aiohttp
import httpx
from uuid import UUID
from typing import Dict, Any, List, Optional
from datetime import datetime
from celery import current_task

from .celery_app import celery_app
from .database import db_manager
from .redis_manager import redis_manager
from .contract_processor import ContractProcessor, ProcessingResult
from .finalizer import SearchFinalizer
from ..core.event_channel import event_channel
from ..core.events import (
    ProgressEvent, ResultAddedEvent, DoneEvent, ErrorEvent,
    EventType
)
from ...models import (
    SearchRequest, SearchStatus, ContractResult, MatchType,
    SpecComparisonRow, MatchStatus as ModelMatchStatus
)
from ...services.parser.search import SearchParser

logger = logging.getLogger(__name__)


async def _initialize_event_channel():
    """Initialize event channel if not already initialized."""
    try:
        await event_channel.initialize()
    except Exception as e:
        logger.warning(f"Event channel initialization failed: {e}")
        pass  # Already initialized or failed


@celery_app.task(bind=True, name="process_search")
def process_search(self, search_id: str):
    """
    Process a search request in the background.
    
    Args:
        search_id: ID of the search request to process
    """
    # Run async function in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        start_time = time.time()
        loop.run_until_complete(_process_search_async(search_id))
        runtime_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Search {search_id} completed in {runtime_ms}ms")
    except Exception as e:
        logger.error(f"Error processing search {search_id}: {e}")
        raise
    finally:
        loop.close()


async def _process_search_async(search_id: str):
    """
    Async implementation of search processing.
    
    Args:
        search_id: ID of the search request to process
    """
    search_uuid = UUID(search_id)
    
    # Initialize event channel
    await _initialize_event_channel()
    
    # Initialize HTTP clients
    http_session = None
    http_client = None
    
    try:
        # Load search request from database
        search_request = await _load_search_request(search_id)
        if not search_request:
            raise ValueError(f"Search request {search_id} not found")
        
        # Update status to RUNNING
        await _update_search_status(search_id, SearchStatus.RUNNING)
        
        # Send initial progress event
        await _send_progress_event(
            search_uuid, 
            processed=0, 
            total=0, 
            status="Starting search..."
        )
        
        # Step 1: Search for contracts using SearchParser
        contracts = await _search_contracts(search_request)
        if not contracts:
            await _complete_search_with_error(
                search_uuid, search_id, 
                "No contracts found matching the criteria"
            )
            return
        
        # Check for stop signal before starting processing
        if redis_manager.check_stop_signal(search_id):
            await _complete_search_stopped(search_uuid, search_id, len(contracts))
            return
        
        # Step 2: Process contracts
        processed_results = await _process_contracts(
            search_request, contracts, search_uuid, search_id
        )
        
        # Step 3: Finalize search
        await _finalize_search(
            search_request, processed_results, search_uuid, search_id
        )
        
    except Exception as e:
        logger.error(f"Error processing search {search_id}: {e}", exc_info=True)
        await _handle_processing_error(search_uuid, search_id, str(e))
        raise
    finally:
        # Cleanup HTTP clients
        if http_session:
            await http_session.close()
        if http_client:
            await http_client.aclose()


async def _load_search_request(search_id: str) -> SearchRequest:
    """Load search request from database."""
    with db_manager.get_session() as session:
        search_request = session.query(SearchRequest).filter(
            SearchRequest.id == search_id
        ).first()
        
        if not search_request:
            raise ValueError(f"Search request {search_id} not found")
        
        return search_request


async def _update_search_status(search_id: str, status: SearchStatus, error_message: str = None):
    """Update search request status in database."""
    with db_manager.get_session() as session:
        search_request = session.query(SearchRequest).filter(
            SearchRequest.id == search_id
        ).first()
        
        if search_request:
            search_request.status = status
            if error_message:
                search_request.error_message = error_message
            session.commit()
            logger.info(f"Updated search {search_id} status to {status}")


async def _search_contracts(search_request: SearchRequest) -> List[Dict[str, Any]]:
    """Search for contracts using SearchParser."""
    try:
        logger.info(f"Searching contracts for: {search_request.object_name}")
        
        # Initialize search parser
        search_parser = SearchParser()
        
        # Build search URL
        search_url = search_parser.build_search_url(
            ktru_code=search_request.ktru_code,
            customer_region=search_request.customer_region,
            law=search_request.law,
            date_from=search_request.date_from,
            date_to=search_request.date_to,
            execution_statuses=search_request.execution_statuses,
            page_size=min(search_request.limit_contracts, 50)
        )
        
        logger.debug(f"Search URL: {search_url}")
        
        # Create HTTP session
        async with aiohttp.ClientSession() as session:
            # Fetch search results
            html = await search_parser._make_request_with_retry(search_url, session)
            if not html:
                raise ValueError("Failed to fetch search results")
            
            # Parse search results
            total_found, contracts = search_parser._parse_search_results(html)
            
            # Limit to requested number of contracts
            contracts = contracts[:search_request.limit_contracts]
            
            logger.info(f"Found {total_found} contracts, processing {len(contracts)}")
            
            # Update total found in database
            with db_manager.get_session() as db_session:
                search_request_db = db_session.query(SearchRequest).filter(
                    SearchRequest.id == search_request.id
                ).first()
                if search_request_db:
                    search_request_db.found_total = total_found
                    db_session.commit()
            
            return contracts
            
    except Exception as e:
        logger.error(f"Failed to search contracts: {e}")
        raise


async def _process_contracts(
    search_request: SearchRequest,
    contracts: List[Dict[str, Any]],
    search_uuid: UUID,
    search_id: str
) -> List[ProcessingResult]:
    """Process contracts through the pipeline."""
    processed_results = []
    total_contracts = len(contracts)
    
    # Initialize HTTP clients for contract processing
    http_session = aiohttp.ClientSession()
    http_client = httpx.AsyncClient(timeout=30.0)
    
    try:
        # Initialize contract processor
        contract_processor = ContractProcessor(
            search_request=search_request,
            http_session=http_session,
            http_client=http_client
        )
        
        for i, contract in enumerate(contracts):
            # Check for stop signal
            if redis_manager.check_stop_signal(search_id):
                logger.info(f"Stop signal received for search {search_id}")
                break
            
            # Update progress
            await _send_progress_event(
                search_uuid,
                processed=i,
                total=total_contracts,
                status=f"Processing contract {i+1}/{total_contracts}"
            )
            
            # Update Redis progress
            redis_manager.update_progress(
                search_id, i, total_contracts,
                f"Processing contract {i+1}/{total_contracts}"
            )
            
            try:
                # Process contract
                result = await contract_processor.process_contract(
                    contract_url=contract.get("url", ""),
                    reestr_number=contract.get("reestr_number", ""),
                    sign_date=contract.get("sign_date", datetime.now()),
                    total_price=contract.get("price")
                )
                
                if result:
                    # Save to database
                    await _save_contract_result(result)
                    
                    # Add to results
                    processed_results.append(result)
                    
                    # Send result event
                    await _send_result_event(search_uuid, result)
                    
                    logger.info(f"Processed contract {i+1}/{total_contracts}: "
                               f"{contract.get('reestr_number')}")
                else:
                    logger.warning(f"Failed to process contract: {contract.get('reestr_number')}")
                    
            except Exception as e:
                logger.error(f"Error processing contract {contract.get('reestr_number')}: {e}")
                # Continue with next contract
        
        return processed_results
        
    finally:
        # Close HTTP clients
        await http_session.close()
        await http_client.aclose()


async def _save_contract_result(processing_result: ProcessingResult):
    """Save contract result to database."""
    with db_manager.get_session() as session:
        # Convert dictionary to ContractResult model
        contract_data = processing_result.contract_result
        
        # Handle match_type enum
        match_type_str = contract_data.get("match_type", "NO_MATCH")
        match_type = MatchType(match_type_str) if match_type_str in ["IDENTICAL", "HOMOGENEOUS", "NO_MATCH"] else MatchType.NO_MATCH
        
        # Create ContractResult
        contract_result = ContractResult(
            id=contract_data["id"],
            search_id=contract_data["search_id"],
            reestr_number=contract_data["reestr_number"],
            contract_url=contract_data["contract_url"],
            sign_date=contract_data["sign_date"],
            unit_price=contract_data.get("unit_price"),
            currency=contract_data.get("currency", "RUB"),
            match_type=match_type,
            ai_score=contract_data["ai_score"],
            manufacturer_target=contract_data.get("manufacturer_target"),
            manufacturer_found=contract_data.get("manufacturer_found"),
            manufacturer_match=contract_data.get("manufacturer_match"),
            is_2025_plus=contract_data.get("is_2025_plus", False),
            accepted_for_nmc=contract_data.get("accepted_for_nmc", False),
            raw_data_json=contract_data.get("raw_data_json", {})
        )
        
        session.add(contract_result)
        
        # Create SpecComparisonRows
        for row_data in processing_result.spec_comparison_rows:
            spec_row = SpecComparisonRow(
                id=row_data["id"],
                contract_result_id=row_data["contract_result_id"],
                name=row_data["name"],
                target_value=row_data.get("target_value"),
                actual_value=row_data.get("actual_value"),
                match_status=ModelMatchStatus(row_data["match_status"]),
                weight=row_data.get("weight", 1)
            )
            session.add(spec_row)
        
        session.commit()
        logger.debug(f"Saved contract result: {contract_result.reestr_number}")


async def _finalize_search(
    search_request: SearchRequest,
    processed_results: List[ProcessingResult],
    search_uuid: UUID,
    search_id: str
):
    """Finalize search processing."""
    try:
        # Convert ProcessingResults to dictionaries for finalizer
        contract_dicts = []
        for result in processed_results:
            contract_dict = result.contract_result.copy()
            contract_dict["ai_score"] = result.ai_score
            contract_dict["match_type"] = result.match_type
            contract_dict["manufacturer_match"] = result.manufacturer_match
            contract_dict["unit_price"] = result.unit_price
            contract_dicts.append(contract_dict)
        
        # Initialize finalizer
        finalizer = SearchFinalizer()
        
        # Select top contracts
        selected_contracts, selected_ids = finalizer.select_top_contracts(
            contract_dicts, count=3
        )
        
        # Calculate NMCK
        nmck_value = finalizer.calculate_nmck(selected_contracts)
        
        # Update contracts with NMCK acceptance
        updated_contracts = finalizer.update_contracts_for_nmc(
            contract_dicts, selected_ids
        )
        
        # Update contracts in database
        await _update_contracts_acceptance(updated_contracts)
        
        # Prepare final update data
        update_data = finalizer.prepare_final_update(
            search_id=search_id,
            total_found=search_request.found_total or 0,
            total_processed=len(processed_results),
            selected_contract_ids=selected_ids,
            nmck_value=nmck_value
        )
        
        # Update search request in database
        await _update_search_final(
            search_id, 
            update_data["status"],
            update_data["found_total"],
            update_data["processed_count"],
            update_data["selected_contract_ids"],
            update_data["nmc_value"],
            update_data["error_message"]
        )
        
        # Send completion event
        await _send_done_event(
            search_uuid,
            total_processed=len(processed_results),
            total_found=search_request.found_total or 0,
            nmck_value=nmck_value,
            selected_count=len(selected_ids)
        )
        
        # Clear Redis data
        redis_manager.clear_stop_signal(search_id)
        redis_manager.clear_progress(search_id)
        
        logger.info(f"Search {search_id} finalized successfully")
        
    except Exception as e:
        logger.error(f"Error finalizing search {search_id}: {e}")
        raise


async def _update_contracts_acceptance(updated_contracts: List[Dict[str, Any]]):
    """Update contract acceptance status in database."""
    with db_manager.get_session() as session:
        for contract_data in updated_contracts:
            contract_id = contract_data.get("id")
            accepted = contract_data.get("accepted_for_nmc", False)
            
            if contract_id:
                contract = session.query(ContractResult).filter(
                    ContractResult.id == contract_id
                ).first()
                
                if contract:
                    contract.accepted_for_nmc = accepted
        
        session.commit()
        logger.debug(f"Updated acceptance status for {len(updated_contracts)} contracts")


async def _update_search_final(
    search_id: str,
    status: str,
    found_total: int,
    processed_count: int,
    selected_contract_ids: List[str],
    nmc_value: Optional[float],
    error_message: Optional[str] = None
):
    """Update search request with final results."""
    with db_manager.get_session() as session:
        search_request = session.query(SearchRequest).filter(
            SearchRequest.id == search_id
        ).first()
        
        if search_request:
            search_request.status = SearchStatus(status)
            search_request.found_total = found_total
            search_request.processed_count = processed_count
            search_request.selected_contract_ids = selected_contract_ids
            search_request.nmc_value = nmc_value
            search_request.error_message = error_message
            
            session.commit()
            logger.info(f"Updated search {search_id} with final results")


async def _send_progress_event(search_uuid: UUID, processed: int, total: int, status: str):
    """Send progress event."""
    try:
        progress_event = ProgressEvent(
            search_id=search_uuid,
            processed_count=processed,
            found_total=total,
            status=status
        )
        await event_channel.publish(search_uuid, progress_event)
    except Exception as e:
        logger.warning(f"Failed to send progress event: {e}")


async def _send_result_event(search_uuid: UUID, result: ProcessingResult):
    """Send result added event."""
    try:
        result_event = ResultAddedEvent(
            search_id=search_uuid,
            contract_id=UUID(result.contract_result["id"]),
            reestr_number=result.contract_result["reestr_number"],
            unit_price=result.unit_price,
            match_type=result.match_type,
            ai_score=result.ai_score,
            manufacturer_match=result.manufacturer_match
        )
        await event_channel.publish(search_uuid, result_event)
    except Exception as e:
        logger.warning(f"Failed to send result event: {e}")


async def _send_done_event(
    search_uuid: UUID, 
    total_processed: int, 
    total_found: int,
    nmck_value: Optional[float],
    selected_count: int
):
    """Send done event."""
    try:
        done_event = DoneEvent(
            search_id=search_uuid,
            total_processed=total_processed,
            total_found=total_found,
            nmc_value=nmck_value,
            selected_count=selected_count
        )
        await event_channel.publish(search_uuid, done_event)
    except Exception as e:
        logger.warning(f"Failed to send done event: {e}")


async def _complete_search_with_error(search_uuid: UUID, search_id: str, error_message: str):
    """Complete search with error."""
    logger.error(f"Search {search_id} failed: {error_message}")
    
    # Send error event
    error_event = ErrorEvent(
        search_id=search_uuid,
        error_message=error_message,
        error_code="NO_CONTRACTS_FOUND"
    )
    await event_channel.publish(search_uuid, error_event)
    
    # Update database
    await _update_search_status(search_id, SearchStatus.ERROR, error_message)
    
    # Clear Redis data
    redis_manager.clear_stop_signal(search_id)
    redis_manager.clear_progress(search_id)


async def _complete_search_stopped(search_uuid: UUID, search_id: str, total_found: int):
    """Complete search as stopped."""
    logger.info(f"Search {search_id} stopped by user")
    
    # Update database
    await _update_search_status(search_id, SearchStatus.STOPPED)
    
    # Send done event with stopped status
    done_event = DoneEvent(
        search_id=search_uuid,
        total_processed=0,
        total_found=total_found,
        nmc_value=None,
        selected_count=0
    )
    await event_channel.publish(search_uuid, done_event)
    
    # Clear Redis data
    redis_manager.clear_stop_signal(search_id)
    redis_manager.clear_progress(search_id)


async def _handle_processing_error(search_uuid: UUID, search_id: str, error_message: str):
    """Handle processing error."""
    logger.error(f"Processing error for search {search_id}: {error_message}")
    
    # Send error event
    error_event = ErrorEvent(
        search_id=search_uuid,
        error_message=error_message,
        error_code="PROCESSING_ERROR"
    )
    await event_channel.publish(search_uuid, error_event)
    
    # Update database
    await _update_search_status(search_id, SearchStatus.ERROR, error_message)
    
    # Clear Redis data
    redis_manager.clear_stop_signal(search_id)
    redis_manager.clear_progress(search_id)


@celery_app.task(name="stop_search")
def stop_search(search_id: str):
    """
    Stop a running search.
    
    Args:
        search_id: ID of the search request to stop
    """
    try:
        # Set stop signal in Redis
        success = redis_manager.set_stop_signal(search_id)
        
        if success:
            logger.info(f"Stop signal set for search {search_id}")
            return {"status": "stopping", "search_id": search_id}
        else:
            logger.error(f"Failed to set stop signal for search {search_id}")
            return {"status": "error", "search_id": search_id, "message": "Failed to set stop signal"}
            
    except Exception as e:
        logger.error(f"Error stopping search {search_id}: {e}")
        return {"status": "error", "search_id": search_id, "message": str(e)}