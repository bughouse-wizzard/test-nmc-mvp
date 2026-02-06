"""
Finalization logic for search processing.
Handles selecting top contracts, calculating NMCK, and updating search status.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SearchFinalizer:
    """Handles finalization of search processing."""
    
    def __init__(self):
        """Initialize search finalizer."""
        pass
    
    def select_top_contracts(
        self, 
        contract_results: List[Dict[str, Any]], 
        count: int = 3
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Select top contracts for NMCK calculation.
        
        Priority order:
        1. Match type (IDENTICAL > HOMOGENEOUS > NO_MATCH)
        2. AI score (higher is better)
        3. Manufacturer match (True > False > None)
        4. Contract year (newer is better)
        
        Args:
            contract_results: List of contract result dictionaries
            count: Number of contracts to select (default: 3)
            
        Returns:
            Tuple of (selected_contracts, selected_contract_ids)
        """
        if not contract_results:
            return [], []
        
        # Define match type priority
        match_type_priority = {
            "IDENTICAL": 3,
            "HOMOGENEOUS": 2,
            "NO_MATCH": 1
        }
        
        # Score each contract
        scored_contracts = []
        for contract in contract_results:
            score = self._calculate_selection_score(contract, match_type_priority)
            scored_contracts.append((score, contract))
        
        # Sort by score (descending)
        scored_contracts.sort(key=lambda x: x[0], reverse=True)
        
        # Select top contracts
        selected = [contract for _, contract in scored_contracts[:count]]
        selected_ids = [contract["id"] for contract in selected]
        
        logger.info(f"Selected {len(selected)} contracts out of {len(contract_results)}")
        for i, contract in enumerate(selected):
            logger.debug(f"  {i+1}. {contract['reestr_number']} - "
                        f"Match: {contract['match_type']}, "
                        f"Score: {contract['ai_score']}, "
                        f"Price: {contract.get('unit_price')}")
        
        return selected, selected_ids
    
    def _calculate_selection_score(
        self, 
        contract: Dict[str, Any], 
        match_type_priority: Dict[str, int]
    ) -> float:
        """
        Calculate selection score for a contract.
        
        Args:
            contract: Contract result dictionary
            match_type_priority: Priority mapping for match types
            
        Returns:
            Selection score (higher is better)
        """
        score = 0.0
        
        # Match type score (0-30 points)
        match_type = contract.get("match_type", "NO_MATCH")
        match_score = match_type_priority.get(match_type, 1)
        score += match_score * 10  # 10, 20, or 30 points
        
        # AI score (0-50 points)
        ai_score = contract.get("ai_score", 0)
        score += ai_score * 0.5  # Convert 0-100 to 0-50 points
        
        # Manufacturer match (0-10 points)
        manufacturer_match = contract.get("manufacturer_match")
        if manufacturer_match is True:
            score += 10
        elif manufacturer_match is False:
            score += 0  # No points for mismatch
        # None gets 0 points
        
        # Contract year bonus (0-10 points)
        sign_date = contract.get("sign_date")
        if isinstance(sign_date, datetime):
            year = sign_date.year
            current_year = datetime.now().year
            if year >= current_year - 1:  # Last year or current year
                score += 10
            elif year >= current_year - 3:  # Within 3 years
                score += 5
        
        # Unit price availability bonus (0-5 points)
        if contract.get("unit_price") is not None:
            score += 5
        
        return score
    
    def calculate_nmck(self, selected_contracts: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate NMCK (Initial Maximum Contract Price) from selected contracts.
        
        Rules:
        1. Use unit_price if available
        2. If no unit_price, try to calculate from total_price and quantity
        3. Take average of available prices
        4. Handle outliers (remove prices > 2x median or < 0.5x median)
        
        Args:
            selected_contracts: List of selected contract dictionaries
            
        Returns:
            Calculated NMCK value or None if cannot calculate
        """
        if not selected_contracts:
            return None
        
        # Extract unit prices
        unit_prices = []
        for contract in selected_contracts:
            unit_price = contract.get("unit_price")
            if unit_price is not None and unit_price > 0:
                unit_prices.append(unit_price)
        
        if not unit_prices:
            logger.warning("No valid unit prices found in selected contracts")
            return None
        
        # Remove outliers using IQR method
        cleaned_prices = self._remove_outliers(unit_prices)
        
        if not cleaned_prices:
            logger.warning("All prices were outliers, using original prices")
            cleaned_prices = unit_prices
        
        # Calculate average
        nmck_value = sum(cleaned_prices) / len(cleaned_prices)
        
        logger.info(f"Calculated NMCK: {nmck_value:.2f} from {len(cleaned_prices)} prices "
                   f"(original: {len(unit_prices)}, removed outliers: {len(unit_prices) - len(cleaned_prices)})")
        
        return nmck_value
    
    def _remove_outliers(self, prices: List[float]) -> List[float]:
        """
        Remove outliers from price list using IQR method.
        
        Args:
            prices: List of prices
            
        Returns:
            List of prices with outliers removed
        """
        if len(prices) < 3:
            return prices  # Not enough data to detect outliers
        
        # Sort prices
        sorted_prices = sorted(prices)
        
        # Calculate quartiles
        n = len(sorted_prices)
        q1_index = n // 4
        q3_index = (3 * n) // 4
        
        q1 = sorted_prices[q1_index]
        q3 = sorted_prices[q3_index]
        
        # Calculate IQR
        iqr = q3 - q1
        
        # Define outlier bounds
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        # Filter outliers
        filtered_prices = [p for p in prices if lower_bound <= p <= upper_bound]
        
        return filtered_prices
    
    def prepare_final_update(
        self,
        search_id: str,
        total_found: int,
        total_processed: int,
        selected_contract_ids: List[str],
        nmck_value: Optional[float],
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare final update data for SearchRequest.
        
        Args:
            search_id: Search request ID
            total_found: Total number of contracts found
            total_processed: Total number of contracts processed
            selected_contract_ids: IDs of selected contracts
            nmck_value: Calculated NMCK value
            error_message: Error message if any
            
        Returns:
            Dictionary with update data
        """
        update_data = {
            "found_total": total_found,
            "processed_count": total_processed,
            "selected_contract_ids": selected_contract_ids,
            "nmc_value": nmck_value,
            "runtime_ms": None,  # Will be calculated in tasks.py
            "error_message": error_message
        }
        
        # Determine final status
        if error_message:
            update_data["status"] = "ERROR"
        elif total_processed == 0:
            update_data["status"] = "ERROR"
            update_data["error_message"] = "No contracts were processed"
        else:
            update_data["status"] = "DONE"
        
        logger.info(f"Prepared final update for search {search_id}: "
                   f"status={update_data['status']}, "
                   f"processed={total_processed}, "
                   f"nmck={nmck_value}")
        
        return update_data
    
    def update_contracts_for_nmc(
        self,
        contract_results: List[Dict[str, Any]],
        selected_contract_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Update contracts to mark which are accepted for NMCK calculation.
        
        Args:
            contract_results: List of contract result dictionaries
            selected_contract_ids: IDs of contracts selected for NMCK
            
        Returns:
            Updated contract results
        """
        updated_contracts = []
        
        for contract in contract_results:
            contract_id = contract.get("id")
            is_selected = contract_id in selected_contract_ids if contract_id else False
            
            # Create updated contract
            updated_contract = contract.copy()
            updated_contract["accepted_for_nmc"] = is_selected
            
            updated_contracts.append(updated_contract)
        
        logger.info(f"Marked {len(selected_contract_ids)} contracts as accepted for NMCK")
        
        return updated_contracts