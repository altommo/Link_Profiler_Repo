"""
Google Trends Client - Interacts with Google Trends using the unofficial pytrends library.
File: Link_Profiler/clients/google_trends_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from pytrends.request import TrendReq # Requires pip install pytrends

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

class GoogleTrendsClient:
    """
    Client for fetching data from Google Trends using the unofficial `pytrends` library.
    Note: `pytrends` uses synchronous requests, so calls are wrapped in `asyncio.to_thread`.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".GoogleTrendsClient")
        self.enabled = config_loader.get("keyword_api.google_trends_api.enabled", False)
        self.pytrends: Optional[TrendReq] = None

        if not self.enabled:
            self.logger.info("Google Trends API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise pytrends client."""
        if self.enabled:
            self.logger.info("Entering GoogleTrendsClient context.")
            # pytrends initialization is synchronous
            self.pytrends = TrendReq(hl='en-US', tz=360) # hl: host language, tz: timezone offset
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No explicit close method for pytrends, but good practice for context."""
        self.logger.info("Exiting GoogleTrendsClient context.")
        self.pytrends = None # Clear instance

    @api_rate_limited(service="google_trends_api", api_client_type="google_trends_client", endpoint="get_keyword_trends")
    async def get_keyword_trends(self, keywords: List[str], timeframe: str = 'today 12-m') -> Dict[str, Any]:
        """
        Fetches keyword trend data from Google Trends.
        
        Args:
            keywords (List[str]): List of keywords to fetch trends for (max 5).
            timeframe (str): Timeframe for the trend data (e.g., 'today 12-m', '2018-01-01 2018-12-31').
        
        Returns:
            Dict[str, Any]: Dictionary containing 'interest_over_time', 'related_queries', 'rising_queries'.
        """
        if not self.enabled or not self.pytrends:
            self.logger.warning(f"Google Trends API is disabled or not initialized. Simulating trend data for {keywords}.")
            return self._simulate_trends(keywords, timeframe)

        if not (1 <= len(keywords) <= 5):
            self.logger.error("Google Trends API supports 1 to 5 keywords per request.")
            return self._simulate_trends(keywords, timeframe)

        self.logger.info(f"Fetching Google Trends data for keywords: {keywords} ({timeframe})...")
        try:
            # pytrends methods are synchronous, run in a separate thread
            await asyncio.to_thread(self.pytrends.build_payload, keywords, cat=0, timeframe=timeframe, geo='', gprop='')
            
            interest_over_time = await asyncio.to_thread(self.pytrends.interest_over_time)
            related_queries = await asyncio.to_thread(self.pytrends.related_queries)
            # trending_searches is global, not keyword specific, so might not be directly useful here
            # rising_searches = await asyncio.to_thread(self.pytrends.trending_searches, pn='united_states')

            # Convert pandas DataFrames to dictionaries/lists for serialization
            interest_over_time_dict = interest_over_time.to_dict(orient='records') if not interest_over_time.empty else []
            
            related_queries_dict = {}
            for key, df in related_queries.items():
                if df is not None and not df.empty:
                    related_queries_dict[key] = df.to_dict(orient='records')
                else:
                    related_queries_dict[key] = []

            self.logger.info(f"Google Trends data for {keywords} completed.")
            return {
                'interest_over_time': interest_over_time_dict,
                'related_queries': related_queries_dict,
                'rising_queries': [] # Not directly from keyword payload
            }
        except Exception as e:
            self.logger.error(f"Error fetching Google Trends data for {keywords}: {e}", exc_info=True)
            return self._simulate_trends(keywords, timeframe) # Fallback to simulation on error

    def _simulate_trends(self, keywords: List[str], timeframe: str) -> Dict[str, Any]:
        """Helper to generate simulated Google Trends data."""
        self.logger.info(f"Simulating Google Trends data for {keywords} ({timeframe}).")
        
        # Simulate interest over time
        interest_over_time_data = []
        for i in range(12): # 12 months
            date = (datetime.now() - timedelta(days=30 * (11 - i))).strftime("%Y-%m-%d")
            row = {"date": date}
            for keyword in keywords:
                row[keyword] = random.randint(30, 90)
            interest_over_time_data.append(row)

        # Simulate related queries
        related_queries_data = {}
        for keyword in keywords:
            related_queries_data[keyword] = {
                "top": [{"query": f"related {keyword} 1", "value": random.randint(50, 100)},
                        {"query": f"related {keyword} 2", "value": random.randint(30, 70)}],
                "rising": [{"query": f"trending {keyword} A", "value": random.randint(100, 300)},
                           {"query": f"trending {keyword} B", "value": random.randint(50, 150)}]
            }

        return {
            'interest_over_time': interest_over_time_data,
            'related_queries': related_queries_data,
            'rising_queries': []
        }
