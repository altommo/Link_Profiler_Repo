import logging
from typing import Dict, Any, Optional, Callable, Awaitable
import asyncio

from Link_Profiler.utils.api_quota_manager import APIQuotaManager
from Link_Profiler.clients.base_client import BaseAPIClient # Assuming BaseAPIClient is the base for all specific API clients

logger = logging.getLogger(__name__)

class APIRoutingService:
    """
    A dedicated service layer for routing API calls to the optimal external API client.
    It encapsulates the logic of selecting the best API based on APIQuotaManager's recommendations,
    and handles multi-tiered fallbacks.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(APIRoutingService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, api_quota_manager: APIQuotaManager, api_clients: Dict[str, BaseAPIClient]):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".APIRoutingService")
        self.api_quota_manager = api_quota_manager
        self.api_clients = api_clients # Dictionary of all initialized API clients (e.g., {"serpstack": SerpstackClient_instance})
        self.logger.info("APIRoutingService initialized.")

    async def __aenter__(self):
        """Enter context for all underlying API clients."""
        self.logger.debug("Entering APIRoutingService context.")
        for client in self.api_clients.values():
            await client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context for all underlying API clients."""
        self.logger.debug("Exiting APIRoutingService context.")
        for client in self.api_clients.values():
            await client.__aexit__(exc_type, exc_val, exc_tb)

    async def route_api_call(
        self,
        query_type: str,
        api_call_func: Callable[..., Awaitable[Any]], # The actual method to call on the client (e.g., client.search)
        api_name_prefix: str, # Prefix to identify the API client type (e.g., "serpstack", "valueserp")
        optimize_for_cost: bool = False,
        ml_enabled: bool = False,
        **kwargs # Arguments to pass to the api_call_func
    ) -> Any:
        """
        Routes an API call to the optimal external API client based on strategy and handles fallbacks.

        Args:
            query_type (str): The type of query (e.g., "serp_search", "whois_lookup").
            api_call_func (Callable): The asynchronous method to call on the selected API client.
                                      This function should accept the client instance as its first argument,
                                      followed by its specific parameters.
            api_name_prefix (str): A string prefix to identify the relevant API clients in self.api_clients.
                                   (e.g., "serpstack" for SerpstackClient, "valueserp" for ValueserpClient).
            optimize_for_cost (bool): If True, prioritizes cost optimization; otherwise, prioritizes quality.
            ml_enabled (bool): If True, enables ML influence on routing decisions.
            **kwargs: Arguments to pass to the api_call_func.

        Returns:
            Any: The result of the API call.

        Raises:
            Exception: If all API attempts (including fallbacks) fail.
        """
        selected_api_name: Optional[str] = None
        result = None
        exception_caught: Optional[Exception] = None

        # Tier 1: Try the best quality/quota-optimized API
        if optimize_for_cost:
            selected_api_name = await self.api_quota_manager.get_quota_optimized_api(query_type, ml_enabled)
            strategy_used = "quota_optimized"
        else:
            selected_api_name = await self.api_quota_manager.get_best_quality_api(query_type, ml_enabled)
            strategy_used = "best_quality"

        if selected_api_name and selected_api_name in self.api_clients:
            client_instance = self.api_clients[selected_api_name]
            try:
                self.logger.info(f"Routing '{query_type}' call to primary API: '{selected_api_name}' (Strategy: {strategy_used}).")
                start_time = time.monotonic()
                result = await api_call_func(client_instance, **kwargs) # Pass client instance and kwargs
                response_time_ms = (time.monotonic() - start_time) * 1000
                self.api_quota_manager.record_api_performance(selected_api_name, True, response_time_ms, query_type, strategy_used)
                self.api_quota_manager.record_usage(selected_api_name, 1)
                return result
            except Exception as e:
                exception_caught = e
                self.logger.warning(f"Primary API '{selected_api_name}' failed for '{query_type}': {e}. Attempting fallback.")
                response_time_ms = (time.monotonic() - start_time) * 1000
                self.api_quota_manager.record_api_performance(selected_api_name, False, response_time_ms, query_type, strategy_used)
        else:
            self.logger.warning(f"No primary API found for '{query_type}' (Strategy: {strategy_used}). Attempting fallback.")

        # Tier 2: Fallback to any other available API
        fallback_api_name = await self.api_quota_manager.get_any_available_api(query_type)
        if fallback_api_name and fallback_api_name != selected_api_name and fallback_api_name in self.api_clients:
            client_instance = self.api_clients[fallback_api_name]
            try:
                self.logger.info(f"Routing '{query_type}' call to fallback API: '{fallback_api_name}'.")
                start_time = time.monotonic()
                result = await api_call_func(client_instance, **kwargs)
                response_time_ms = (time.monotonic() - start_time) * 1000
                self.api_quota_manager.record_api_performance(fallback_api_name, True, response_time_ms, query_type, "fallback_any")
                self.api_quota_manager.record_usage(fallback_api_name, 1)
                return result
            except Exception as e:
                exception_caught = e
                self.logger.warning(f"Fallback API '{fallback_api_name}' also failed for '{query_type}': {e}. Resorting to simulation.")
                response_time_ms = (time.monotonic() - start_time) * 1000
                self.api_quota_manager.record_api_performance(fallback_api_name, False, response_time_ms, query_type, "fallback_any")
        else:
            self.logger.warning(f"No suitable fallback API found for '{query_type}'. Resorting to simulation.")

        # Tier 3: Final Fallback to a simulated client if available
        simulated_api_name = f"simulated_{api_name_prefix}" # e.g., "simulated_serpstack"
        if simulated_api_name in self.api_clients:
            client_instance = self.api_clients[simulated_api_name]
            try:
                self.logger.info(f"Routing '{query_type}' call to simulated API: '{simulated_api_name}'.")
                start_time = time.monotonic()
                result = await api_call_func(client_instance, **kwargs)
                response_time_ms = (time.monotonic() - start_time) * 1000
                self.api_quota_manager.record_api_performance(simulated_api_name, True, response_time_ms, query_type, "simulated_fallback")
                return result
            except Exception as e:
                exception_caught = e
                self.logger.error(f"Simulated API '{simulated_api_name}' also failed for '{query_type}': {e}. This should not happen.", exc_info=True)
                response_time_ms = (time.monotonic() - start_time) * 1000
                self.api_quota_manager.record_api_performance(simulated_api_name, False, response_time_ms, query_type, "simulated_fallback")
        else:
            self.logger.error(f"No simulated client '{simulated_api_name}' available for '{query_type}'.")

        # If all attempts fail, re-raise the last caught exception or a generic one
        if exception_caught:
            raise exception_caught
        raise Exception(f"Failed to route API call for '{query_type}' after all attempts.")
