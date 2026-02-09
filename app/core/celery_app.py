"""
Celery Worker Configuration for NMCK MVP.

Configure Celery with Redis broker, define queues, and implement BaseTask
with database session management.
"""
import os
from celery import Celery, Task
from celery.signals import worker_ready, worker_shutdown
import logging
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine for database connections
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class BaseTask(Task):
    """
    Base Celery task with database session management.
    
    This task class automatically creates and closes a database session
    for each task execution, ensuring proper resource management.
    """
    abstract = True
    
    def __init__(self):
        super().__init__()
        self.db_session = None
    
    def __call__(self, *args, **kwargs):
        """
        Execute task with database session management.
        
        Creates a database session before task execution and closes it
        after completion (even if an exception occurs).
        """
        self.db_session = SessionLocal()
        try:
            logger.debug(f"Starting task {self.name} with database session")
            result = self.run(*args, **kwargs)
            self.db_session.commit()
            return result
        except Exception as e:
            logger.error(f"Task {self.name} failed: {str(e)}")
            if self.db_session:
                self.db_session.rollback()
            raise
        finally:
            if self.db_session:
                self.db_session.close()
                self.db_session = None
                logger.debug(f"Closed database session for task {self.name}")

# Create Celery application with Redis broker and result backend
celery_app = Celery(
    "nmck_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    task_cls=BaseTask,
    include=[
        "app.services.worker.tasks",
        "app.services.worker.search_tasks",
    ]
)

# Configure Celery application
celery_app.conf.update(
    # Serialization settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,  # Results expire after 1 hour
    
    # Timezone settings
    timezone="UTC",
    enable_utc=True,
    
    # Task tracking and monitoring
    task_track_started=True,  # Critical: Track when tasks start
    task_time_limit=settings.TASK_TIME_LIMIT,  # 5 minutes per task
    task_soft_time_limit=settings.TASK_TIME_LIMIT - 30,  # Soft limit 30 seconds before hard limit
    
    # Worker settings
    worker_concurrency=settings.WORKER_CONCURRENCY,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    
    # Reliability settings
    task_acks_late=True,  # Acknowledge tasks after they complete
    task_reject_on_worker_lost=True,  # Reject tasks if worker is lost
    broker_connection_retry_on_startup=True,  # Retry connection on startup
    
    # Queue settings
    task_default_queue="default",
    task_default_exchange="nmck_exchange",
    task_default_routing_key="nmck.default",
    task_default_exchange_type="direct",
    
    # Result backend settings
    result_backend_transport_options={
        "retry_policy": {
            "timeout": 5.0,
            "interval_start": 0,
            "interval_step": 0.2,
            "interval_max": 0.5,
            "max_retries": 3,
        }
    }
)

# Define task queues
celery_app.conf.task_queues = {
    "default": {
        "exchange": "nmck_exchange",
        "exchange_type": "direct",
        "routing_key": "nmck.default",
    },
    "search_queue": {
        "exchange": "nmck_exchange",
        "exchange_type": "direct",
        "routing_key": "nmck.search",
    },
    "processing_queue": {
        "exchange": "nmck_exchange",
        "exchange_type": "direct",
        "routing_key": "nmck.processing",
    },
}

# Configure task routes
celery_app.conf.task_routes = {
    # Search-related tasks go to search queue
    "app.services.worker.search_tasks.*": {
        "queue": "search_queue",
        "routing_key": "nmck.search",
    },
    # Document processing tasks go to processing queue
    "app.services.worker.tasks.process_document": {
        "queue": "processing_queue",
        "routing_key": "nmck.processing",
    },
    "app.services.worker.tasks.extract_text": {
        "queue": "processing_queue",
        "routing_key": "nmck.processing",
    },
    # All other tasks go to default queue
    "app.services.worker.tasks.*": {
        "queue": "default",
        "routing_key": "nmck.default",
    },
}

# Worker lifecycle signals
@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Handler for when worker is ready."""
    logger.info(f"Worker {sender} is ready and waiting for tasks")
    logger.info(f"Connected to Redis at {settings.REDIS_URL}")
    logger.info(f"Database connection configured for {settings.DATABASE_URL}")

@worker_shutdown.connect
def worker_shutdown_handler(sender, **kwargs):
    """Handler for when worker is shutting down."""
    logger.info(f"Worker {sender} is shutting down")

if __name__ == "__main__":
    # Start Celery worker when script is executed directly
    celery_app.start()