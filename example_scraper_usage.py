"""
Example usage of ZakupkiSearchScraper.

This script demonstrates how to use the scraper to search for contracts
on zakupki.gov.ru with the required parameters:
- 44-FZ
- Status=Executed
- Region=SZFO
- Date=3 years
- KTRU code
"""

import asyncio
import logging
from app.services.scraper import create_scraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Example usage of the scraper."""
    
    # Example KTRU code (replace with actual code)
    ktru_code = "31.20.11.110"  # Example KTRU code
    
    # Create scraper instance
    scraper = await create_scraper(base_delay=3.0)  # 3 second delay for robots.txt compliance
    
    try:
        logger.info(f"Searching for contracts with KTRU code: {ktru_code}")
        logger.info("Parameters: 44-FZ, Status=Executed, Region=SZFO, Last 3 years")
        
        # Search for contracts
        total_found, contracts = await scraper.search_contracts(
            ktru_code=ktru_code,
            region="СЗФО",
            execution_statuses=["Исполнение завершено", "Исполнение прекращено"],
            max_pages=1,  # Only first page for example
        )
        
        logger.info(f"Total contracts found: {total_found}")
        logger.info(f"Contracts retrieved: {len(contracts)}")
        
        # Display contract details
        for i, contract in enumerate(contracts[:5], 1):  # Show first 5 contracts
            logger.info(f"\nContract {i}:")
            logger.info(f"  Reestr Number: {contract['reestr_number']}")
            logger.info(f"  Date: {contract['date']}")
            logger.info(f"  Price: {contract['price']} {contract['currency']}")
            logger.info(f"  Link: {contract['link']}")
        
        if len(contracts) > 5:
            logger.info(f"\n... and {len(contracts) - 5} more contracts")
            
    except Exception as e:
        logger.error(f"Error during search: {e}")
        
    finally:
        # Close the scraper
        await scraper.close()
        logger.info("Scraper closed")


if __name__ == "__main__":
    asyncio.run(main())