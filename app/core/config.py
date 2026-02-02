"""Application configuration."""
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """Application settings."""
    
    # Database - using SQLite for development
    DATABASE_URL: str = "sqlite:///./nmck.db"
    
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "NMCK Search System"
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()