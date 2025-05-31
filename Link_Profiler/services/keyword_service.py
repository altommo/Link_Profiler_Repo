"""
Keyword Service - Provides functionalities for fetching keyword research data.
File: Link_Profiler/services/keyword_service.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp
import os

from Link_Profiler.core.models import KeywordSuggestion # Absolute import
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper # New import

logger = logging.getLogger(__name__)

class BaseKeywordAPIClient:
    """
    Base class for a Keyword Research API client.
    Real implementations would connect to external services like Google Keyword Planner, Ahrefs, etc.
    """
    async def get_keyword_suggestions(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        raise NotImplementedError

    async def __aenter__(self):
        """Async context manager entry for client session."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        pass # No-op for base class

class SimulatedKeywordAPIClient(BaseKeywordAPIClient):
    """
    A simulated client for Keyword Research APIs.
    Generates dummy keyword suggestion data.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SimulatedKeywordAPIClient")
        self._session: Optional[aiohttp.ClientSession] = None # For simulating network calls

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedKeywordAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedKeywordAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_keyword_suggestions(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Simulates fetching keyword suggestions for a given seed keyword.
        """
        self.logger.info(f"Simulating API call for keyword suggestions for seed: '{seed_keyword}'")
        
        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("SimulatedKeywordAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession()
            close_session_after_use = True

        try:
            # Simulate an actual HTTP request, even if it's to a dummy URL
            async with session_to_use.get(f"http://localhost:8080/simulate_keywords/{seed_keyword}") as response:
                pass
        except aiohttp.ClientConnectorError:
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated keyword fetch: {e}")
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

        suggestions = []
        for i in range(num_suggestions):
            suggested_keyword = f"{seed_keyword} {random.choice(['ideas', 'tools', 'analysis', 'strategy'])} {i+1}"
            search_volume = random.randint(100, 10000)
            cpc_estimate = round(random.uniform(0.5, 5.0), 2)
            keyword_trend = [random.uniform(0.1, 1.0) for _ in range(12)] # 12 months of data
            competition_level = random.choice(["Low", "Medium", "High"])
            
            suggestions.append(
                KeywordSuggestion(
                    seed_keyword=seed_keyword,
                    suggested_keyword=suggested_keyword,
                    search_volume_monthly=search_volume,
                    cpc_estimate=cpc_estimate,
                    keyword_trend=keyword_trend,
                    competition_level=competition_level,
                    data_timestamp=datetime.now()
                )
            )
        self.logger.info(f"Simulated {len(suggestions)} keyword suggestions for '{seed_keyword}'.")
        return suggestions

class RealKeywordAPIClient(BaseKeywordAPIClient):
    """
    A client for a real Keyword Research API (e.g., Ahrefs, SEMrush, Google Keyword Planner).
    Requires an API key.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.real-keyword-provider.com"):
        self.logger = logging.getLogger(__name__ + ".RealKeywordAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealKeywordAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}"})
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealKeywordAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_keyword_suggestions(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Fetches keyword suggestions for a given seed keyword from a real API.
        This is a placeholder; replace with actual API call logic.
        """
        endpoint = f"{self.base_url}/keywords/suggestions"
        params = {
            "keyword": seed_keyword,
            "limit": num_suggestions,
            "api_key": self.api_key # Some APIs use query param for key
        }
        self.logger.info(f"Attempting real API call for keyword suggestions: {endpoint}?keyword={seed_keyword}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealKeywordAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}"})
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                
                suggestions = []
                # Placeholder for parsing actual API response
                # Example: assuming 'suggestions' key with list of dicts
                for item in data.get("suggestions", []):
                    suggestions.append(
                        KeywordSuggestion(
                            seed_keyword=seed_keyword,
                            suggested_keyword=item.get("keyword"),
                            search_volume_monthly=item.get("search_volume"),
                            cpc_estimate=item.get("cpc"),
                            keyword_trend=item.get("trend", []),
                            competition_level=item.get("competition"),
                            data_timestamp=datetime.now()
                        )
                    )
                self.logger.info(f"RealKeywordAPIClient: Found {len(suggestions)} keyword suggestions for '{seed_keyword}'.")
                return suggestions

        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real keyword suggestions for '{seed_keyword}': {e}. Returning empty list.")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in real keyword fetch for '{seed_keyword}': {e}. Returning empty list.")
            return []
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()


class KeywordService:
    """
    Service for fetching Keyword Research data.
    """
    def __init__(self, api_client: Optional[BaseKeywordAPIClient] = None, keyword_scraper: Optional[KeywordScraper] = None):
        self.logger = logging.getLogger(__name__)
        self.api_client = api_client if api_client else SimulatedKeywordAPIClient()
        self.keyword_scraper = keyword_scraper # Store the KeywordScraper instance
        
        # Determine which API client to use based on environment variable
        # This logic is now redundant if keyword_scraper is preferred, but kept for clarity
        # if os.getenv("USE_REAL_KEYWORD_API", "false").lower() == "true":
        #     real_api_key = os.getenv("REAL_KEYWORD_API_KEY")
        #     if not real_api_key:
        #         self.logger.error("REAL_KEYWORD_API_KEY environment variable not set. Falling back to simulated Keyword API.")
        #         self.api_client = SimulatedKeywordAPIClient()
        #     else:
        #         self.logger.info("Using RealKeywordAPIClient for keyword lookups.")
        #         self.api_client = RealKeywordAPIClient(api_key=real_api_key)
        # else:
        #     self.logger.info("Using SimulatedKeywordAPIClient for keyword lookups.")
        #     self.api_client = SimulatedKeywordAPIClient()

    async def __aenter__(self):
        """Async context manager entry for KeywordService."""
        self.logger.debug("Entering KeywordService context.")
        await self.api_client.__aenter__()
        if self.keyword_scraper: # Also enter the KeywordScraper's context if it exists
            await self.keyword_scraper.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for KeywordService."""
        self.logger.debug("Exiting KeywordService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.keyword_scraper: # Also exit the KeywordScraper's context if it exists
            await self.keyword_scraper.__aexit__(exc_type, exc_val, exc_tb)

    async def get_keyword_data(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Fetches keyword suggestions for a given seed keyword.
        Prioritizes the local KeywordScraper if available, otherwise uses the API client.
        """
        if self.keyword_scraper:
            self.logger.info(f"Using KeywordScraper to fetch keyword data for '{seed_keyword}'.")
            return await self.keyword_scraper.get_keyword_data(seed_keyword, num_suggestions)
        else:
            self.logger.info(f"Using Keyword API client to fetch keyword data for '{seed_keyword}'.")
            return await self.api_client.get_keyword_suggestions(seed_keyword, num_suggestions)
