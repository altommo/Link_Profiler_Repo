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

class WebscrapingAIClient(BaseAPIClient):
    """
    Client for the Webscraping.AI API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Pass api_quota_manager to BaseAPIClient
        self.logger = logging.getLogger(__name__ + ".WebscrapingAIClient")
        self.base_url = config_loader.get("external_apis.webscraping_ai.base_url", "https://api.webscraping.ai/api/v1/")
        self.api_key = config_loader.get("external_apis.webscraping_ai.api_key")
        self.enabled = config_loader.get("external_apis.webscraping_ai.enabled", False)
        # resilience_manager and api_quota_manager are now handled by BaseAPIClient's __init__

        if not self.enabled or not self.api_key:
            self.logger.info("Webscraping.AI API is disabled or API key is missing.")

    async def __aenter__(self):
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await super().__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="webscraping_ai", api_client_type="webscraping_ai_client", endpoint="scrape")
    async def scrape(self, url: str, render_js: bool = False, proxy: bool = False) -> Dict[str, Any]:
        """
        Scrapes a URL using the Webscraping.AI API.
        """
        if not self.enabled or not self.api_key:
            self.logger.warning("Webscraping.AI API is not enabled or API key is missing.")
            return {"error": "Webscraping.AI API not enabled or key missing"}

        params = {
            "api_key": self.api_key,
            "url": url,
            "render_js": render_js,
            "proxy": proxy
        }

        try:
            data = await self._make_request("GET", self.base_url + "scrape", params=params)
            self.logger.info(f"Webscraping.AI scrape for '{url}' successful.")
            return data
        except Exception as e:
            self.logger.error(f"Error during Webscraping.AI scrape for '{url}': {e}", exc_info=True)
            return {"error": str(e)}
