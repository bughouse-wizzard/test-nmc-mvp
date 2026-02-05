"""
Event channel for publishing and subscribing to search events.
Supports both Redis and in-memory implementations.
"""
import asyncio
import json
from typing import Dict, Set, AsyncGenerator, Optional, Any
from uuid import UUID
import redis.asyncio as redis
from .config import settings
from .events import Event


class EventChannel:
    """Event channel for publishing and subscribing to search events."""
    
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._in_memory_subscribers: Dict[UUID, Set[asyncio.Queue]] = {}
        self._use_redis = True  # Default to Redis if available
        
    async def initialize(self):
        """Initialize the event channel."""
        try:
            self._redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self._redis_client.ping()
            print("Event channel: Using Redis for event distribution")
        except Exception as e:
            print(f"Event channel: Redis not available, falling back to in-memory: {e}")
            self._use_redis = False
            self._redis_client = None
    
    async def publish(self, search_id: UUID, event: Event):
        """
        Publish an event for a specific search.
        
        Args:
            search_id: ID of the search
            event: Event to publish
        """
        event_data = event.model_dump_json()
        
        if self._use_redis and self._redis_client:
            # Publish to Redis channel
            channel_name = f"search:{search_id}:events"
            await self._redis_client.publish(channel_name, event_data)
        else:
            # Publish to in-memory subscribers
            await self._publish_in_memory(search_id, event_data)
    
    async def _publish_in_memory(self, search_id: UUID, event_data: str):
        """Publish event to in-memory subscribers."""
        if search_id in self._in_memory_subscribers:
            for queue in self._in_memory_subscribers[search_id].copy():
                try:
                    await queue.put(event_data)
                except Exception as e:
                    print(f"Error publishing to in-memory queue: {e}")
                    # Remove broken queue
                    self._in_memory_subscribers[search_id].discard(queue)
    
    async def subscribe(self, search_id: UUID) -> AsyncGenerator[str, None]:
        """
        Subscribe to events for a specific search.
        
        Args:
            search_id: ID of the search to subscribe to
            
        Yields:
            JSON string of events
        """
        if self._use_redis and self._redis_client:
            async for event in self._subscribe_redis(search_id):
                yield event
        else:
            async for event in self._subscribe_in_memory(search_id):
                yield event
    
    async def _subscribe_redis(self, search_id: UUID) -> AsyncGenerator[str, None]:
        """Subscribe to Redis channel."""
        channel_name = f"search:{search_id}:events"
        pubsub = self._redis_client.pubsub()
        
        try:
            await pubsub.subscribe(channel_name)
            
            # Wait for subscription confirmation
            async for message in pubsub.listen():
                if message["type"] == "subscribe":
                    continue
                
                if message["type"] == "message":
                    yield message["data"]
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
    
    async def _subscribe_in_memory(self, search_id: UUID) -> AsyncGenerator[str, None]:
        """Subscribe to in-memory events."""
        # Create a queue for this subscriber
        queue = asyncio.Queue()
        
        # Register the queue
        if search_id not in self._in_memory_subscribers:
            self._in_memory_subscribers[search_id] = set()
        self._in_memory_subscribers[search_id].add(queue)
        
        try:
            # Yield events from the queue
            while True:
                event_data = await queue.get()
                yield event_data
        finally:
            # Clean up when done
            if search_id in self._in_memory_subscribers:
                self._in_memory_subscribers[search_id].discard(queue)
                if not self._in_memory_subscribers[search_id]:
                    del self._in_memory_subscribers[search_id]
    
    async def cleanup(self, search_id: UUID):
        """Clean up subscribers for a search."""
        if search_id in self._in_memory_subscribers:
            # Notify all subscribers that the search is done
            done_event = {
                "type": "done",
                "search_id": str(search_id),
                "message": "Search completed"
            }
            await self._publish_in_memory(search_id, json.dumps(done_event))
            
            # Clear subscribers
            del self._in_memory_subscribers[search_id]
    
    async def close(self):
        """Close the event channel."""
        if self._redis_client:
            await self._redis_client.close()


# Global event channel instance
event_channel = EventChannel()