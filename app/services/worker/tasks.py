"""
Test tasks for Celery worker verification.
"""
import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="test_task")
def test_task(self, message: str):
    """
    Test task to verify Celery worker is working.
    
    Args:
        message: Test message to log
    
    Returns:
        str: Echo of the input message
    """
    logger.info(f"Test task received message: {message}")
    logger.info(f"Database session available: {hasattr(self, 'db_session')}")
    if hasattr(self, 'db_session') and self.db_session:
        logger.info(f"Database session: {self.db_session}")
    return f"Echo: {message}"

@celery_app.task(bind=True, name="add_numbers")
def add_numbers(self, a: int, b: int):
    """
    Simple addition task for testing.
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        int: Sum of a and b
    """
    logger.info(f"Adding {a} + {b}")
    result = a + b
    logger.info(f"Result: {result}")
    return result