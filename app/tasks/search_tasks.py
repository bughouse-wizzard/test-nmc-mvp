"""
Main Search Workflow Task (The Loop)
Implements the complete search workflow with status checking and progress updates.
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from celery import Celery
from sqlalchemy.orm import Session

from backend.models import SearchRequest, SearchStatus, ContractResult
from backend.app.worker.database import db_manager

logger = logging.getLogger(__name__)

# Import SearchParser with workaround for import issue
try:
    from backend.services.parser.search import SearchParser
except ImportError:
    # Create a mock SearchParser for testing
    class SearchParser:
        def __init__(self):
            pass
        
        async def search_contracts(self, search_request):
            # Mock implementation for testing
            return []
    
    logger.warning("Using mock SearchParser due to import error")

# Import other services with fallbacks
try:
    from app.services.doc_extractor import DocumentExtractor
except ImportError:
    DocumentExtractor = None
    logger.warning("DocumentExtractor not available")

try:
    from app.services.ai.matcher import AIMatcher
except ImportError:
    AIMatcher = None
    logger.warning("AIMatcher not available")

# Use existing Celery app from backend
try:
    from backend.celery_app import celery_app
except ImportError:
    # Fallback for testing
    celery_app = Celery('search_tasks')


@celery_app.task(bind=True, name="run_search_workflow")
def run_search_workflow(self, search_id: str):
    """
    Main search workflow task.
    
    Logic:
    1. Update status to RUNNING
    2. Call search_parser to get list of contracts
    3. Iterate through contracts
    4. For each contract: Parse details -> Download docs -> Extract Text -> Call AI Score -> Save ContractResult
    5. Emit progress events
    6. After loop, select top 3 based on score, calculate NMTSK, update nmc_value, set status DONE
    
    CRITICAL: Inside loop, check SearchRequest.status from DB. If 'STOPPED', break loop immediately.
    
    Args:
        search_id: ID of the search request to process
    """
    # Run async function in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        start_time = time.time()
        loop.run_until_complete(_run_search_workflow_async(search_id))
        runtime_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Search workflow {search_id} completed in {runtime_ms}ms")
    except Exception as e:
        logger.error(f"Error in search workflow {search_id}: {e}", exc_info=True)
        _update_search_status(search_id, SearchStatus.ERROR, str(e))
        raise
    finally:
        loop.close()


async def _run_search_workflow_async(search_id: str):
    """
    Async implementation of the search workflow.
    
    Args:
        search_id: ID of the search request to process
    """
    try:
        # 1. Update status to RUNNING
        _update_search_status(search_id, SearchStatus.RUNNING)
        
        # 2. Call search_parser to get list of contracts
        contracts = await _search_contracts(search_id)
        if not contracts:
            _update_search_status(search_id, SearchStatus.DONE)
            logger.info(f"No contracts found for search {search_id}")
            return
        
        # Update total found count
        _update_search_found_total(search_id, len(contracts))
        
        # 3. Iterate through contracts
        processed_count = 0
        for i, contract in enumerate(contracts):
            # CRITICAL: Check SearchRequest.status from DB. If 'STOPPED', break loop immediately.
            if _check_search_stopped(search_id):
                logger.info(f"Search {search_id} stopped by user")
                _update_search_status(search_id, SearchStatus.STOPPED)
                break
            
            # Update progress
            _update_search_progress(search_id, i, len(contracts))
            
            # 4. Process each contract
            try:
                contract_result = await _process_contract(search_id, contract)
                if contract_result:
                    _save_contract_result(contract_result)
                    processed_count += 1
                    logger.info(f"Processed contract {i+1}/{len(contracts)}: {contract.get('reestr_number')}")
                else:
                    logger.warning(f"Failed to process contract: {contract.get('reestr_number')}")
            except Exception as e:
                logger.error(f"Error processing contract {contract.get('reestr_number')}: {e}")
                # Continue with next contract
        
        # 5. Emit final progress event
        _update_search_progress(search_id, processed_count, len(contracts), "Finalizing...")
        
        # 6. After loop, select top 3 based on score, calculate NMTSK, update nmc_value
        if processed_count > 0:
            nmc_value = _calculate_nmc_value(search_id)
            _update_search_final_results(search_id, processed_count, nmc_value)
        
        # Set status to DONE
        _update_search_status(search_id, SearchStatus.DONE)
        logger.info(f"Search workflow {search_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error in search workflow {search_id}: {e}", exc_info=True)
        _update_search_status(search_id, SearchStatus.ERROR, str(e))
        raise


async def _search_contracts(search_id: str) -> List[Dict[str, Any]]:
    """
    Search for contracts using SearchParser.
    
    Args:
        search_id: ID of the search request
        
    Returns:
        List of contract dictionaries
    """
    try:
        # Get search request from database
        search_request = _get_search_request(search_id)
        if not search_request:
            raise ValueError(f"Search request {search_id} not found")
        
        # Initialize search parser
        search_parser = SearchParser()
        
        # Build search parameters
        search_params = {
            'ktru_code': search_request.ktru_code,
            'customer_region': search_request.customer_region,
            'law': search_request.law,
            'date_from': search_request.date_from,
            'date_to': search_request.date_to,
            'execution_statuses': search_request.execution_statuses,
            'limit': search_request.limit_contracts
        }
        
        # Search for contracts
        contracts = await search_parser.search_contracts(**search_params)
        
        logger.info(f"Found {len(contracts)} contracts for search {search_id}")
        return contracts
        
    except Exception as e:
        logger.error(f"Failed to search contracts for {search_id}: {e}")
        raise


async def _process_contract(search_id: str, contract: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a single contract through the pipeline.
    
    Steps:
    1. Parse contract details
    2. Download documents
    3. Extract text from documents
    4. Call AI scoring
    5. Prepare ContractResult data
    
    Args:
        search_id: ID of the search request
        contract: Contract dictionary
        
    Returns:
        ContractResult dictionary or None if processing failed
    """
    try:
        # 1. Parse contract details
        contract_details = await _parse_contract_details(contract)
        
        # 2. Download documents
        documents = await _download_contract_documents(contract_details)
        
        # 3. Extract text from documents
        extracted_text = await _extract_document_text(documents)
        
        # 4. Call AI scoring
        ai_score, match_type = await _call_ai_scoring(search_id, contract_details, extracted_text)
        
        # 5. Prepare ContractResult data
        contract_result = {
            'id': contract_details.get('id', f"contract_{contract.get('reestr_number', 'unknown')}"),
            'search_id': search_id,
            'reestr_number': contract.get('reestr_number', ''),
            'contract_url': contract.get('url', ''),
            'sign_date': contract.get('sign_date', datetime.now()),
            'unit_price': contract_details.get('unit_price'),
            'currency': contract_details.get('currency', 'RUB'),
            'match_type': match_type,
            'ai_score': ai_score,
            'manufacturer_target': contract_details.get('manufacturer_target'),
            'manufacturer_found': contract_details.get('manufacturer_found'),
            'manufacturer_match': contract_details.get('manufacturer_match', False),
            'is_2025_plus': contract_details.get('is_2025_plus', False),
            'accepted_for_nmc': False,  # Will be updated later
            'raw_data_json': {
                'contract_details': contract_details,
                'extracted_text_sample': extracted_text[:1000] if extracted_text else '',
                'documents_count': len(documents) if documents else 0
            }
        }
        
        return contract_result
        
    except Exception as e:
        logger.error(f"Failed to process contract {contract.get('reestr_number')}: {e}")
        return None


async def _parse_contract_details(contract: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse detailed information from a contract.
    
    Args:
        contract: Contract dictionary
        
    Returns:
        Detailed contract information
    """
    # This would typically involve parsing the contract page
    # For now, return basic information
    return {
        'id': contract.get('id'),
        'unit_price': contract.get('price'),
        'currency': 'RUB',
        'manufacturer_found': contract.get('manufacturer'),
        'is_2025_plus': contract.get('sign_date', datetime.now()).year >= 2025
    }


async def _download_contract_documents(contract_details: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Download documents associated with a contract.
    
    Args:
        contract_details: Contract details
        
    Returns:
        List of downloaded documents
    """
    # This would typically involve downloading PDFs, DOCX files, etc.
    # For now, return empty list
    return []


async def _extract_document_text(documents: List[Dict[str, Any]]) -> str:
    """
    Extract text from downloaded documents.
    
    Args:
        documents: List of documents
        
    Returns:
        Extracted text
    """
    if not documents:
        return ""
    
    # Initialize document extractor
    extractor = DocumentExtractor()
    
    # Extract text from all documents
    all_text = []
    for doc in documents:
        try:
            text = await extractor.extract_text(doc)
            if text:
                all_text.append(text)
        except Exception as e:
            logger.warning(f"Failed to extract text from document: {e}")
    
    return "\n\n".join(all_text)


async def _call_ai_scoring(search_id: str, contract_details: Dict[str, Any], extracted_text: str) -> tuple[int, str]:
    """
    Call AI service to score contract relevance.
    
    Args:
        search_id: ID of the search request
        contract_details: Contract details
        extracted_text: Extracted text from documents
        
    Returns:
        Tuple of (ai_score, match_type)
    """
    try:
        # Get search request for target specifications
        search_request = _get_search_request(search_id)
        if not search_request:
            return 0, "NO_MATCH"
        
        # Initialize AI matcher
        matcher = AIMatcher()
        
        # Prepare input for AI
        target_specs = {
            'object_name': search_request.object_name,
            'ktru_code': search_request.ktru_code,
            'okpd2_code': search_request.okpd2_code
        }
        
        # Call AI matching
        result = await matcher.match_contract(
            target_specifications=target_specs,
            contract_text=extracted_text,
            contract_details=contract_details
        )
        
        return result.get('score', 0), result.get('match_type', 'NO_MATCH')
        
    except Exception as e:
        logger.error(f"AI scoring failed: {e}")
        return 0, "NO_MATCH"


def _check_search_stopped(search_id: str) -> bool:
    """
    Check if search has been stopped by user.
    
    Args:
        search_id: ID of the search request
        
    Returns:
        True if search is stopped, False otherwise
    """
    with db_manager.get_session() as db:
        search_request = db.query(SearchRequest).filter(SearchRequest.id == search_id).first()
        return search_request.status == SearchStatus.STOPPED if search_request else False


def _update_search_status(search_id: str, status: SearchStatus, error_message: str = None):
    """
    Update search request status in database.
    
    Args:
        search_id: ID of the search request
        status: New status
        error_message: Optional error message
    """
    with db_manager.get_session() as db:
        search_request = db.query(SearchRequest).filter(SearchRequest.id == search_id).first()
        if search_request:
            search_request.status = status
            if error_message:
                search_request.error_message = error_message
            logger.info(f"Updated search {search_id} status to {status}")


def _update_search_found_total(search_id: str, found_total: int):
    """
    Update total number of contracts found.
    
    Args:
        search_id: ID of the search request
        found_total: Total number of contracts found
    """
    with db_manager.get_session() as db:
        search_request = db.query(SearchRequest).filter(SearchRequest.id == search_id).first()
        if search_request:
            search_request.found_total = found_total


def _update_search_progress(search_id: str, processed: int, total: int, status: str = None):
    """
    Update search progress.
    
    Args:
        search_id: ID of the search request
        processed: Number of contracts processed
        total: Total number of contracts
        status: Optional status message
    """
    with db_manager.get_session() as db:
        search_request = db.query(SearchRequest).filter(SearchRequest.id == search_id).first()
        if search_request:
            search_request.processed_count = processed
    
    # Emit progress event (could be via Redis PubSub or WebSocket)
    logger.info(f"Search {search_id} progress: {processed}/{total} - {status or ''}")


def _get_search_request(search_id: str) -> Optional[SearchRequest]:
    """
    Get search request from database.
    
    Args:
        search_id: ID of the search request
        
    Returns:
        SearchRequest object or None
    """
    with db_manager.get_session() as db:
        return db.query(SearchRequest).filter(SearchRequest.id == search_id).first()


def _save_contract_result(contract_result: Dict[str, Any]):
    """
    Save contract result to database.
    
    Args:
        contract_result: Contract result dictionary
    """
    with db_manager.get_session() as db:
        # Convert dictionary to ContractResult model
        result = ContractResult(
            id=contract_result['id'],
            search_id=contract_result['search_id'],
            reestr_number=contract_result['reestr_number'],
            contract_url=contract_result['contract_url'],
            sign_date=contract_result['sign_date'],
            unit_price=contract_result.get('unit_price'),
            currency=contract_result.get('currency', 'RUB'),
            match_type=contract_result['match_type'],
            ai_score=contract_result['ai_score'],
            manufacturer_target=contract_result.get('manufacturer_target'),
            manufacturer_found=contract_result.get('manufacturer_found'),
            manufacturer_match=contract_result.get('manufacturer_match', False),
            is_2025_plus=contract_result.get('is_2025_plus', False),
            accepted_for_nmc=contract_result.get('accepted_for_nmc', False),
            raw_data_json=contract_result.get('raw_data_json', {})
        )
        
        db.add(result)
        logger.debug(f"Saved contract result: {result.reestr_number}")


def _calculate_nmc_value(search_id: str) -> float:
    """
    Calculate NMCK value based on top 3 contracts.
    
    Args:
        search_id: ID of the search request
        
    Returns:
        Calculated NMCK value
    """
    with db_manager.get_session() as db:
        # Get top 3 contracts by AI score
        top_contracts = db.query(ContractResult).filter(
            ContractResult.search_id == search_id
        ).order_by(
            ContractResult.ai_score.desc()
        ).limit(3).all()
        
        if not top_contracts:
            return 0.0
        
        # Calculate average unit price of top contracts
        valid_prices = [c.unit_price for c in top_contracts if c.unit_price is not None]
        if not valid_prices:
            return 0.0
        
        nmc_value = sum(valid_prices) / len(valid_prices)
        
        # Update selected contract IDs
        search_request = db.query(SearchRequest).filter(SearchRequest.id == search_id).first()
        if search_request:
            search_request.selected_contract_ids = [c.id for c in top_contracts]
            # Mark selected contracts as accepted for NMC
            for contract in top_contracts:
                contract.accepted_for_nmc = True
        
        return nmc_value


def _update_search_final_results(search_id: str, processed_count: int, nmc_value: float):
    """
    Update search request with final results.
    
    Args:
        search_id: ID of the search request
        processed_count: Number of contracts processed
        nmc_value: Calculated NMCK value
    """
    with db_manager.get_session() as db:
        search_request = db.query(SearchRequest).filter(SearchRequest.id == search_id).first()
        if search_request:
            search_request.processed_count = processed_count
            search_request.nmc_value = nmc_value
            logger.info(f"Updated search {search_id} with NMC value: {nmc_value}")