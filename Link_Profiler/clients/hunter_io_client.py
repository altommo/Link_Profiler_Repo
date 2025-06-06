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

logger = logging.getLogger(__name__)

class HunterIOClient(BaseAPIClient):
    """
    Client for the Hunter.io API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        super().__init__(session_manager)
        self.logger = logging.getLogger(__name__ + ".HunterIOClient")
        self.base_url = config_loader.get("external_apis.hunter_io.base_url", "https://api.hunter.io/v2/")
        self.api_key = config_loader.get("external_apis.hunter_io.api_key")
        self.enabled = config_loader.get("external_apis.hunter_io.enabled", False)
        self.resilience_manager = resilience_manager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to HunterIOClient. Falling back to global instance.")

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

        try:
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(self.base_url + "email-finder", params=params, timeout=30),
                url=self.base_url + "email-finder"
            )
            response.raise_for_status()
            data = await response.json()
            self.logger.info(f"Hunter.io email finder for '{domain}' successful.")
            return data
        except Exception as e:
            self.logger.error(f"Error during Hunter.io email finder for '{domain}': {e}", exc_info=True)
            return {"error": str(e)}

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

        try:
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(self.base_url + "domain-search", params=params, timeout=30),
                url=self.base_url + "domain-search"
            )
            response.raise_for_status()
            data = await response.json()
            self.logger.info(f"Hunter.io domain search for '{domain}' successful.")
            return data
        except Exception as e:
            self.logger.error(f"Error during Hunter.io domain search for '{domain}': {e}", exc_info=True)
            return {"error": str(e)}
