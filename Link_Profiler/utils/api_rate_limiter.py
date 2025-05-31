"""
API Rate Limiter - Provides a generic rate limiting mechanism for external API calls.
File: Link_Profiler/utils/api_rate_limiter.py
"""

import asyncio
import time
import logging
from functools import wraps
from typing import Callable, Any, Dict, Optional
import aiohttp # New: Import aiohttp
import openai # New: Import openai

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.monitoring.prometheus_metrics import (
    EXTERNAL_API_CALLS_TOTAL, EXTERNAL_API_CALL_DURATION_SECONDS, EXTERNAL_API_CALL_ERRORS_TOTAL,
    API_RATE_LIMITER_THROTTLES_TOTAL, EXTERNAL_API_CALL_RETRIES_TOTAL # New: Import retry metric
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
            self.max_retries = config_loader.get("api_rate_limiter.max_retries", 3) # New: Max retries
            self.retry_backoff_factor = config_loader.get("api_rate_limiter.retry_backoff_factor", 0.5) # New: Backoff factor
            self.logger = logging.getLogger(f"{__name__}.{service_name}")
            
            if self.enabled:
                self.logger.info(f"API Rate Limiter enabled for '{service_name}' at {self.requests_per_second} req/s with {self.max_retries} retries.")
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
                API_RATE_LIMITER_THROTTLES_TOTAL.labels(
                    service=self._service_name,
                    api_client_type=key.split(':')[1], # Extract from key
                    endpoint=key.split(':')[2] # Extract from key
                ).inc()
                await asyncio.sleep(wait_time)
            
            self._last_call_time[key] = time.monotonic()

def api_rate_limited(service: str, api_client_type: str, endpoint: str):
    """
    Decorator to apply rate limiting and Prometheus metrics to external API calls.
    Includes retry logic for transient errors.
    
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
            
            for attempt in range(rate_limiter.max_retries + 1):
                # Rate limit before making the call (and before each retry)
                await rate_limiter._wait_if_needed(f"{service}:{api_client_type}:{endpoint}")

                # Prometheus: Increment total calls counter (only for initial attempt, retries are separate)
                if attempt == 0:
                    EXTERNAL_API_CALLS_TOTAL.labels(
                        service=service,
                        api_client_type=api_client_type,
                        endpoint=endpoint
                    ).inc()
                else:
                    EXTERNAL_API_CALL_RETRIES_TOTAL.labels(
                        service=service,
                        api_client_type=api_client_type,
                        endpoint=endpoint
                    ).inc()
                    wait_time = rate_limiter.retry_backoff_factor * (2 ** (attempt - 1))
                    rate_limiter.logger.info(f"Retrying {service}:{api_client_type}:{endpoint} (Attempt {attempt}/{rate_limiter.max_retries}). Waiting {wait_time:.2f}s.")
                    await asyncio.sleep(wait_time)

                start_time = time.perf_counter()
                status_code = "unknown" # Default status code for errors

                try:
                    result = await func(*args, **kwargs)
                    status_code = "200" # Placeholder for success, refine if actual status code is available
                    return result
                except Exception as e:
                    # Determine if it's a retryable error (e.g., 5xx, timeout, connection error)
                    is_retryable = False
                    if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                        status_code = str(e.response.status_code)
                        if 500 <= e.response.status_code < 600: # 5xx errors are generally retryable
                            is_retryable = True
                    elif isinstance(e, (asyncio.TimeoutError, aiohttp.ClientConnectorError, openai.APIConnectionError)):
                        status_code = "network_error"
                        is_retryable = True
                    elif hasattr(e, 'status_code') and 500 <= e.status_code < 600: # For openai.APIStatusError
                        status_code = str(e.status_code)
                        is_retryable = True
                    else:
                        status_code = "500" # Generic error

                    if is_retryable and attempt < rate_limiter.max_retries:
                        rate_limiter.logger.warning(f"Transient error for {service}:{api_client_type}:{endpoint} (Status: {status_code}). Retrying...")
                        continue # Go to next attempt
                    else:
                        # Log and re-raise if not retryable or max retries reached
                        rate_limiter.logger.error(f"Failed after {attempt+1} attempts for {service}:{api_client_type}:{endpoint} (Status: {status_code}): {e}", exc_info=True)
                        EXTERNAL_API_CALL_ERRORS_TOTAL.labels(
                            service=service,
                            api_client_type=api_client_type,
                            endpoint=endpoint,
                            status_code=status_code
                        ).inc()
                        raise # Re-raise the original exception
                finally:
                    # Prometheus: Observe call duration
                    duration = time.perf_counter() - start_time
                    EXTERNAL_API_CALL_DURATION_SECONDS.labels(
                        service=service,
                        api_client_type=api_client_type,
                        endpoint=endpoint
                    ).observe(duration)
            
            # This part should ideally not be reached if exceptions are always re-raised or returned
            # but it's here for completeness in case the loop finishes without a return/raise.
            return None # Should not happen
        return wrapper
    return decorator
