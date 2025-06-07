import logging
from typing import Optional, Dict, Any
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager
from datetime import datetime # Import datetime
import asyncio # Import asyncio for sleep

class BaseAPIClient:
    """
    Base class for all API clients to provide common functionality
    like session management and logging.
    """
    def __init__(self, session_manager: SessionManager, resilience_manager: DistributedResilienceManager, api_quota_manager: APIQuotaManager):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Session Manager: Must be provided
        self.session_manager = session_manager
        if not self.session_manager:
            raise ValueError(f"SessionManager must be provided for {self.__class__.__name__}.")

        # Resilience Manager: Must be provided
        self.resilience_manager = resilience_manager
        if not self.resilience_manager:
            raise ValueError(f"DistributedResilienceManager must be provided for {self.__class__.__name__}.")
        
        # API Quota Manager: Must be provided
        self.api_quota_manager = api_quota_manager
        if not self.api_quota_manager:
            raise ValueError(f"APIQuotaManager must be provided for {self.__class__.__name__}.")


    async def __aenter__(self):
        """Ensure the session manager is entered when using the client as an async context manager."""
        if self.session_manager:
            await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure the session manager is exited when using the client as an async context manager."""
        if self.session_manager:
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def _make_request(self, method: str, url: str, **kwargs):
        """
        Internal helper to make requests using the shared session manager.
        Handles common errors and logging.
        Implements multi-tiered fallback using APIQuotaManager.
        """
        # Determine the API name for this client instance (e.g., "serpstack", "builtwith")
        # This assumes a naming convention or a way to derive it from the class name
        api_name = self.__class__.__name__.replace("Client", "").lower() # e.g., SerpstackClient -> serpstack

        start_time = datetime.utcnow()
        success = False
        response_time_ms = 0.0
        try:
            # Wrap the actual request with the resilience manager
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.request(method, url, **kwargs),
                url=url # Use the request URL for circuit breaker naming
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            success = True
            
            # Add last_fetched_at to the response object if it's a dict/json
            try:
                json_data = await response.json()
                # Ensure json_data is a dictionary before adding a key
                if isinstance(json_data, dict):
                    json_data['last_fetched_at'] = datetime.utcnow().isoformat()
                return json_data
            except Exception:
                # If response is not JSON, return the response object itself
                return response
        except Exception as e:
            self.logger.error(f"Request to {url} failed: {e}")
            raise
        finally:
            end_time = datetime.utcnow()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            # Record performance and usage
            if self.api_quota_manager:
                self.api_quota_manager.record_api_performance(api_name, success, response_time_ms)
                if success: # Only record usage if the call was successful
                    self.api_quota_manager.record_usage(api_name)
