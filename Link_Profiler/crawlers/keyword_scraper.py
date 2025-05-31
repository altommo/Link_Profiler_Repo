"""
Keyword Scraper - Scrapes public keyword suggestion endpoints and integrates with Pytrends.
File: Link_Profiler/crawlers/keyword_scraper.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp
from urllib.parse import urlencode

from pytrends.request import TrendReq # For Google Trends
from pytrends.exceptions import ResponseError as PytrendsResponseError

from Link_Profiler.core.models import KeywordSuggestion # Absolute import
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager
from Link_Profiler.config.config_loader import config_loader # New: Import config_loader

logger = logging.getLogger(__name__)

class KeywordScraper:
    """
    Scrapes keyword suggestions from public endpoints (Google, Bing) and
    fetches trend data using Pytrends.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None
        self.pytrends_client: Optional[TrendReq] = None

    async def __aenter__(self):
        """Initialises aiohttp session and Pytrends client."""
        self.logger.info("Entering KeywordScraper context.")
        if self._session is None or self._session.closed:
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()
            else:
                # Default user agent if no rotation/randomization is enabled
                headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

            self._session = aiohttp.ClientSession(headers=headers)
        
        # Pytrends is synchronous, so we'll run its methods in a thread pool
        self.pytrends_client = TrendReq(hl='en-US', tz=360) # tz=360 for GMT+6, adjust as needed
        
        self.logger.info("KeywordScraper initialised.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes aiohttp session."""
        self.logger.info("Exiting KeywordScraper context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self.pytrends_client = None # Clear pytrends client
        self.logger.info("KeywordScraper closed.")

    async def _get_google_suggestions(self, query: str) -> List[str]:
        """Fetches suggestions from Google Autocomplete API."""
        if not self._session:
            raise RuntimeError("aiohttp session not initialized.")
        
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={urlencode({'q': query})}"
        try:
            # Add human-like delays if configured
            if config_loader.get("anti_detection.human_like_delays", False):
                await asyncio.sleep(random.uniform(0.5, 1.5))

            async with self._session.get(url, timeout=5) as response:
                response.raise_for_status()
                data = await response.json()
                # Google Autocomplete returns a list of lists: [query, [suggestions], [descriptions], [urls]]
                return data[1] if len(data) > 1 else []
        except aiohttp.ClientError as e:
            self.logger.warning(f"Error fetching Google suggestions for '{query}': {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in Google suggestions fetch for '{query}': {e}", exc_info=True)
            return []

    async def _get_bing_suggestions(self, query: str) -> List[str]:
        """Fetches suggestions from Bing Suggest API."""
        if not self._session:
            raise RuntimeError("aiohttp session not initialized.")
        
        url = f"https://api.bing.com/qsonhs.aspx?q={urlencode({'q': query})}"
        try:
            # Add human-like delays if configured
            if config_loader.get("anti_detection.human_like_delays", False):
                await asyncio.sleep(random.uniform(0.5, 1.5))

            async with self._session.get(url, timeout=5) as response:
                response.raise_for_status()
                data = await response.json()
                # Bing Suggest returns JSON with 'AS' -> 'Results' -> 'Suggests'
                suggestions = [s['Txt'] for s in data.get('AS', {}).get('Results', [{}])[0].get('Suggests', [])]
                return suggestions
        except aiohttp.ClientError as e:
            self.logger.warning(f"Error fetching Bing suggestions for '{query}': {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in Bing suggestions fetch for '{query}': {e}", exc_info=True)
            return []

    async def _get_keyword_trends(self, keywords: List[str], timeframe: str = 'today 12-m') -> Dict[str, List[float]]:
        """
        Fetches historical monthly interest data for keywords using Pytrends.
        Pytrends is synchronous, so run it in a thread pool.
        """
        if not self.pytrends_client:
            self.logger.warning("Pytrends client not initialised. Cannot fetch trends.")
            return {kw: [] for kw in keywords}

        trends_data: Dict[str, List[float]] = {}
        
        # Pytrends has a limit on the number of keywords per request (usually 5)
        # and also rate limits.
        chunk_size = 4 # Pytrends allows up to 5, but 4 is safer for related queries
        for i in range(0, len(keywords), chunk_size):
            chunk = keywords[i:i + chunk_size]
            try:
                # Pytrends methods are synchronous, run in executor
                await asyncio.to_thread(self.pytrends_client.build_payload, chunk, cat=0, timeframe=timeframe, geo='', gprop='')
                interest_over_time_df = await asyncio.to_thread(self.pytrends_client.interest_over_time)
                
                if not interest_over_time_df.empty:
                    for kw in chunk:
                        if kw in interest_over_time_df.columns:
                            # Convert to list of floats, handling 'isPartial' column if present
                            trends_data[kw] = interest_over_time_df[kw].tolist()
                        else:
                            trends_data[kw] = []
                else:
                    for kw in chunk:
                        trends_data[kw] = []
            except PytrendsResponseError as e:
                self.logger.warning(f"Pytrends API error for keywords {chunk}: {e}. Skipping trends for this chunk.")
                for kw in chunk:
                    trends_data[kw] = []
            except Exception as e:
                self.logger.error(f"Unexpected error fetching trends for keywords {chunk}: {e}", exc_info=True)
                for kw in chunk:
                    trends_data[kw] = []
            
            # Add human-like delays if configured
            if config_loader.get("anti_detection.human_like_delays", False):
                await asyncio.sleep(random.uniform(1, 3)) # Be respectful to Google Trends rate limits
            else:
                await asyncio.sleep(random.uniform(0.5, 1.0)) # Default delay

        return trends_data

    async def get_keyword_data(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Fetches keyword suggestions and enriches them with trend data.
        """
        all_suggestions: List[str] = []
        
        # Fetch from Google
        google_suggs = await self._get_google_suggestions(seed_keyword)
        self.logger.info(f"Found {len(google_suggs)} Google suggestions for '{seed_keyword}'.")
        all_suggestions.extend(google_suggs)

        # Fetch from Bing
        bing_suggs = await self._get_bing_suggestions(seed_keyword)
        self.logger.info(f"Found {len(bing_suggs)} Bing suggestions for '{seed_keyword}'.")
        all_suggestions.extend(bing_suggs)

        # Deduplicate and limit suggestions
        unique_suggestions = list(set(s.lower() for s in all_suggestions if s.strip()))[:num_suggestions]
        
        # Fetch trends for unique suggestions
        trends = await self._get_keyword_trends(unique_suggestions)

        keyword_suggestions: List[KeywordSuggestion] = []
        for suggested_keyword_lower in unique_suggestions:
            # Simulate search volume, CPC, and competition level
            # TODO: Integrate with real APIs for search volume, CPC, and competition level.
            search_volume = random.randint(100, 10000)
            cpc_estimate = round(random.uniform(0.5, 5.0), 2)
            competition_level = random.choice(["Low", "Medium", "High"])

            keyword_suggestions.append(
                KeywordSuggestion(
                    seed_keyword=seed_keyword,
                    suggested_keyword=suggested_keyword_lower,
                    search_volume_monthly=search_volume,
                    cpc_estimate=cpc_estimate,
                    keyword_trend=trends.get(suggested_keyword_lower, []),
                    competition_level=competition_level,
                    data_timestamp=datetime.now()
                )
            )
        
        self.logger.info(f"Generated {len(keyword_suggestions)} enriched keyword suggestions for '{seed_keyword}'.")
        return keyword_suggestions

# Example usage (for testing)
async def main():
    logging.basicConfig(level=logging.INFO)
    seed = "python programming"
    
    async with KeywordScraper() as scraper:
        suggestions = await scraper.get_keyword_data(seed, num_suggestions=10)
        for s in suggestions:
            print(f"Seed: {s.seed_keyword}, Suggested: {s.suggested_keyword}, Volume: {s.search_volume_monthly}, CPC: {s.cpc_estimate}, Trend: {s.keyword_trend[:5]}..., Comp: {s.competition_level}")

if __name__ == "__main__":
    asyncio.run(main())
