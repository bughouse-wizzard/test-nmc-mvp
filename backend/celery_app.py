"""
Celery application configuration for background task processing.
"""
import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery application
celery_app = Celery(
    "nmck_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "backend.services.worker.tasks",
        "backend.services.worker.search_worker",
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.TASK_TIME_LIMIT,
    worker_concurrency=settings.WORKER_CONCURRENCY,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)

# Optional: Configure task routes
celery_app.conf.task_routes = {
    "backend.services.worker.search_worker.process_search_task": {
        "queue": "search_queue"
    },
    "backend.services.worker.tasks.*": {
        "queue": "default"
    }
}

@worker_ready.connect
def worker_ready_handler(sender, **kwargs):
    """Handler for when worker is ready."""
    logger.info(f"Worker {sender} is ready and waiting for tasks")

@worker_shutdown.connect
def worker_shutdown_handler(sender, **kwargs):
    """Handler for when worker is shutting down."""
    logger.info(f"Worker {sender} is shutting down")

if __name__ == "__main__":
    celery_app.start()