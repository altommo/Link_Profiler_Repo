import logging
import asyncio
from typing import Dict, Any, Optional
import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager

logger = logging.getLogger(__name__)

class PageSpeedClient(BaseAPIClient):
    """
    Client for Google PageSpeed Insights API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        super().__init__(session_manager, resilience_manager)
        self.logger = logging.getLogger(__name__ + ".PageSpeedClient")
        self.base_url = config_loader.get("serp_api.pagespeed_insights_api.base_url")
        self.api_key = config_loader.get("serp_api.pagespeed_insights_api.api_key")
        self.enabled = config_loader.get("serp_api.pagespeed_insights_api.enabled", False)

        if not self.enabled:
            self.logger.info("Google PageSpeed Insights API is disabled by configuration.")
        elif not self.api_key:
            self.logger.warning("Google PageSpeed Insights API key is missing. PageSpeed Insights will be disabled.")
            self.enabled = False

    @api_rate_limited(service="pagespeed_api", api_client_type="pagespeed_client", endpoint="analyze_url")
    async def analyze_url(self, url: str, strategy: str = 'mobile') -> Optional[Dict[str, Any]]:
        """
        Analyzes the performance of a web page using Google PageSpeed Insights.
        
        Args:
            url (str): The URL to analyze.
            strategy (str): The strategy to use, 'mobile' or 'desktop'.
            
        Returns:
            Optional[Dict[str, Any]]: The JSON response from the PageSpeed Insights API, or None on failure.
        """
        if not self.enabled:
            self.logger.warning(f"PageSpeed Insights API is disabled. Skipping analysis for {url}.")
            return None

        params = {
            'url': url,
            'key': self.api_key,
            'strategy': strategy
        }

        self.logger.info(f"Calling PageSpeed Insights API for URL: {url} (Strategy: {strategy})...")
        try:
            # _make_request now handles resilience
            response_data = await self._make_request("GET", self.base_url, params=params)
            self.logger.info(f"PageSpeed Insights data for {url} fetched successfully.")
            return response_data
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Network/API error fetching PageSpeed Insights data for {url} (Status: {e.status}): {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Error fetching PageSpeed Insights data for {url}: {e}", exc_info=True)
            return None

