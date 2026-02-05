"""
Celery tasks for background processing.
"""
import asyncio
import logging
from typing import Dict, Any

from celery import Task
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.services.worker.search_worker import SearchWorker

logger = logging.getLogger(__name__)

# Create database engine and session factory
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class SearchTask(Task):
    """Custom task class for search processing."""
    
    def __init__(self):
        super().__init__()
        self.search_worker = None
    
    def initialize(self):
        """Initialize the search worker."""
        if self.search_worker is None:
            self.search_worker = SearchWorker(
                db_session_factory=SessionLocal
            )
            logger.info("SearchWorker initialized")
    
    def run(self, search_id: str) -> Dict[str, Any]:
        """
        Process a search request.
        
        Args:
            search_id: UUID of the search request
            
        Returns:
            Dictionary with processing results
        """
        self.initialize()
        
        try:
            # Run async function in sync context
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create new event loop if none exists
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async process_search method
        result = loop.run_until_complete(
            self.search_worker.process_search(search_id)
        )
        
        return result


# Create Celery task instance
process_search_task = SearchTask()