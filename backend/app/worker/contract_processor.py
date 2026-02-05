"""
Contract processing pipeline for background worker.
Integrates ContractParser, AI client, and MatcherEngine to process contracts.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import aiohttp
import httpx

from ..core.config import settings
from ...services.parser.contract import ContractParser, ContractInfo, ContractLineItem
from ...services.ai.client import DeepSeekClient
from ...services.matcher.engine import MatcherEngine, MatchStatus

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of contract processing."""
    contract_result: Any  # Will be ContractResult from models
    spec_comparison_rows: List[Any]  # Will be List[SpecComparisonRow]
    ai_score: int
    match_type: Any  # Will be MatchType enum
    manufacturer_match: Optional[bool]
    unit_price: Optional[float]


class ContractProcessor:
    """Processes individual contracts through the full pipeline."""
    
    def __init__(
        self,
        search_request: Any,  # Will be SearchRequest from models
        ai_client: Optional[DeepSeekClient] = None,
        matcher_engine: Optional[MatcherEngine] = None,
        http_session: Optional[aiohttp.ClientSession] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        """
        Initialize contract processor.
        
        Args:
            search_request: The search request being processed
            ai_client: DeepSeek AI client (will be created if not provided)
            matcher_engine: Matcher engine (will be created if not provided)
            http_session: aiohttp session for HTTP requests
            http_client: httpx client for HTTP requests
        """
        self.search_request = search_request
        self.ai_client = ai_client or DeepSeekClient()
        self.matcher_engine = matcher_engine or MatcherEngine()
        
        # Initialize contract parser
        self.contract_parser = ContractParser(
            base_url=settings.ZAKUPKI_BASE_URL,
            session=http_session,
            http_client=http_client,
            year_threshold=2025
        )
        
        # Extract target specifications from search request
        self.target_specs = self._extract_target_specs()
        
        logger.info(f"ContractProcessor initialized for search: {search_request.id}")
    
    def _extract_target_specs(self) -> Dict[str, Any]:
        """
        Extract target specifications from search request.
        
        Returns:
            Dictionary of target specifications
        """
        # In a real implementation, this would parse the object_name and other fields
        # to extract technical specifications. For now, create a basic structure.
        return {
            "object_name": self.search_request.object_name,
            "ktru_code": self.search_request.ktru_code,
            "okpd2_code": self.search_request.okpd2_code,
            "manufacturer": None,  # Would be extracted from object_name or separate field
            "characteristics": []  # Would be parsed from object_name or requirements text
        }
    
    async def process_contract(
        self, 
        contract_url: str, 
        reestr_number: str,
        sign_date: datetime,
        total_price: Optional[float] = None
    ) -> Optional[ProcessingResult]:
        """
        Process a single contract through the full pipeline.
        
        Args:
            contract_url: URL to the contract
            reestr_number: Registry number of the contract
            sign_date: Sign date of the contract
            total_price: Total price of the contract (optional)
            
        Returns:
            ProcessingResult if successful, None if failed
        """
        try:
            logger.info(f"Processing contract: {reestr_number}")
            
            # Step 1: Parse contract details
            contract_info = await self._parse_contract_details(contract_url)
            if not contract_info:
                logger.warning(f"Failed to parse contract: {reestr_number}")
                return None
            
            # Step 2: Extract specifications from contract
            contract_specs = await self._extract_specifications(contract_info)
            if not contract_specs:
                logger.warning(f"Failed to extract specs from contract: {reestr_number}")
                return None
            
            # Step 3: Compare specifications and calculate score
            comparison_result = await self._compare_specifications(contract_specs)
            if not comparison_result:
                logger.warning(f"Failed to compare specs for contract: {reestr_number}")
                return None
            
            # Step 4: Create database records
            processing_result = self._create_db_records(
                contract_info=contract_info,
                contract_specs=contract_specs,
                comparison_result=comparison_result,
                reestr_number=reestr_number,
                contract_url=contract_url,
                sign_date=sign_date,
                total_price=total_price
            )
            
            logger.info(f"Successfully processed contract: {reestr_number}, "
                       f"AI Score: {processing_result.ai_score}, "
                       f"Match Type: {processing_result.match_type}")
            
            return processing_result
            
        except Exception as e:
            logger.error(f"Error processing contract {reestr_number}: {e}")
            return None
    
    async def _parse_contract_details(self, contract_url: str) -> Optional[ContractInfo]:
        """Parse contract details using ContractParser."""
        try:
            contract_info = await self.contract_parser.parse_contract(contract_url)
            logger.debug(f"Parsed contract details: {contract_info.reestr_number}")
            return contract_info
        except Exception as e:
            logger.error(f"Failed to parse contract details: {e}")
            return None
    
    async def _extract_specifications(self, contract_info: ContractInfo) -> Optional[Dict[str, Any]]:
        """Extract specifications from contract using AI."""
        try:
            # Prepare text for AI analysis
            analysis_text = self._prepare_analysis_text(contract_info)
            
            # Use AI to extract specifications
            if contract_info.printed_form_path:
                # If we have a printed form, read and analyze it
                try:
                    with open(contract_info.printed_form_path, 'r', encoding='utf-8') as f:
                        printed_form_text = f.read()
                    analysis_text += f"\n\nPrinted Form Content:\n{printed_form_text}"
                except Exception as e:
                    logger.warning(f"Failed to read printed form: {e}")
            
            # Call AI client and capture raw response
            contract_specs = await self.ai_client.extract_specs_from_contract_doc_async(
                analysis_text
            )
            
            logger.debug(f"Extracted specifications from contract")
            return contract_specs
            
        except Exception as e:
            logger.error(f"Failed to extract specifications: {e}")
            # Fall back to heuristic extraction from line items
            return self._extract_specs_heuristic(contract_info)
    
    def _prepare_analysis_text(self, contract_info: ContractInfo) -> str:
        """Prepare text for AI analysis from contract info."""
        text_parts = []
        
        # Basic contract info
        text_parts.append(f"Contract: {contract_info.reestr_number}")
        text_parts.append(f"Customer: {contract_info.customer}")
        text_parts.append(f"Supplier: {contract_info.supplier}")
        text_parts.append(f"Sign Date: {contract_info.sign_date}")
        text_parts.append(f"Total Price: {contract_info.total_price} {contract_info.currency}")
        text_parts.append(f"Execution Status: {contract_info.execution_status}")
        
        # Line items
        if contract_info.line_items:
            text_parts.append("\nLine Items:")
            for item in contract_info.line_items:
                item_text = f"  - {item.name}"
                if item.ktru_code:
                    item_text += f" (KTRU: {item.ktru_code})"
                if item.okpd2_code:
                    item_text += f" (OKPD2: {item.okpd2_code})"
                if item.unit_price:
                    item_text += f" - {item.unit_price} per {item.unit}"
                if item.manufacturer:
                    item_text += f" - Manufacturer: {item.manufacturer}"
                text_parts.append(item_text)
        
        return "\n".join(text_parts)
    
    def _extract_specs_heuristic(self, contract_info: ContractInfo) -> Dict[str, Any]:
        """Extract specifications heuristically from contract info."""
        specs = {
            "object_name": contract_info.line_items[0].name if contract_info.line_items else "Unknown",
            "ktru_codes": list(set(item.ktru_code for item in contract_info.line_items if item.ktru_code)),
            "okpd2_codes": list(set(item.okpd2_code for item in contract_info.line_items if item.okpd2_code)),
            "manufacturers": list(set(item.manufacturer for item in contract_info.line_items if item.manufacturer)),
            "units": list(set(item.unit for item in contract_info.line_items if item.unit)),
            "characteristics": []
        }
        
        # Extract characteristics from line item names
        for item in contract_info.line_items:
            if item.name and len(item.name) > 20:  # Assume longer names contain characteristics
                specs["characteristics"].append({
                    "name": "Item Description",
                    "value": item.name
                })
        
        return specs
    
    async def _compare_specifications(
        self, 
        contract_specs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Compare specifications and calculate match score."""
        try:
            # Use AI for comprehensive comparison
            comparison_result = await self.ai_client.compare_specs_and_score_async(
                target_specs=self.target_specs,
                actual_specs=contract_specs
            )
            
            # Enhance with heuristic matching
            comparison_result = self._enhance_with_heuristic_matching(
                comparison_result, 
                contract_specs
            )
            
            logger.debug(f"Compared specifications, score: {comparison_result.get('score', 0)}")
            return comparison_result
            
        except Exception as e:
            logger.error(f"Failed to compare specifications with AI: {e}")
            # Fall back to heuristic matching only
            return self._compare_specs_heuristic(contract_specs)
    
    def _enhance_with_heuristic_matching(
        self, 
        ai_result: Dict[str, Any], 
        contract_specs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance AI comparison result with heuristic matching."""
        enhanced_result = ai_result.copy()
        
        # Add manufacturer check
        target_manufacturer = self.target_specs.get("manufacturer")
        contract_manufacturers = contract_specs.get("manufacturers", [])
        
        if target_manufacturer and contract_manufacturers:
            manufacturer_match = any(
                self.matcher_engine._compare_strings(
                    target_manufacturer.lower(),
                    manufacturer.lower()
                ) > self.matcher_engine.MANUFACTURER_SIMILARITY_THRESHOLD
                for manufacturer in contract_manufacturers
            )
            enhanced_result["manufacturer_match"] = manufacturer_match
        
        return enhanced_result
    
    def _compare_specs_heuristic(self, contract_specs: Dict[str, Any]) -> Dict[str, Any]:
        """Compare specifications using heuristic matching only."""
        # Simple heuristic comparison
        score = 50  # Base score
        
        # Check KTRU code match
        target_ktru = self.target_specs.get("ktru_code")
        contract_ktru_codes = contract_specs.get("ktru_codes", [])
        
        if target_ktru and contract_ktru_codes:
            if target_ktru in contract_ktru_codes:
                score += 30  # KTRU match is important
        
        # Check manufacturer match
        target_manufacturer = self.target_specs.get("manufacturer")
        contract_manufacturers = contract_specs.get("manufacturers", [])
        
        manufacturer_match = False
        if target_manufacturer and contract_manufacturers:
            manufacturer_match = any(
                target_manufacturer.lower() in manufacturer.lower()
                for manufacturer in contract_manufacturers
            )
            if manufacturer_match:
                score += 20
        
        # Determine match type based on score
        match_type = MatchType.IDENTICAL if score >= 80 else MatchType.HOMOGENEOUS
        
        return {
            "score": min(score, 100),
            "match_type": match_type.value,
            "manufacturer_match": manufacturer_match,
            "details": {
                "heuristic_score": score,
                "ktru_match": target_ktru in contract_ktru_codes if target_ktru else False,
                "manufacturer_found": contract_manufacturers[0] if contract_manufacturers else None
            }
        }
    
    def _create_db_records(
        self,
        contract_info: ContractInfo,
        contract_specs: Dict[str, Any],
        comparison_result: Dict[str, Any],
        reestr_number: str,
        contract_url: str,
        sign_date: datetime,
        total_price: Optional[float]
    ) -> ProcessingResult:
        """Create database records from processing results."""
        # Generate IDs
        contract_result_id = str(uuid.uuid4())
        
        # Extract unit price from line items if available
        unit_price = None
        if contract_info.line_items:
            # Use the first line item's unit price, or calculate from total
            first_item = contract_info.line_items[0]
            if first_item.unit_price:
                unit_price = first_item.unit_price
            elif total_price and first_item.quantity:
                unit_price = total_price / first_item.quantity
        
        # Get match type from comparison result
        match_type_str = comparison_result.get("match_type", "NO_MATCH")
        
        # Create clean copies of contract_specs and comparison_result without debug data
        contract_specs_clean = contract_specs.copy() if isinstance(contract_specs, dict) else contract_specs
        comparison_result_clean = comparison_result.copy() if isinstance(comparison_result, dict) else comparison_result
        
        # Remove debug data from clean copies
        if isinstance(contract_specs_clean, dict) and "_debug" in contract_specs_clean:
            contract_specs_clean = {k: v for k, v in contract_specs_clean.items() if k != "_debug"}
        if isinstance(comparison_result_clean, dict) and "_debug" in comparison_result_clean:
            comparison_result_clean = {k: v for k, v in comparison_result_clean.items() if k != "_debug"}
        
        # Create raw data for ContractResult
        raw_data = {
            "contract_info": {
                "reestr_number": contract_info.reestr_number,
                "customer": contract_info.customer,
                "supplier": contract_info.supplier,
                "total_price": contract_info.total_price,
                "currency": contract_info.currency,
                "execution_status": contract_info.execution_status,
                "line_items_count": len(contract_info.line_items),
                "attachments_count": len(contract_info.attachments),
                "has_printed_form": contract_info.printed_form_path is not None
            },
            "contract_specs": contract_specs_clean,
            "comparison_result": comparison_result_clean,
            "debug_data": {
                "parser_html": {
                    "common_info_html_sample": contract_info.raw_html[:5000] if contract_info.raw_html else None,
                    "common_info_html_length": len(contract_info.raw_html) if contract_info.raw_html else 0,
                    "has_printed_form": contract_info.printed_form_path is not None,
                    "printed_form_path": contract_info.printed_form_path
                },
                "ai_extraction_debug": contract_specs.get("_debug") if isinstance(contract_specs, dict) else None,
                "ai_comparison_debug": comparison_result.get("_debug") if isinstance(comparison_result, dict) else None,
                "processing_timestamp": datetime.now().isoformat()
            }
        }
        
        # Create contract result dictionary (will be converted to model in tasks.py)
        contract_result_dict = {
            "id": contract_result_id,
            "search_id": self.search_request.id,
            "reestr_number": reestr_number,
            "contract_url": contract_url,
            "sign_date": sign_date,
            "unit_price": unit_price,
            "currency": contract_info.currency,
            "match_type": match_type_str,
            "ai_score": int(comparison_result.get("score", 0)),
            "manufacturer_target": self.target_specs.get("manufacturer"),
            "manufacturer_found": contract_specs.get("manufacturers", [None])[0],
            "manufacturer_match": comparison_result.get("manufacturer_match"),
            "is_2025_plus": contract_info.sign_date.year >= 2025,
            "accepted_for_nmc": False,  # Will be determined later
            "raw_data_json": raw_data
        }
        
        # Create spec comparison rows
        spec_comparison_rows = []
        details = comparison_result.get("details", {})
        
        # Add key comparison rows
        comparison_fields = [
            ("KTRU Code", self.target_specs.get("ktru_code"), 
             contract_specs.get("ktru_codes", [None])[0], 
             "MATCH" if details.get("ktru_match") else "DIFF"),
            ("Manufacturer", self.target_specs.get("manufacturer"),
             contract_specs.get("manufacturers", [None])[0],
             "MATCH" if comparison_result.get("manufacturer_match") else "DIFF"),
            ("Object Name", self.target_specs.get("object_name"),
             contract_specs.get("object_name"),
             "MATCH" if self._compare_object_names(
                 self.target_specs.get("object_name"),
                 contract_specs.get("object_name")
             ) else "DIFF"),
        ]
        
        for name, target_value, actual_value, match_status in comparison_fields:
            if target_value or actual_value:
                row_dict = {
                    "id": str(uuid.uuid4()),
                    "contract_result_id": contract_result_id,
                    "name": name,
                    "target_value": str(target_value) if target_value else None,
                    "actual_value": str(actual_value) if actual_value else None,
                    "match_status": match_status,
                    "weight": 2 if name == "KTRU Code" else 1
                }
                spec_comparison_rows.append(row_dict)
        
        return ProcessingResult(
            contract_result=contract_result_dict,
            spec_comparison_rows=spec_comparison_rows,
            ai_score=int(comparison_result.get("score", 0)),
            match_type=match_type_str,
            manufacturer_match=comparison_result.get("manufacturer_match"),
            unit_price=unit_price
        )
    
    def _compare_object_names(self, target_name: Optional[str], actual_name: Optional[str]) -> bool:
        """Compare object names using fuzzy matching."""
        if not target_name or not actual_name:
            return False
        
        similarity = self.matcher_engine._compare_strings(
            target_name.lower(),
            actual_name.lower()
        )
        
        return similarity > self.matcher_engine.STRING_SIMILARITY_THRESHOLD