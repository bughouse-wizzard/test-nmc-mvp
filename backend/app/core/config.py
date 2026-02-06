"""
Application configuration settings.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "nmck-calculator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@db:5432/nmck_db"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "NMCK Calculation System"
    
    # CORS
    BACKEND_CORS_ORIGINS: list = ["*"]
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # External APIs
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # Parsing settings
    ZAKUPKI_BASE_URL: str = "https://zakupki.gov.ru"
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    CRAWL_DELAY: int = 60  # seconds between requests
    
    # Worker settings
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "2"))
    TASK_TIME_LIMIT: int = 300  # 5 minutes per task
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()