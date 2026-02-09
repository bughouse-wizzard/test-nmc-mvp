"""
Redis manager for stop signal checking and inter-process communication.
Provides functionality to check for STOP signals during contract processing.
"""
import redis
from typing import Optional
from ..core.config import settings


class RedisManager:
    """Manages Redis connections and stop signal checking."""
    
    # Key patterns for Redis
    STOP_SIGNAL_KEY = "search:stop:{search_id}"
    PROGRESS_KEY = "search:progress:{search_id}"
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis manager.
        
        Args:
            redis_url: Redis URL (defaults to settings.REDIS_URL)
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Test connection
            self.redis_client.ping()
            print(f"Redis manager initialized with URL: {self.redis_url}")
        except Exception as e:
            print(f"Failed to initialize Redis manager: {e}")
            # Don't raise exception, just set redis_client to None
            # This allows the application to work without Redis (for testing)
            self.redis_client = None
    
    def set_stop_signal(self, search_id: str) -> bool:
        """
        Set a STOP signal for a search.
        
        Args:
            search_id: Search request ID
            
        Returns:
            True if signal was set successfully
        """
        if self.redis_client is None:
            return False
        try:
            key = self.STOP_SIGNAL_KEY.format(search_id=search_id)
            # Set with 1 hour expiration to prevent stale signals
            return self.redis_client.setex(key, 3600, "STOP")
        except Exception as e:
            print(f"Failed to set stop signal for search {search_id}: {e}")
            return False
    
    def check_stop_signal(self, search_id: str) -> bool:
        """
        Check if STOP signal exists for a search.
        
        Args:
            search_id: Search request ID
            
        Returns:
            True if STOP signal exists, False otherwise
        """
        if self.redis_client is None:
            return False
        try:
            key = self.STOP_SIGNAL_KEY.format(search_id=search_id)
            signal = self.redis_client.get(key)
            return signal == "STOP"
        except Exception as e:
            print(f"Failed to check stop signal for search {search_id}: {e}")
            return False
    
    def clear_stop_signal(self, search_id: str) -> bool:
        """
        Clear STOP signal for a search.
        
        Args:
            search_id: Search request ID
            
        Returns:
            True if signal was cleared successfully
        """
        if self.redis_client is None:
            return False
        try:
            key = self.STOP_SIGNAL_KEY.format(search_id=search_id)
            return self.redis_client.delete(key) > 0
        except Exception as e:
            print(f"Failed to clear stop signal for search {search_id}: {e}")
            return False
    
    def update_progress(self, search_id: str, processed: int, total: int, status: str = "") -> bool:
        """
        Update progress information for a search.
        
        Args:
            search_id: Search request ID
            processed: Number of contracts processed
            total: Total number of contracts to process
            status: Current status message
            
        Returns:
            True if progress was updated successfully
        """
        if self.redis_client is None:
            return False
        try:
            key = self.PROGRESS_KEY.format(search_id=search_id)
            progress_data = {
                "processed": processed,
                "total": total,
                "status": status,
                "percentage": (processed / total * 100) if total > 0 else 0
            }
            # Store as hash with 1 hour expiration
            self.redis_client.hset(key, mapping=progress_data)
            self.redis_client.expire(key, 3600)
            return True
        except Exception as e:
            print(f"Failed to update progress for search {search_id}: {e}")
            return False
    
    def get_progress(self, search_id: str) -> Optional[dict]:
        """
        Get progress information for a search.
        
        Args:
            search_id: Search request ID
            
        Returns:
            Dictionary with progress data or None if not found
        """
        if self.redis_client is None:
            return None
        try:
            key = self.PROGRESS_KEY.format(search_id=search_id)
            progress_data = self.redis_client.hgetall(key)
            if progress_data:
                # Convert string values to appropriate types
                return {
                    "processed": int(progress_data.get("processed", 0)),
                    "total": int(progress_data.get("total", 0)),
                    "status": progress_data.get("status", ""),
                    "percentage": float(progress_data.get("percentage", 0))
                }
            return None
        except Exception as e:
            print(f"Failed to get progress for search {search_id}: {e}")
            return None
    
    def clear_progress(self, search_id: str) -> bool:
        """
        Clear progress information for a search.
        
        Args:
            search_id: Search request ID
            
        Returns:
            True if progress was cleared successfully
        """
        if self.redis_client is None:
            return False
        try:
            key = self.PROGRESS_KEY.format(search_id=search_id)
            return self.redis_client.delete(key) > 0
        except Exception as e:
            print(f"Failed to clear progress for search {search_id}: {e}")
            return False
    
    def close(self):
        """Close Redis connection."""
        if self.redis_client:
            self.redis_client.close()
            print("Redis connection closed")


# Global Redis manager instance
redis_manager = RedisManager()