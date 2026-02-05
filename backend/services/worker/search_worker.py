"""
Main search worker for processing contract search and NMCK calculation.
Implements the complete workflow:
1. Receive search_id
2. Execute parser_search_engine
3. Iterate through contracts with STOP signal check
4. Process each contract (parser_contract_details, extract_specs, compare_specs)
5. Update DB and publish progress events
6. Finalize: Select top 3 contracts, calculate NMCK, update SearchRequest status
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import redis
from sqlalchemy.orm import Session
from celery import Task

from backend.app.core.config import settings
from backend.models import (
    Base, SearchRequest, ContractResult, SpecComparisonRow,
    SearchStatus, MatchType, MatchStatus, InputSource
)
from backend.services.parser.search import SearchParser
from backend.services.parser.contract import ContractParser, ContractInfo
from backend.services.ai.client import DeepSeekClient
from backend.services.matcher.engine import MatcherEngine

logger = logging.getLogger(__name__)


@dataclass
class WorkerContext:
    """Context for worker execution."""
    search_id: str
    db_session: Session
    redis_client: redis.Redis
    search_parser: SearchParser
    contract_parser: ContractParser
    ai_client: DeepSeekClient
    matcher_engine: MatcherEngine
    stop_key: str
    progress_channel: str


class SearchWorker:
    """Main worker class for processing search requests."""
    
    def __init__(self, db_session_factory, redis_client=None):
        """
        Initialize search worker.
        
        Args:
            db_session_factory: Factory function to create SQLAlchemy sessions
            redis_client: Redis client instance (optional)
        """
        self.db_session_factory = db_session_factory
        self.redis_client = redis_client or redis.Redis.from_url(settings.REDIS_URL)
        
        # Initialize services
        self.search_parser = SearchParser()
        self.contract_parser = ContractParser()
        self.ai_client = DeepSeekClient()
        self.matcher_engine = MatcherEngine()
    
    def _check_stop_signal(self, redis_client: redis.Redis, stop_key: str) -> bool:
        """
        Check Redis for STOP signal.
        
        Args:
            redis_client: Redis client
            stop_key: Redis key to check for STOP signal
            
        Returns:
            True if STOP signal is present, False otherwise
        """
        try:
            stop_signal = redis_client.get(stop_key)
            return stop_signal == b"STOP"
        except Exception as e:
            logger.error(f"Error checking STOP signal: {e}")
            return False
    
    def _publish_progress(
        self, 
        redis_client: redis.Redis, 
        channel: str, 
        search_id: str,
        progress: Dict[str, Any]
    ):
        """
        Publish progress event via Redis PubSub.
        
        Args:
            redis_client: Redis client
            channel: Redis channel name
            search_id: Search request ID
            progress: Progress data to publish
        """
        try:
            message = {
                "search_id": search_id,
                "timestamp": datetime.utcnow().isoformat(),
                "progress": progress
            }
            redis_client.publish(channel, json.dumps(message))
            logger.debug(f"Published progress for search {search_id}: {progress}")
        except Exception as e:
            logger.error(f"Error publishing progress: {e}")
    
    async def process_search(self, search_id: str) -> Dict[str, Any]:
        """
        Main method to process a search request.
        
        Args:
            search_id: UUID of the search request
            
        Returns:
            Dictionary with processing results
        """
        start_time = time.time()
        
        # Create database session
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session = SessionLocal()
        
        try:
            # Get search request from database
            search_request = db_session.query(SearchRequest).filter(
                SearchRequest.id == search_id
            ).first()
            
            if not search_request:
                raise ValueError(f"Search request {search_id} not found")
            
            # Update search status to RUNNING
            search_request.status = SearchStatus.RUNNING
            db_session.commit()
            
            # Create worker context
            stop_key = f"search_stop:{search_id}"
            progress_channel = f"search_progress:{search_id}"
            
            context = WorkerContext(
                search_id=search_id,
                db_session=db_session,
                redis_client=self.redis_client,
                search_parser=self.search_parser,
                contract_parser=self.contract_parser,
                ai_client=self.ai_client,
                matcher_engine=self.matcher_engine,
                stop_key=stop_key,
                progress_channel=progress_channel
            )
            
            # Publish initial progress
            self._publish_progress(
                self.redis_client,
                progress_channel,
                search_id,
                {
                    "status": "RUNNING",
                    "message": "Starting contract search",
                    "progress": 0,
                    "total_contracts": 0,
                    "processed_contracts": 0
                }
            )
            
            # Step 1: Execute parser_search_engine
            logger.info(f"Starting contract search for {search_id}")
            contracts = await self._execute_search_engine(context, search_request)
            
            # Check STOP signal after search
            if self._check_stop_signal(self.redis_client, stop_key):
                logger.info(f"STOP signal received for search {search_id}")
                search_request.status = SearchStatus.STOPPED
                db_session.commit()
                return {"status": "STOPPED", "message": "Search stopped by user"}
            
            # Update found total
            search_request.found_total = len(contracts)
            db_session.commit()
            
            # Publish search completion progress
            self._publish_progress(
                self.redis_client,
                progress_channel,
                search_id,
                {
                    "status": "SEARCH_COMPLETE",
                    "message": f"Found {len(contracts)} contracts",
                    "progress": 10,
                    "total_contracts": len(contracts),
                    "processed_contracts": 0
                }
            )
            
            # Step 2: Process contracts
            processed_contracts = await self._process_contracts(context, search_request, contracts)
            
            # Step 3: Finalize - select top 3 and calculate NMCK
            await self._finalize_search(context, search_request, processed_contracts)
            
            # Calculate runtime
            runtime_ms = int((time.time() - start_time) * 1000)
            search_request.runtime_ms = runtime_ms
            
            # Update search status to DONE
            search_request.status = SearchStatus.DONE
            db_session.commit()
            
            # Publish final progress
            self._publish_progress(
                self.redis_client,
                progress_channel,
                search_id,
                {
                    "status": "DONE",
                    "message": f"Search completed successfully. NMCK: {search_request.nmc_value}",
                    "progress": 100,
                    "total_contracts": len(contracts),
                    "processed_contracts": len(processed_contracts),
                    "nmc_value": search_request.nmc_value,
                    "runtime_ms": runtime_ms
                }
            )
            
            logger.info(f"Search {search_id} completed successfully in {runtime_ms}ms")
            
            return {
                "status": "DONE",
                "search_id": search_id,
                "total_contracts": len(contracts),
                "processed_contracts": len(processed_contracts),
                "nmc_value": search_request.nmc_value,
                "runtime_ms": runtime_ms
            }
            
        except Exception as e:
            logger.error(f"Error processing search {search_id}: {e}", exc_info=True)
            
            # Update search status to ERROR
            if 'search_request' in locals():
                search_request.status = SearchStatus.ERROR
                search_request.error_message = str(e)
                db_session.commit()
            
            # Publish error progress
            self._publish_progress(
                self.redis_client,
                progress_channel,
                search_id,
                {
                    "status": "ERROR",
                    "message": f"Error processing search: {str(e)}",
                    "progress": 0,
                    "error": str(e)
                }
            )
            
            raise
        finally:
            db_session.close()
    
    async def _execute_search_engine(
        self, 
        context: WorkerContext, 
        search_request: SearchRequest
    ) -> List[Dict]:
        """
        Execute search engine to find contracts.
        
        Args:
            context: Worker context
            search_request: Search request object
            
        Returns:
            List of contract dictionaries
        """
        try:
            # Build search URL
            search_url = context.search_parser.build_search_url(
                ktru_code=search_request.ktru_code,
                customer_region=search_request.customer_region,
                law=search_request.law,
                date_from=search_request.date_from,
                date_to=search_request.date_to,
                execution_statuses=search_request.execution_statuses,
                page_size=min(50, search_request.limit_contracts)
            )
            
            logger.info(f"Search URL: {search_url}")
            
            # In a real implementation, we would make HTTP request and parse results
            # For now, return mock data
            # TODO: Implement actual HTTP request and parsing
            
            # Mock data for testing
            contracts = []
            for i in range(min(10, search_request.limit_contracts)):
                contracts.append({
                    "reestr_number": f"1234567890{i}",
                    "contract_url": f"https://zakupki.gov.ru/epz/contract/contractCard/common-info.html?reestrNumber=1234567890{i}",
                    "sign_date": datetime.now(),
                    "price": 100000 * (i + 1),
                    "currency": "RUB"
                })
            
            return contracts
            
        except Exception as e:
            logger.error(f"Error executing search engine: {e}")
            raise
    
    async def _process_contracts(
        self,
        context: WorkerContext,
        search_request: SearchRequest,
        contracts: List[Dict]
    ) -> List[ContractResult]:
        """
        Process contracts sequentially with STOP signal checking.
        
        Args:
            context: Worker context
            search_request: Search request object
            contracts: List of contract dictionaries
            
        Returns:
            List of processed ContractResult objects
        """
        processed_contracts = []
        total_contracts = len(contracts)
        
        for i, contract_data in enumerate(contracts):
            # Check STOP signal before processing each contract
            if self._check_stop_signal(context.redis_client, context.stop_key):
                logger.info(f"STOP signal received during contract processing for search {context.search_id}")
                search_request.status = SearchStatus.STOPPED
                context.db_session.commit()
                break
            
            # Publish progress
            progress_percent = 10 + int((i / total_contracts) * 80)  # 10-90% for contract processing
            self._publish_progress(
                context.redis_client,
                context.progress_channel,
                context.search_id,
                {
                    "status": "PROCESSING_CONTRACTS",
                    "message": f"Processing contract {i+1} of {total_contracts}",
                    "progress": progress_percent,
                    "current_contract": i + 1,
                    "total_contracts": total_contracts,
                    "processed_contracts": len(processed_contracts)
                }
            )
            
            try:
                # Process single contract
                contract_result = await self._process_single_contract(
                    context, search_request, contract_data, i
                )
                
                if contract_result:
                    processed_contracts.append(contract_result)
                    
                    # Update processed count
                    search_request.processed_count = len(processed_contracts)
                    context.db_session.commit()
                    
                    logger.info(f"Processed contract {i+1}/{total_contracts}: {contract_data.get('reestr_number')}")
                
            except Exception as e:
                logger.error(f"Error processing contract {contract_data.get('reestr_number')}: {e}")
                # Continue with next contract
        
        return processed_contracts
    
    async def _process_single_contract(
        self,
        context: WorkerContext,
        search_request: SearchRequest,
        contract_data: Dict,
        index: int
    ) -> Optional[ContractResult]:
        """
        Process a single contract through the complete pipeline.
        
        Args:
            context: Worker context
            search_request: Search request object
            contract_data: Contract data dictionary
            index: Contract index
            
        Returns:
            ContractResult object or None if processing failed
        """
        try:
            # Step 1: Parse contract details
            contract_info = await self._parse_contract_details(context, contract_data)
            if not contract_info:
                return None
            
            # Step 2: Extract specifications
            specs = await self._extract_specifications(context, contract_info)
            if not specs:
                return None
            
            # Step 3: Compare specifications
            comparison_result = await self._compare_specifications(context, search_request, specs)
            if not comparison_result:
                return None
            
            # Step 4: Create ContractResult and SpecComparisonRow records
            contract_result = self._create_contract_result(
                context, search_request, contract_info, comparison_result
            )
            
            # Step 5: Create spec comparison rows
            self._create_spec_comparison_rows(context, contract_result, comparison_result)
            
            context.db_session.add(contract_result)
            context.db_session.commit()
            
            return contract_result
            
        except Exception as e:
            logger.error(f"Error in contract processing pipeline: {e}")
            return None
    
    async def _parse_contract_details(
        self,
        context: WorkerContext,
        contract_data: Dict
    ) -> Optional[ContractInfo]:
        """
        Parse contract details using ContractParser.
        
        Args:
            context: Worker context
            contract_data: Contract data dictionary
            
        Returns:
            ContractInfo object or None if parsing failed
        """
        try:
            contract_url = contract_data.get("contract_url")
            if not contract_url:
                logger.error("Contract URL not provided")
                return None
            
            # Parse contract details
            contract_info = await context.contract_parser.parse_contract(contract_url)
            return contract_info
            
        except Exception as e:
            logger.error(f"Error parsing contract details: {e}")
            return None
    
    async def _extract_specifications(
        self,
        context: WorkerContext,
        contract_info: ContractInfo
    ) -> Optional[Dict[str, Any]]:
        """
        Extract specifications from contract using AI.
        
        Args:
            context: Worker context
            contract_info: ContractInfo object
            
        Returns:
            Extracted specifications dictionary or None if extraction failed
        """
        try:
            # Prepare text for AI analysis
            text_to_analyze = ""
            
            # Add contract basic info
            text_to_analyze += f"Contract: {contract_info.reestr_number}\n"
            text_to_analyze += f"Customer: {contract_info.customer}\n"
            text_to_analyze += f"Supplier: {contract_info.supplier}\n"
            text_to_analyze += f"Total Price: {contract_info.total_price} {contract_info.currency}\n"
            
            # Add line items
            for item in contract_info.line_items:
                text_to_analyze += f"\nItem: {item.name}\n"
                if item.okpd2_code:
                    text_to_analyze += f"OKPD2: {item.okpd2_code}\n"
                if item.ktru_code:
                    text_to_analyze += f"KTRU: {item.ktru_code}\n"
                if item.unit_price:
                    text_to_analyze += f"Unit Price: {item.unit_price}\n"
                if item.manufacturer:
                    text_to_analyze += f"Manufacturer: {item.manufacturer}\n"
            
            # Extract specifications using AI
            specs = await context.ai_client.extract_specs_from_contract_doc_async(text_to_analyze)
            return specs
            
        except Exception as e:
            logger.error(f"Error extracting specifications: {e}")
            return None
    
    async def _compare_specifications(
        self,
        context: WorkerContext,
        search_request: SearchRequest,
        actual_specs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Compare specifications using AI and heuristic matcher.
        
        Args:
            context: Worker context
            search_request: Search request object
            actual_specs: Actual specifications from contract
            
        Returns:
            Comparison result dictionary or None if comparison failed
        """
        try:
            # Prepare target specifications from search request
            target_specs = {
                "object_name": search_request.object_name,
                "ktru_code": search_request.ktru_code,
                "okpd2_code": search_request.okpd2_code,
                "characteristics": search_request.characteristics_text if hasattr(search_request, 'characteristics_text') else "",
                "manufacturer": search_request.manufacturer if hasattr(search_request, 'manufacturer') else None
            }
            
            # Compare using AI
            ai_comparison = await context.ai_client.compare_specs_and_score_async(
                target_specs, actual_specs
            )
            
            # Additional heuristic comparison
            comparison_result = {
                "ai_score": ai_comparison.get("score", 0),
                "match_type": ai_comparison.get("match_type", "NO_MATCH"),
                "manufacturer_match": self._compare_manufacturers(
                    target_specs.get("manufacturer"),
                    actual_specs.get("manufacturer")
                ),
                "is_2025_plus": contract_info.sign_date.year >= 2025 if 'contract_info' in locals() else False,
                "spec_comparisons": []
            }
            
            # Add detailed spec comparisons
            if "comparisons" in ai_comparison:
                for comp in ai_comparison["comparisons"]:
                    comparison_result["spec_comparisons"].append({
                        "name": comp.get("name"),
                        "target_value": comp.get("target_value"),
                        "actual_value": comp.get("actual_value"),
                        "match_status": comp.get("match_status", "UNKNOWN"),
                        "weight": comp.get("weight", 1)
                    })
            
            return comparison_result
            
        except Exception as e:
            logger.error(f"Error comparing specifications: {e}")
            return None
    
    def _compare_manufacturers(self, target_manufacturer: Optional[str], actual_manufacturer: Optional[str]) -> Optional[bool]:
        """
        Compare manufacturer names.
        
        Args:
            target_manufacturer: Target manufacturer name
            actual_manufacturer: Actual manufacturer name
            
        Returns:
            True if manufacturers match, False if they don't, None if comparison not possible
        """
        if not target_manufacturer or not actual_manufacturer:
            return None
        
        # Simple comparison - in real implementation would use fuzzy matching
        target_lower = target_manufacturer.lower().strip()
        actual_lower = actual_manufacturer.lower().strip()
        
        return target_lower == actual_lower
    
    def _create_contract_result(
        self,
        context: WorkerContext,
        search_request: SearchRequest,
        contract_info: ContractInfo,
        comparison_result: Dict[str, Any]
    ) -> ContractResult:
        """
        Create ContractResult record.
        
        Args:
            context: Worker context
            search_request: Search request object
            contract_info: ContractInfo object
            comparison_result: Comparison result dictionary
            
        Returns:
            ContractResult object
        """
        # Determine match type
        match_type = MatchType.NO_MATCH
        ai_score = comparison_result.get("ai_score", 0)
        
        if ai_score >= 90:
            match_type = MatchType.IDENTICAL
        elif ai_score >= 70:
            match_type = MatchType.HOMOGENEOUS
        
        # Check if contract should be accepted for NMCK calculation
        accepted_for_nmc = (
            match_type in [MatchType.IDENTICAL, MatchType.HOMOGENEOUS] and
            comparison_result.get("manufacturer_match", False) and
            comparison_result.get("is_2025_plus", False)
        )
        
        # Create ContractResult
        contract_result = ContractResult(
            id=str(uuid.uuid4()),
            search_id=search_request.id,
            reestr_number=contract_info.reestr_number,
            contract_url=contract_info.contract_url,
            sign_date=contract_info.sign_date,
            unit_price=contract_info.total_price,  # Using total price as unit price for simplicity
            currency=contract_info.currency,
            match_type=match_type,
            ai_score=int(ai_score),
            manufacturer_target=search_request.manufacturer if hasattr(search_request, 'manufacturer') else None,
            manufacturer_found=contract_info.supplier,  # Using supplier as manufacturer
            manufacturer_match=comparison_result.get("manufacturer_match"),
            is_2025_plus=comparison_result.get("is_2025_plus", False),
            accepted_for_nmc=accepted_for_nmc,
            raw_data_json={
                "contract_info": contract_info.__dict__ if hasattr(contract_info, '__dict__') else {},
                "comparison_result": comparison_result
            }
        )
        
        return contract_result
    
    def _create_spec_comparison_rows(
        self,
        context: WorkerContext,
        contract_result: ContractResult,
        comparison_result: Dict[str, Any]
    ):
        """
        Create SpecComparisonRow records.
        
        Args:
            context: Worker context
            contract_result: ContractResult object
            comparison_result: Comparison result dictionary
        """
        spec_comparisons = comparison_result.get("spec_comparisons", [])
        
        for comp in spec_comparisons:
            spec_row = SpecComparisonRow(
                id=str(uuid.uuid4()),
                contract_result_id=contract_result.id,
                name=comp.get("name", "Unknown"),
                target_value=comp.get("target_value"),
                actual_value=comp.get("actual_value"),
                match_status=MatchStatus(comp.get("match_status", "UNKNOWN")),
                weight=comp.get("weight", 1)
            )
            context.db_session.add(spec_row)
    
    async def _finalize_search(
        self,
        context: WorkerContext,
        search_request: SearchRequest,
        processed_contracts: List[ContractResult]
    ):
        """
        Finalize search: select top 3 contracts and calculate NMCK.
        
        Args:
            context: Worker context
            search_request: Search request object
            processed_contracts: List of processed ContractResult objects
        """
        try:
            # Filter contracts accepted for NMCK calculation
            accepted_contracts = [
                cr for cr in processed_contracts 
                if cr.accepted_for_nmc and cr.unit_price is not None
            ]
            
            if not accepted_contracts:
                logger.warning(f"No contracts accepted for NMCK calculation for search {context.search_id}")
                search_request.nmc_value = None
                search_request.selected_contract_ids = []
                return
            
            # Sort by unit price (ascending)
            accepted_contracts.sort(key=lambda x: x.unit_price)
            
            # Select top 3 contracts
            top_contracts = accepted_contracts[:3]
            
            # Calculate NMCK (average of top 3 prices)
            total_price = sum(cr.unit_price for cr in top_contracts)
            nmc_value = total_price / len(top_contracts)
            
            # Update search request
            search_request.nmc_value = nmc_value
            search_request.selected_contract_ids = [cr.id for cr in top_contracts]
            
            logger.info(f"Calculated NMCK for search {context.search_id}: {nmc_value} from {len(top_contracts)} contracts")
            
        except Exception as e:
            logger.error(f"Error finalizing search {context.search_id}: {e}")
            search_request.nmc_value = None
            search_request.selected_contract_ids = []