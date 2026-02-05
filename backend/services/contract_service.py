"""
Contract Service for integrating parser with search functionality.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.services.parser.contract import ContractParser

logger = logging.getLogger(__name__)


class ContractService:
    """Service for contract processing and integration with parser."""
    
    def __init__(self):
        """Initialize contract service."""
        self.parser = ContractParser()
    
    async def process_contract(self, contract_url: str) -> Dict[str, Any]:
        """
        Process a single contract using the parser.
        
        Args:
            contract_url: URL to the contract card
            
        Returns:
            Processed contract data
        """
        logger.info(f"Processing contract: {contract_url}")
        
        try:
            # Parse contract using the parser
            parsed_data = await self.parser.parse_contract(contract_url)
            
            # Extract key information for search results
            processed_data = self._extract_key_data(parsed_data)
            
            # Add processing metadata
            processed_data.update({
                "processed_at": datetime.utcnow().isoformat(),
                "processing_success": True,
                "parser_version": "1.0.0"
            })
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Failed to process contract {contract_url}: {e}")
            return {
                "contract_url": contract_url,
                "processing_success": False,
                "error": str(e),
                "processed_at": datetime.utcnow().isoformat()
            }
    
    def _extract_key_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key data from parsed contract for search results.
        
        Args:
            parsed_data: Full parsed contract data
            
        Returns:
            Extracted key data
        """
        common_info = parsed_data.get("common_info", {})
        payments_data = parsed_data.get("payments_data", {})
        unit_prices = parsed_data.get("unit_prices", [])
        
        # Extract basic contract info
        key_data = {
            "reestr_number": parsed_data.get("reestr_number", ""),
            "contract_url": parsed_data.get("contract_url", ""),
            "contract_year": parsed_data.get("contract_year", datetime.now().year),
            "is_2025_plus": parsed_data.get("is_2025_plus", False),
            
            # From common info
            "contract_number": common_info.get("contract_number", ""),
            "sign_date": common_info.get("sign_date", ""),
            "customer": common_info.get("customer", ""),
            "supplier": common_info.get("supplier", ""),
            "contract_price": common_info.get("contract_price", ""),
            "currency": common_info.get("currency", "RUB"),
            "status": common_info.get("status", ""),
            
            # From payments data
            "specification_count": len(payments_data.get("specification", [])),
            "line_items_count": len(payments_data.get("line_items", [])),
            
            # Attachments
            "attachments_count": len(parsed_data.get("attachments", [])),
            "has_printed_form": any(
                att.get("type") == "printed_form" 
                for att in parsed_data.get("attachments", [])
            ),
            
            # Unit prices
            "unit_prices_count": len(unit_prices),
            "unit_prices": unit_prices,
            
            # Raw data references
            "raw_common_info": common_info,
            "raw_payments_data": payments_data,
            "raw_attachments": parsed_data.get("attachments", []),
            "printed_form_data": parsed_data.get("printed_form_data")
        }
        
        # Calculate average unit price if available
        if unit_prices:
            valid_prices = [price.get("unit_price") for price in unit_prices 
                          if price.get("unit_price") is not None]
            if valid_prices:
                key_data["average_unit_price"] = sum(valid_prices) / len(valid_prices)
                key_data["min_unit_price"] = min(valid_prices)
                key_data["max_unit_price"] = max(valid_prices)
        
        return key_data
    
    async def process_multiple_contracts(self, contract_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Process multiple contracts concurrently.
        
        Args:
            contract_urls: List of contract URLs
            
        Returns:
            List of processed contract data
        """
        logger.info(f"Processing {len(contract_urls)} contracts")
        
        # Process contracts concurrently
        tasks = [self.process_contract(url) for url in contract_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing contract {contract_urls[i]}: {result}")
                processed_results.append({
                    "contract_url": contract_urls[i],
                    "processing_success": False,
                    "error": str(result),
                    "processed_at": datetime.utcnow().isoformat()
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    def filter_contracts_by_year(self, contracts: List[Dict[str, Any]], min_year: int = None, max_year: int = None) -> List[Dict[str, Any]]:
        """
        Filter contracts by year.
        
        Args:
            contracts: List of processed contract data
            min_year: Minimum contract year (inclusive)
            max_year: Maximum contract year (inclusive)
            
        Returns:
            Filtered contracts
        """
        filtered = []
        
        for contract in contracts:
            if not contract.get("processing_success", False):
                continue
                
            contract_year = contract.get("contract_year")
            if contract_year is None:
                continue
                
            if min_year is not None and contract_year < min_year:
                continue
            if max_year is not None and contract_year > max_year:
                continue
                
            filtered.append(contract)
        
        return filtered
    
    def extract_specification_data(self, contract: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract specification data from contract.
        
        Args:
            contract: Processed contract data
            
        Returns:
            List of specification items
        """
        if not contract.get("processing_success", False):
            return []
        
        payments_data = contract.get("raw_payments_data", {})
        return payments_data.get("specification", [])
    
    def extract_line_items_data(self, contract: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract line items data from contract.
        
        Args:
            contract: Processed contract data
            
        Returns:
            List of line items
        """
        if not contract.get("processing_success", False):
            return []
        
        payments_data = contract.get("raw_payments_data", {})
        return payments_data.get("line_items", [])
    
    def get_contract_summary(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get summary of contract data.
        
        Args:
            contract: Processed contract data
            
        Returns:
            Contract summary
        """
        if not contract.get("processing_success", False):
            return {"error": "Contract processing failed"}
        
        return {
            "reestr_number": contract.get("reestr_number"),
            "contract_number": contract.get("contract_number"),
            "sign_date": contract.get("sign_date"),
            "customer": contract.get("customer"),
            "supplier": contract.get("supplier"),
            "contract_price": contract.get("contract_price"),
            "currency": contract.get("currency"),
            "contract_year": contract.get("contract_year"),
            "is_2025_plus": contract.get("is_2025_plus"),
            "specification_count": contract.get("specification_count", 0),
            "line_items_count": contract.get("line_items_count", 0),
            "attachments_count": contract.get("attachments_count", 0),
            "has_printed_form": contract.get("has_printed_form", False),
            "unit_prices_count": contract.get("unit_prices_count", 0),
            "average_unit_price": contract.get("average_unit_price"),
            "processing_success": True
        }