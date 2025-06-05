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
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class KeywordScraper:
    """
    Scrapes keyword suggestions from public endpoints (Google, Bing) and
    fetches trend data using Pytrends.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__)
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager # Avoid name collision
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to KeywordScraper. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to KeywordScraper. Falling back to global instance.")


        self.pytrends_client: Optional[TrendReq] = None

    async def __aenter__(self):
        """Initialises aiohttp session and Pytrends client."""
        self.logger.info("Entering KeywordScraper context.")
        await self.session_manager.__aenter__() # Ensure session manager is entered
        
        # Pytrends is synchronous, so we'll run its methods in a thread pool
        self.pytrends_client = TrendReq(hl='en-US', tz=360) # tz=360 for GMT+6, adjust as needed
        
        self.logger.info("KeywordScraper initialised.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes aiohttp session."""
        self.logger.info("Exiting KeywordScraper context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb) # Ensure session manager is exited
        self.pytrends_client = None # Clear pytrends client
        self.logger.info("KeywordScraper closed.")

    async def _get_google_suggestions(self, query: str) -> List[str]:
        """Fetches suggestions from Google Autocomplete API."""
        if not self.session_manager:
            raise RuntimeError("SessionManager not initialized.")
        
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={urlencode({'q': query})}"
        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(url, timeout=5),
                url=url # Pass the URL for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            # Google Autocomplete returns a list of lists: [query, [suggestions], [descriptions], [urls]]
            return data[1] if len(data) > 1 else []
        except Exception as e:
            self.logger.warning(f"Error fetching Google suggestions for '{query}': {e}")
            return []

    async def _get_bing_suggestions(self, query: str) -> List[str]:
        """Fetches suggestions from Bing Suggest API."""
        if not self.session_manager:
            raise RuntimeError("SessionManager not initialized.")
        
        url = f"https://api.bing.com/qsonhs.aspx?q={urlencode({'q': query})}"
        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(url, timeout=5),
                url=url # Pass the URL for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            # Bing Suggest returns JSON with 'AS' -> 'Results' -> 'Suggests'
            suggestions = [s['Txt'] for s in data.get('AS', {}).get('Results', [{}])[0].get('Suggests', [])]
            return suggestions
        except Exception as e:
            self.logger.warning(f"Error fetching Bing suggestions for '{query}': {e}")
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
                            # Convert to list of floats, handling 'isPartial' column if present
                            # Ensure the column exists before accessing
                            if kw in interest_over_time_df.columns:
                                trends_data[kw] = interest_over_time_df[kw].tolist()
                            else:
                                trends_data[kw] = [] # Keyword not found in trends data
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
                    keyword=suggested_keyword_lower, # Changed from suggested_keyword
                    search_volume=search_volume, # Changed from search_volume_monthly
                    cpc=cpc_estimate, # Changed from cpc_estimate
                    competition=competition_level, # Changed from competition_level
                    difficulty=random.randint(1, 100), # New field
                    relevance=round(random.uniform(0.1, 1.0), 2), # New field
                    source="Scraper", # New field
                    # keyword_trend is already handled by trends
                    # data_timestamp is not in KeywordSuggestion dataclass
                )
            )
        
        self.logger.info(f"Generated {len(keyword_suggestions)} enriched keyword suggestions for '{seed_keyword}'.")
        return keyword_suggestions

