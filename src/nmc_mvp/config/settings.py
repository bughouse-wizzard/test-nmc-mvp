import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nmc_mvp")
    
    # Application settings
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # API settings
    API_PREFIX = "/api"
    
    # Search limits
    DEFAULT_CONTRACT_LIMIT = int(os.getenv("DEFAULT_CONTRACT_LIMIT", "30"))
    
    # File storage
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "./uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "16 * 1024 * 1024"))  # 16MB


settings = Settings()