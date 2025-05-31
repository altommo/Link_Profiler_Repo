"""
API Rate Limiter - Provides a generic rate limiting mechanism for external API calls.
File: Link_Profiler/utils/api_rate_limiter.py
"""

import asyncio
import time
import logging
from functools import wraps
from typing import Callable, Any, Dict, Optional

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.monitoring.prometheus_metrics import (
    EXTERNAL_API_CALLS_TOTAL, EXTERNAL_API_CALL_DURATION_SECONDS, EXTERNAL_API_CALL_ERRORS_TOTAL
)

logger = logging.getLogger(__name__)

class APIRateLimiter:
    """
    Manages rate limiting for external API calls based on configured requests per second.
    Uses a per-service/client/endpoint lock to prevent exceeding limits.
    """
    _instances: Dict[str, 'APIRateLimiter'] = {}
    _locks: Dict[str, asyncio.Lock] = {}
    _last_call_time: Dict[str, float] = {}

    def __new__(cls, service_name: str):
        """Ensures a singleton instance per service_name."""
        if service_name not in cls._instances:
            instance = super().__new__(cls)
            instance._service_name = service_name
            cls._instances[service_name] = instance
        return cls._instances[service_name]

    def __init__(self, service_name: str):
        if not hasattr(self, '_initialized'): # Prevent re-initialization for singletons
            self._initialized = True
            self.enabled = config_loader.get("api_rate_limiter.enabled", False)
            self.requests_per_second = config_loader.get("api_rate_limiter.requests_per_second", 1.0)
            self.min_interval = 1.0 / self.requests_per_second if self.requests_per_second > 0 else 0.0
            self.logger = logging.getLogger(f"{__name__}.{service_name}")
            
            if self.enabled:
                self.logger.info(f"API Rate Limiter enabled for '{service_name}' at {self.requests_per_second} req/s.")
            else:
                self.logger.info(f"API Rate Limiter disabled for '{service_name}'.")

    async def _wait_if_needed(self, key: str):
        """Waits if necessary to adhere to the rate limit for a specific key."""
        if not self.enabled:
            return

        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
            self._last_call_time[key] = 0.0

        async with self._locks[key]:
            now = time.monotonic()
            time_since_last_call = now - self._last_call_time[key]

            if time_since_last_call < self.min_interval:
                wait_time = self.min_interval - time_since_last_call
                self.logger.debug(f"Rate limiting '{key}'. Waiting for {wait_time:.2f} seconds.")
                await asyncio.sleep(wait_time)
            
            self._last_call_time[key] = time.monotonic()

def api_rate_limited(service: str, api_client_type: str, endpoint: str):
    """
    Decorator to apply rate limiting and Prometheus metrics to external API calls.
    
    Args:
        service (str): The name of the service (e.g., "domain_api", "backlink_api").
        api_client_type (str): The type of API client (e.g., "real_api", "abstract_api", "gsc_api", "openlinkprofiler_api", "metrics_api").
        endpoint (str): The specific endpoint or method being called (e.g., "availability", "whois", "search").
    """
    rate_limiter = APIRateLimiter(service) # Get singleton instance for the service

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # The first argument of the method is 'self' (the API client instance)
            # We can use its class name for more specific logging if needed, but service/api_client_type are sufficient for metrics.
            
            # Rate limit before making the call
            await rate_limiter._wait_if_needed(f"{service}:{api_client_type}:{endpoint}")

            # Prometheus: Increment total calls counter
            EXTERNAL_API_CALLS_TOTAL.labels(
                service=service,
                api_client_type=api_client_type,
                endpoint=endpoint
            ).inc()

            start_time = time.perf_counter()
            status_code = "unknown" # Default status code for errors

            try:
                result = await func(*args, **kwargs)
                # Assuming successful API calls return a non-error status or data
                # For HTTP-based clients, we might get a status code from the response object
                # For non-HTTP clients (like GSC), we assume success if no exception.
                status_code = "200" # Placeholder for success, refine if actual status code is available
                return result
            except Exception as e:
                # Prometheus: Increment error counter
                # Try to extract status code from HTTPX/AIOHTTP exceptions if possible
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    status_code = str(e.response.status_code)
                elif hasattr(e, 'status_code'): # For openai.APIStatusError
                    status_code = str(e.status_code)
                else:
                    status_code = "500" # Generic error
                
                EXTERNAL_API_CALL_ERRORS_TOTAL.labels(
                    service=service,
                    api_client_type=api_client_type,
                    endpoint=endpoint,
                    status_code=status_code
                ).inc()
                raise # Re-raise the exception
            finally:
                # Prometheus: Observe call duration
                duration = time.perf_counter() - start_time
                EXTERNAL_API_CALL_DURATION_SECONDS.labels(
                    service=service,
                    api_client_type=api_client_type,
                    endpoint=endpoint
                ).observe(duration)
        return wrapper
    return decorator
