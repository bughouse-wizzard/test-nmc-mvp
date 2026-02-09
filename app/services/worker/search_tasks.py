"""
Search-related tasks for Celery worker.
"""
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="search_task")
def search_task(self, query: str):
    """
    Search task for testing search queue.
    
    Args:
        query: Search query
    
    Returns:
        str: Search results message
    """
    logger.info(f"Search task received query: {query}")
    logger.info(f"Task executing in search queue with database session: {hasattr(self, 'db_session')}")
    return f"Search results for: {query}"

@celery_app.task(bind=True, name="process_search_task")
def process_search_task(self, search_id: str):
    """
    Process search task (simulated).
    
    Args:
        search_id: Search ID to process
    
    Returns:
        dict: Processing status
    """
    logger.info(f"Processing search task for ID: {search_id}")
    # Simulate some processing
    import time
    time.sleep(0.1)
    return {
        "search_id": search_id,
        "status": "processed",
        "message": "Search processing completed"
    }