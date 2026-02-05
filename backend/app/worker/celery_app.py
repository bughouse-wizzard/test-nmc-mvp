"""
Celery application configuration.
"""
from celery import Celery
from ..core.config import settings

# Create Celery application
celery_app = Celery(
    "nmck_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"]
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
    worker_max_tasks_per_child=100,
    broker_connection_retry_on_startup=True,
)

# Optional: Configure task routes
celery_app.conf.task_routes = {
    "app.worker.tasks.process_search": {"queue": "search"},
    "app.worker.tasks.*": {"queue": "default"},
}