import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlencode
import time # Import time for performance measurement

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class ValueserpClient(BaseAPIClient):
    """
    Client for the ValueSERP API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Pass api_quota_manager to BaseAPIClient
        self.logger = logging.getLogger(__name__ + ".ValueserpClient")
        self.base_url = config_loader.get("external_apis.valueserp.base_url", "https://api.valueserp.com/search")
        self.api_key = config_loader.get("external_apis.valueserp.api_key")
        self.enabled = config_loader.get("external_apis.valueserp.enabled", False)
        # resilience_manager and api_quota_manager are now handled by BaseAPIClient's __init__

        if not self.enabled or not self.api_key:
            self.logger.info("ValueSERP API is disabled or API key is missing.")

    async def __aenter__(self):
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await super().__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="valueserp", api_client_type="valueserp_client", endpoint="search")
    async def search(self, query: str, num_results: int = 10, country: str = "us") -> Dict[str, Any]:
        """
        Performs a search query using the ValueSERP API.
        """
        if not self.enabled or not self.api_key:
            self.logger.warning("ValueSERP API is not enabled or API key is missing.")
            return {"error": "ValueSERP API not enabled or key missing"}

        params = {
            "api_key": self.api_key,
            "q": query,
            "num": num_results,
            "country": country,
        }

        start_time = time.monotonic()
        success = False
        try:
            data = await self._make_request("GET", self.base_url, params=params)
            success = True
            self.logger.info(f"ValueSERP search for '{query}' successful.")
            return data
        except Exception as e:
            self.logger.error(f"Error during ValueSERP search for '{query}': {e}", exc_info=True)
            return {"error": str(e)}
        finally:
            response_time_ms = (time.monotonic() - start_time) * 1000
            self.api_quota_manager.record_api_performance("valueserp", success, response_time_ms)
