"""
Google PageSpeed Insights Client - Fetches PageSpeed data for URLs.
File: Link_Profiler/clients/google_pagespeed_client.py
"""

import asyncio
import logging
from typing import Dict, Any, Optional
import aiohttp
import json

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager

logger = logging.getLogger(__name__)

class PageSpeedClient:
    """
    Client for fetching PageSpeed Insights data from Google's API.
    Requires a Google Cloud API key with PageSpeed Insights API enabled.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__ + ".PageSpeedClient")
        self.base_url = config_loader.get("serp_api.pagespeed_insights_api.base_url")
        self.api_key = config_loader.get("serp_api.pagespeed_insights_api.api_key")
        self.enabled = config_loader.get("serp_api.pagespeed_insights_api.enabled", False)
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to PageSpeedClient. Falling back to local SessionManager.")

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
            self.logger.info("Exiting PageSpeedClient context.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

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

        params = {
            "url": url,
            "key": self.api_key,
            "strategy": strategy.upper()
        }
        self.logger.info(f"Fetching PageSpeed Insights for {url} with strategy {strategy.upper()}...")

        try:
            async with await self.session_manager.get(self.base_url, params=params, timeout=30) as response:
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data = await response.json()
                self.logger.info(f"Successfully fetched PageSpeed Insights for {url}.")
                return data
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/Client error fetching PageSpeed Insights for {url}: {e}. Returning None.")
            return None
        except asyncio.TimeoutError:
            self.logger.error(f"PageSpeed Insights request for {url} timed out.")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching PageSpeed Insights for {url}: {e}. Returning None.", exc_info=True)
            return None
