"""
API Cache - Provides caching functionality for external API calls using Redis.
File: Link_Profiler/utils/api_cache.py
"""

import json
import logging
import redis.asyncio as redis
from typing import Any, Dict, Optional
from functools import wraps
import hashlib

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.monitoring.prometheus_metrics import (
    API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL
)

logger = logging.getLogger(__name__)

class APICache:
    """
    A singleton class to manage caching of external API responses using Redis.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APICache, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".APICache")
        self.enabled = config_loader.get("api_cache.enabled", False)
        self.cache_ttl = config_loader.get("api_cache.ttl", 3600) # Default 1 hour
        self.redis_client: Optional[redis.Redis] = None

        if self.enabled:
            try:
                redis_url = config_loader.get("redis.url")
                if not redis_url:
                    raise ValueError("Redis URL not configured for API Cache.")
                self.redis_client = redis.Redis(connection_pool=redis.ConnectionPool.from_url(redis_url))
                self.logger.info(f"API Cache initialized and enabled with TTL: {self.cache_ttl}s.")
            except Exception as e:
                self.logger.error(f"Failed to initialize API Cache due to Redis connection error: {e}. Disabling cache.", exc_info=True)
                self.enabled = False
        else:
            self.logger.info("API Cache is disabled by configuration.")

    async def get(self, key: str, service: str, endpoint: str) -> Optional[Any]:
        """
        Retrieves a value from the cache.
        """
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            cached_data = await self.redis_client.get(key)
            if cached_data:
                API_CACHE_HITS_TOTAL.labels(service=service, endpoint=endpoint).inc()
                return json.loads(cached_data)
            API_CACHE_MISSES_TOTAL.labels(service=service, endpoint=endpoint).inc()
            return None
        except Exception as e:
            self.logger.error(f"Error getting data from cache for key '{key}': {e}", exc_info=True)
            API_CACHE_ERRORS_TOTAL.labels(service=service, endpoint=endpoint, error_type="get_error").inc()
            return None

    async def set(self, key: str, value: Any, service: str, endpoint: str, ttl: Optional[int] = None):
        """
        Stores a value in the cache.
        """
        if not self.enabled or not self.redis_client:
            return
        
        try:
            ttl_to_use = ttl if ttl is not None else self.cache_ttl
            await self.redis_client.setex(key, ttl_to_use, json.dumps(value))
            API_CACHE_SET_TOTAL.labels(service=service, endpoint=endpoint).inc()
        except Exception as e:
            self.logger.error(f"Error setting data in cache for key '{key}': {e}", exc_info=True)
            API_CACHE_ERRORS_TOTAL.labels(service=service, endpoint=endpoint, error_type="set_error").inc()

    async def close(self):
        """
        Closes the Redis client connection.
        """
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("API Cache Redis client closed.")

# Create a singleton instance
api_cache = APICache()

def cached_api_call(service: str, endpoint: str, ttl: Optional[int] = None):
    """
    Decorator to cache the results of an asynchronous API call.
    The cache key is generated from the function name and its arguments.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not api_cache.enabled:
                return await func(*args, **kwargs)

            # Generate a cache key based on function name and arguments
            # Exclude 'self' from args for method calls
            func_args = args[1:] if args and hasattr(args[0], func.__name__) else args
            cache_key_parts = [func.__name__] + [str(arg) for arg in func_args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = hashlib.md5(":".join(cache_key_parts).encode('utf-8')).hexdigest()
            
            # Try to get from cache
            cached_result = await api_cache.get(cache_key, service, endpoint)
            if cached_result is not None:
                logger.debug(f"Cache hit for {service}:{endpoint} with key {cache_key}")
                return cached_result

            logger.debug(f"Cache miss for {service}:{endpoint} with key {cache_key}. Calling API.")
            # Call the original function
            result = await func(*args, **kwargs)

            # Store result in cache
            if result is not None: # Only cache if result is not None
                await api_cache.set(cache_key, result, service, endpoint, ttl)
            
            return result
        return wrapper
    return decorator
