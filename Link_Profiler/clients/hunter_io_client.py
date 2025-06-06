import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlencode

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class HunterIOClient(BaseAPIClient):
    """
    Client for the Hunter.io API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Pass api_quota_manager to BaseAPIClient
        self.logger = logging.getLogger(__name__ + ".HunterIOClient")
        self.base_url = config_loader.get("external_apis.hunter_io.base_url", "https://api.hunter.io/v2/")
        self.api_key = config_loader.get("external_apis.hunter_io.api_key")
        self.enabled = config_loader.get("external_apis.hunter_io.enabled", False)
        # resilience_manager and api_quota_manager are now handled by BaseAPIClient's __init__

        if not self.enabled or not self.api_key:
            self.logger.info("Hunter.io API is disabled or API key is missing.")

    async def __aenter__(self):
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await super().__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="hunter_io", api_client_type="hunter_io_client", endpoint="email_finder")
    async def email_finder(self, domain: str, full_name: Optional[str] = None, company: Optional[str] = None) -> Dict[str, Any]:
        """
        Finds email addresses for a given domain.
        """
        if not self.enabled or not self.api_key:
            self.logger.warning("Hunter.io API is not enabled or API key is missing.")
            return {"error": "Hunter.io API not enabled or key missing"}

        params = {
            "api_key": self.api_key,
            "domain": domain,
        }
        if full_name:
            params["full_name"] = full_name
        if company:
            params["company"] = company

        start_time = time.monotonic()
        success = False
        try:
            data = await self._make_request("GET", self.base_url + "email-finder", params=params)
            success = True
            self.logger.info(f"Hunter.io email finder for '{domain}' successful.")
            return data
        except Exception as e:
            self.logger.error(f"Error during Hunter.io email finder for '{domain}': {e}", exc_info=True)
            return {"error": str(e)}
        finally:
            response_time_ms = (time.monotonic() - start_time) * 1000
            self.api_quota_manager.record_api_performance("hunter_io", success, response_time_ms)

    @api_rate_limited(service="hunter_io", api_client_type="hunter_io_client", endpoint="domain_search")
    async def domain_search(self, domain: str, limit: int = 10) -> Dict[str, Any]:
        """
        Searches for email addresses associated with a domain.
        """
        if not self.enabled or not self.api_key:
            self.logger.warning("Hunter.io API is not enabled or API key is missing.")
            return {"error": "Hunter.io API not enabled or key missing"}

        params = {
            "api_key": self.api_key,
            "domain": domain,
            "limit": limit
        }

        start_time = time.monotonic()
        success = False
        try:
            data = await self._make_request("GET", self.base_url + "domain-search", params=params)
            success = True
            self.logger.info(f"Hunter.io domain search for '{domain}' successful.")
            return data
        except Exception as e:
            self.logger.error(f"Error during Hunter.io domain search for '{domain}': {e}", exc_info=True)
            return {"error": str(e)}
        finally:
            response_time_ms = (time.monotonic() - start_time) * 1000
            self.api_quota_manager.record_api_performance("hunter_io", success, response_time_ms)
