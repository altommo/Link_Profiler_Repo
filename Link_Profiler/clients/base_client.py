import logging
from typing import Optional
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager
from datetime import datetime # Import datetime
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

class BaseAPIClient:
    """
    Base class for all API clients to provide common functionality
    like session management and logging.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session_manager = session_manager
        if self.session_manager is None:
            # Fallback to the global singleton if not explicitly provided
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager
            self.session_manager = global_session_manager
            self.logger.warning(f"No SessionManager provided for {self.__class__.__name__}. Using global singleton.")

        self.resilience_manager = resilience_manager
        if self.resilience_manager is None:
            # This client is enabled but no DistributedResilienceManager was provided.
            # This indicates a configuration error or missing dependency injection.
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")
        
        self.api_quota_manager = api_quota_manager
        if self.api_quota_manager is None:
            # This client is enabled but no APIQuotaManager was provided.
            # This indicates a configuration error or missing dependency injection.
            raise ValueError(f"{self.__class__.__name__} is enabled but no APIQuotaManager was provided.")


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
        """
        if not self.session_manager:
            self.logger.error("SessionManager is not initialized for this client.")
            raise RuntimeError("SessionManager is not initialized.")
        if not self.resilience_manager:
            self.logger.error("ResilienceManager is not initialized for this client.")
            raise RuntimeError("ResilienceManager is not initialized.")

        try:
            # Wrap the actual request with the resilience manager
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.request(method, url, **kwargs),
                url=url # Use the request URL for circuit breaker naming
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            
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
