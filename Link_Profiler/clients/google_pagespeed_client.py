"""
Google PageSpeed Insights Client - Fetches PageSpeed data for URLs.
File: Link_Profiler/clients/google_pagespeed_client.py
"""

import asyncio
import logging
from typing import Dict, Any, Optional
import aiohttp
import json
import time # Import time for time.monotonic()
from datetime import datetime # For last_fetched_at

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class PageSpeedClient:
    """
    Client for fetching PageSpeed Insights data from Google's API.
    Requires a Google Cloud API key with PageSpeed Insights API enabled.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__ + ".PageSpeedClient")
        self.base_url = config_loader.get("serp_api.pagespeed_insights_api.base_url")
        self.api_key = config_loader.get("serp_api.pagespeed_insights_api.api_key")
        self.enabled = config_loader.get("serp_api.pagespeed_insights_api.enabled", False)
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager # Avoid name collision
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to PageSpeedClient. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        # Removed problematic fallback import
        if self.enabled and self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        self._last_call_time: float = 0.0 # For explicit throttling

        if not self.enabled:
            self.logger.info("PageSpeed Insights API is disabled by configuration.")
        elif not self.api_key:
            self.logger.error("PageSpeed Insights API enabled but API key is missing in config.")
            self.enabled = False
        elif not self.base_url:
            self.logger.error("PageSpeed Insights API enabled but base_url is missing in config.")
            self.enabled = False

    async def __aenter__(self):
        """Async context manager entry for client session."""
        if self.enabled:
            self.logger.info("Entering PageSpeedClient context.")
            await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        if self.enabled:
            self.logger.info("Exiting PageSpeedClient context. Closing aiohttp session.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def _throttle(self):
        """Ensures at least 60 second delay between calls to PageSpeed Insights."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < 60.0:
            wait_time = 60.0 - elapsed
            self.logger.debug(f"Throttling PageSpeed Insights API. Waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)
        self._last_call_time = time.monotonic()

    @api_rate_limited(service="pagespeed_insights_api", api_client_type="pagespeed_client", endpoint="analyze_url")
    async def analyze_url(self, url: str, strategy: str = 'mobile') -> Optional[Dict[str, Any]]:
        """
        Fetches PageSpeed Insights data for a given URL.
        
        Args:
            url: The URL to analyze.
            strategy: 'mobile' or 'desktop'.
            
        Returns:
            A dictionary containing the PageSpeed Insights report, or None if an error occurs.
        """
        if not self.enabled:
            self.logger.warning("PageSpeedClient is disabled. Cannot analyze URL.")
            return None

        if not self.api_key or not self.base_url:
            self.logger.error("PageSpeedClient API key or base URL is not configured.")
            return None

        await self._throttle() # Apply explicit throttling

        params = {
            "url": url,
            "key": self.api_key,
            "strategy": strategy.upper()
        }
        self.logger.info(f"Fetching PageSpeed Insights for {url} with strategy {strategy.upper()}...")

        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(self.base_url, params=params, timeout=30),
                url=self.base_url # Pass the base URL for circuit breaker naming
            )
            response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            data = await response.json()
            self.logger.info(f"Successfully fetched PageSpeed Insights for {url}.")
            data['last_fetched_at'] = datetime.utcnow().isoformat() # Set last_fetched_at for live data
            return data
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                self.logger.warning(f"PageSpeed Insights API rate limit exceeded for {url}. Retrying after 60 seconds.")
                await asyncio.sleep(60)
                return await self.analyze_url(url, strategy) # Retry the call
            else:
                self.logger.error(f"Network/API error fetching PageSpeed Insights for {url} (Status: {e.status}): {e}. Returning None.", exc_info=True)
                return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching PageSpeed Insights for {url}: {e}. Returning None.", exc_info=True)
            return None

