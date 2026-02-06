"""
Database session management for Celery worker.
Provides database session creation and management for background tasks.
"""
import contextlib
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from ..core.config import settings


class DatabaseManager:
    """Manages database connections and sessions for the worker."""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: Database URL (defaults to settings.DATABASE_URL)
        """
        self.database_url = database_url or settings.DATABASE_URL
        self.engine = None
        self.SessionLocal = None
        self._initialize()
    
    def _initialize(self):
        """Initialize database engine and session factory."""
        try:
            # Check if it's SQLite (which doesn't support connection pooling)
            is_sqlite = self.database_url.startswith('sqlite')
            
            if is_sqlite:
                # SQLite configuration
                self.engine = create_engine(
                    self.database_url,
                    connect_args={"check_same_thread": False},
                    echo=settings.DEBUG,
                )
            else:
                # PostgreSQL/other databases with connection pooling
                self.engine = create_engine(
                    self.database_url,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    pool_recycle=3600,  # Recycle connections after 1 hour
                    echo=settings.DEBUG,
                )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            print(f"Database manager initialized with URL: {self.database_url}")
        except Exception as e:
            print(f"Failed to initialize database manager: {e}")
            raise
    
    @contextlib.contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session with automatic cleanup.
        
        Yields:
            SQLAlchemy Session object
            
        Raises:
            SQLAlchemyError: If session creation fails
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    def get_session_direct(self) -> Session:
        """
        Get a database session without context manager.
        Caller is responsible for closing the session.
        
        Returns:
            SQLAlchemy Session object
        """
        return self.SessionLocal()
    
    def close(self):
        """Close database engine and cleanup resources."""
        if self.engine:
            self.engine.dispose()
            print("Database engine disposed")


# Global database manager instance
db_manager = DatabaseManager()