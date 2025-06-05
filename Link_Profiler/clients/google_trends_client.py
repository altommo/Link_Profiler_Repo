"""
Google Trends Client - Fetches Google Trends data using pytrends.
File: Link_Profiler/clients/google_trends_client.py

Google Trends free tier allows approximately 10 requests/minute.
Ingestion jobs must ensure a delay of at least 6 seconds between consecutive calls
to `get_interest_over_time` to stay within these limits.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import time # Import time for time.monotonic()

from pytrends.request import TrendReq
from pytrends.exceptions import ResponseError as PytrendsResponseError

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class GoogleTrendsClient:
    """
    Client for fetching Google Trends data using the unofficial pytrends library.
    Pytrends is synchronous, so its methods are run in a thread pool.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__ + ".GoogleTrendsClient")
        self.enabled = config_loader.get("keyword_api.google_trends_api.enabled", False)
        self.session_manager = session_manager # Store the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager # Avoid name collision
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to GoogleTrendsClient. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to GoogleTrendsClient. Falling back to global instance.")


        self.pytrends_client: Optional[TrendReq] = None
        self._last_call_time: float = 0.0 # For explicit throttling

        if not self.enabled:
            self.logger.info("Google Trends API is disabled by configuration.")

    async def __aenter__(self):
        """Initializes the pytrends client."""
        if self.enabled:
            self.logger.info("Entering GoogleTrendsClient context.")
            # pytrends does not directly use aiohttp session, but we ensure it's available
            await self.session_manager.__aenter__()
            self.pytrends_client = TrendReq(hl='en-US', tz=360) # hl: host language, tz: timezone offset
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleans up pytrends client (no explicit close method)."""
        if self.enabled:
            self.logger.info("Exiting GoogleTrendsClient context.")
            self.pytrends_client = None # Clear the client instance
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="google_trends_api", api_client_type="google_trends_client", endpoint="get_interest_over_time")
    async def get_interest_over_time(self, keywords: List[str], timeframe: str = 'today 12-m') -> Dict[str, Dict[str, int]]:
        """
        Fetches historical monthly interest data for keywords using Pytrends.
        Pytrends is synchronous, so its methods are run in a thread pool.
        
        Returns:
            Dict[str, Dict[str, int]]: keyword -> {date_str: trend_value}
        """
        if not self.enabled or not self.pytrends_client:
            self.logger.warning("GoogleTrendsClient is disabled or not initialized. Cannot fetch trends.")
            return {kw: {} for kw in keywords}

        all_trends_data: Dict[str, Dict[str, int]] = {kw: {} for kw in keywords}
        
        # Pytrends has a limit on the number of keywords per request (usually 5)
        chunk_size = 4 # Pytrends allows up to 5, but 4 is safer for related queries
        
        for i in range(0, len(keywords), chunk_size):
            chunk = keywords[i:i + chunk_size]
            
            # Explicit throttling to respect Google Trends free tier (approx. 10 requests/min)
            elapsed = time.monotonic() - self._last_call_time
            if elapsed < 6.0: # Ensure at least 6 seconds between calls
                wait_time = 6.0 - elapsed
                self.logger.info(f"Throttling Google Trends API. Waiting for {wait_time:.2f} seconds.")
                await asyncio.sleep(wait_time)
            self._last_call_time = time.monotonic()

            try:
                # Use resilience manager for the synchronous pytrends call
                await self.resilience_manager.execute_with_resilience(
                    lambda: self.pytrends_client.build_payload(chunk, cat=0, timeframe=timeframe, geo='', gprop=''),
                    url="https://trends.google.com/trends/api/explore" # Use a representative URL for CB
                )
                interest_over_time_df = await self.resilience_manager.execute_with_resilience(
                    lambda: self.pytrends_client.interest_over_time(),
                    url="https://trends.google.com/trends/api/widgetdata/comparedgeo" # Use a representative URL for CB
                )
                
                if not interest_over_time_df.empty:
                    for kw in chunk:
                        if kw in interest_over_time_df.columns:
                            trends_for_kw: Dict[str, int] = {}
                            for date_index, row in interest_over_time_df.iterrows():
                                date_str = date_index.strftime("%Y-%m-%d")
                                # Check for 'isPartial' column if it exists and is True
                                if "isPartial" in row and row["isPartial"]:
                                    continue # Skip partial data
                                trends_for_kw[date_str] = int(row[kw])
                            all_trends_data[kw] = trends_for_kw
                        else:
                            all_trends_data[kw] = {} # Keyword not found in trends data
                else:
                    for kw in chunk:
                        all_trends_data[kw] = {} # No data for this chunk

            except PytrendsResponseError as e:
                self.logger.warning(f"Pytrends API error for keywords {chunk}: {e}. Skipping trends for this chunk.")
                for kw in chunk:
                    all_trends_data[kw] = {}
            except Exception as e:
                self.logger.error(f"Unexpected error fetching trends for keywords {chunk}: {e}", exc_info=True)
                for kw in chunk:
                    all_trends_data[kw] = {}
            
        return all_trends_data

