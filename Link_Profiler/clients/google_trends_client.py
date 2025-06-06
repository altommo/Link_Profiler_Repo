import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager

logger = logging.getLogger(__name__)

class GoogleTrendsClient(BaseAPIClient):
    """
    Client for Google Trends data using pytrends (unofficial API).
    Note: pytrends is a wrapper around Google Trends website, not an official API.
    It might be unstable and subject to changes.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        super().__init__(session_manager, resilience_manager)
        self.logger = logging.getLogger(__name__ + ".GoogleTrendsClient")
        self.enabled = config_loader.get("keyword_api.google_trends_api.enabled", False)
        
        # pytrends does not require an API key, but it does require a session.
        # It also has rate limits and can be blocked.
        # For server-side use, it's often better to use a proxy or a dedicated service.
        
        if self.enabled and self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        if not self.enabled:
            self.logger.info("Google Trends API is disabled by configuration.")
            return

        try:
            from pytrends.request import TrendReq
            self.pytrends = TrendReq(hl='en-US', tz=360, retries=5, backoff_factor=0.5)
            self.logger.info("pytrends client initialized for Google Trends.")
        except ImportError:
            self.logger.error("pytrends library not found. Google Trends functionality will be disabled. Install with 'pip install pytrends'.")
            self.enabled = False
        except Exception as e:
            self.logger.error(f"Error initializing pytrends: {e}. Google Trends functionality will be disabled.", exc_info=True)
            self.enabled = False

    async def __aenter__(self):
        """No specific async setup needed for pytrends, but BaseAPIClient requires it."""
        if self.enabled:
            self.logger.debug("Entering GoogleTrendsClient context.")
            # pytrends manages its own session, so we don't need to enter self.session_manager here.
            # However, BaseAPIClient's __aenter__ expects it, so we call super().
            await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for pytrends, but BaseAPIClient requires it."""
        if self.enabled:
            self.logger.debug("Exiting GoogleTrendsClient context.")
            await super().__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="google_trends_api", api_client_type="google_trends_client", endpoint="get_interest_over_time")
    async def get_interest_over_time(self, keywords: List[str], timeframe: str = 'today 12-m') -> Optional[Dict[str, Dict[str, int]]]:
        """
        Fetches interest over time for a list of keywords.
        
        Args:
            keywords (List[str]): A list of keywords (max 5) to fetch data for.
            timeframe (str): Timeframe for the data (e.g., 'today 12-m', '2019-01-01 2019-12-31').
            
        Returns:
            Optional[Dict[str, Dict[str, int]]]: A dictionary where keys are keywords and values are lists
                                              of interest scores over time, or None on failure.
        """
        if not self.enabled or not self.pytrends:
            self.logger.warning(f"Google Trends API is disabled. Skipping interest over time for {keywords}.")
            return None
        if not keywords or len(keywords) > 5:
            self.logger.error("Invalid number of keywords for Google Trends (max 5).")
            return None

        self.logger.info(f"Fetching Google Trends interest over time for keywords: {keywords} (Timeframe: {timeframe})...")
        
        all_trends_data: Dict[str, Dict[str, int]] = {kw: {} for kw in keywords}
        
        # Pytrends has a limit on the number of keywords per request (usually 5)
        chunk_size = 4 # Pytrends allows up to 5, but 4 is safer for related queries
        
        for i in range(0, len(keywords), chunk_size):
            chunk = keywords[i:i + chunk_size]
            
            # Explicit throttling to respect Google Trends free tier (approx. 10 requests/min)
            # This is handled by the resilience manager's rate limiting, but a manual sleep is also good for pytrends.
            await asyncio.sleep(random.uniform(1.0, 3.0)) # Be respectful to Google Trends rate limits

            try:
                # Use resilience manager for the synchronous pytrends call
                await self.resilience_manager.execute_with_resilience(
                    lambda: self.pytrends.build_payload(chunk, cat=0, timeframe=timeframe, geo='', gprop=''),
                    url="https://trends.google.com/trends/api/explore" # Use a representative URL for CB
                )
                interest_over_time_df = await self.resilience_manager.execute_with_resilience(
                    lambda: self.pytrends.interest_over_time(),
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

            except Exception as e: # Catch generic exception for pytrends errors
                self.logger.error(f"Error fetching trends for keywords {chunk}: {e}", exc_info=True)
                for kw in chunk:
                    all_trends_data[kw] = {}
            
        return all_trends_data

    @api_rate_limited(service="google_trends_api", api_client_type="google_trends_client", endpoint="get_related_queries")
    async def get_related_queries(self, keyword: str) -> Optional[Dict[str, Any]]:
        """
        Fetches related queries for a given keyword.
        """
        if not self.enabled or not self.pytrends:
            self.logger.warning(f"Google Trends API is disabled. Skipping related queries for {keyword}.")
            return None

        self.logger.info(f"Fetching Google Trends related queries for keyword: {keyword}...")
        
        try:
            self.pytrends.build_payload([keyword], cat=0, timeframe='today 12-m', geo='', gprop='')
            related_queries_dict = await self.resilience_manager.execute_with_resilience(
                lambda: self.pytrends.related_queries(),
                url="https://trends.google.com/trends/api/widgetdata/relatedsearches" # Representative URL for CB
            )

            if not related_queries_dict or keyword not in related_queries_dict:
                self.logger.warning(f"No Google Trends related queries found for: {keyword}.")
                return None

            # pytrends returns a dictionary of DataFrames. Convert to lists of dicts.
            result = {}
            for query_type, df in related_queries_dict[keyword].items():
                if not df.empty:
                    result[query_type] = df.to_dict(orient='records')
            
            self.logger.info(f"Google Trends related queries for {keyword} fetched successfully.")
            return result

        except Exception as e: # Catch generic exception for pytrends errors
            self.logger.error(f"Error fetching Google Trends related queries for {keyword}: {e}", exc_info=True)
            return None
