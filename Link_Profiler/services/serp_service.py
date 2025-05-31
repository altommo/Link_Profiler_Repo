"""
SERP Service - Provides functionalities for fetching Search Engine Results Page (SERP) data.
File: Link_Profiler/services/serp_service.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp

from Link_Profiler.core.models import SERPResult # Absolute import
from Link_Profiler.crawlers.serp_crawler import SERPCrawler # New import
from Link_Profiler.config.config_loader import config_loader # Import config_loader

logger = logging.getLogger(__name__)

class BaseSERPAPIClient:
    """
    Base class for a SERP API client.
    Real implementations would connect to external services like Google Search API, SerpApi, etc.
    """
    async def get_serp_results(self, keyword: str, num_results: int = 10) -> List[SERPResult]:
        raise NotImplementedError

    async def __aenter__(self):
        """Async context manager entry for client session."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        pass # No-op for base class

class SimulatedSERPAPIClient(BaseSERPAPIClient):
    """
    A simulated client for SERP APIs.
    Generates dummy SERP data.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SimulatedSERPAPIClient")
        self._session: Optional[aiohttp.ClientSession] = None # For simulating network calls

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedSERPAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedSERPAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_serp_results(self, keyword: str, num_results: int = 10) -> List[SERPResult]:
        """
        Simulates fetching SERP results for a given keyword.
        """
        self.logger.info(f"Simulating API call for SERP results for keyword: '{keyword}'")
        
        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("SimulatedSERPAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession()
            close_session_after_use = True

        try:
            # Simulate an actual HTTP request, even if it's to a dummy URL
            async with session_to_use.get(f"http://localhost:8080/simulate_serp/{keyword}") as response:
                pass
        except aiohttp.ClientConnectorError:
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated SERP fetch: {e}")
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

        serp_results = []
        for i in range(num_results):
            position = i + 1
            result_url = f"https://example.com/search-result-{keyword.replace(' ', '-')}-{position}"
            title_text = f"Best {keyword} - Result {position}"
            snippet_text = f"This is a simulated snippet for {keyword} at position {position}. It provides relevant information."
            rich_features = []
            if position == 1 and random.random() > 0.5:
                rich_features.append("Featured Snippet")
            if position % 3 == 0:
                rich_features.append("Image Pack")
            
            serp_results.append(
                SERPResult(
                    keyword=keyword,
                    position=position,
                    result_url=result_url,
                    title_text=title_text,
                    snippet_text=snippet_text,
                    rich_features=rich_features,
                    page_load_time=round(random.uniform(0.5, 3.0), 2),
                    crawl_timestamp=datetime.now()
                )
            )
        self.logger.info(f"Simulated {len(serp_results)} SERP results for '{keyword}'.")
        return serp_results

class RealSERPAPIClient(BaseSERPAPIClient):
    """
    A client for a real SERP API (e.g., SerpApi, BrightData SERP API).
    Requires an API key.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.real-serp-provider.com"):
        self.logger = logging.getLogger(__name__ + ".RealSERPAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealSERPAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}"})
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealSERPAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_serp_results(self, keyword: str, num_results: int = 10) -> List[SERPResult]:
        """
        Fetches SERP results for a given keyword from a real API.
        This is a placeholder; replace with actual API call logic.
        """
        endpoint = f"{self.base_url}/search"
        params = {
            "q": keyword,
            "num": num_results,
            "api_key": self.api_key # Some APIs use query param for key
        }
        self.logger.info(f"Attempting real API call for SERP results: {endpoint}?q={keyword}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealSERPAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}"})
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                
                serp_results = []
                # Placeholder for parsing actual API response
                # Example: assuming 'organic_results' key with list of dicts
                for i, item in enumerate(data.get("organic_results", [])):
                    serp_results.append(
                        SERPResult(
                            keyword=keyword,
                            position=item.get("position", i + 1),
                            result_url=item.get("link"),
                            title_text=item.get("title"),
                            snippet_text=item.get("snippet"),
                            rich_features=item.get("rich_features", []), # Assuming API provides this
                            page_load_time=item.get("page_load_time"), # Assuming API provides this
                            crawl_timestamp=datetime.now()
                        )
                    )
                self.logger.info(f"RealSERPAPIClient: Found {len(serp_results)} SERP results for '{keyword}'.")
                return serp_results

        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real SERP results for '{keyword}': {e}. Returning empty list.")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in real SERP fetch for '{keyword}': {e}. Returning empty list.")
            return []
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()


class SERPService:
    """
    Service for fetching Search Engine Results Page (SERP) data.
    """
    def __init__(self, api_client: Optional[BaseSERPAPIClient] = None, serp_crawler: Optional[SERPCrawler] = None):
        self.logger = logging.getLogger(__name__)
        
        # Determine which API client to use based on config_loader priority
        if config_loader.get("serp_api.real_api.enabled"):
            real_api_key = config_loader.get("serp_api.real_api.api_key")
            if not real_api_key:
                self.logger.error("Real SERP API enabled but API key not found in config. Falling back to simulated SERP API.")
                self.api_client = SimulatedSERPAPIClient()
            else:
                self.logger.info("Using RealSERPAPIClient for SERP lookups.")
                self.api_client = RealSERPAPIClient(api_key=real_api_key)
        else:
            self.logger.info("Using SimulatedSERPAPIClient for SERP lookups.")
            self.api_client = SimulatedSERPAPIClient()
            
        self.serp_crawler = serp_crawler # Store the SERPCrawler instance

    async def __aenter__(self):
        """Async context manager entry for SERPService."""
        self.logger.debug("Entering SERPService context.")
        await self.api_client.__aenter__()
        if self.serp_crawler: # Also enter the SERPCrawler's context if it exists
            await self.serp_crawler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for SERPService."""
        self.logger.debug("Exiting SERPService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.serp_crawler: # Also exit the SERPCrawler's context if it exists
            await self.serp_crawler.__aexit__(exc_type, exc_val, exc_tb)

    async def get_serp_data(self, keyword: str, num_results: int = 10, search_engine: str = "google") -> List[SERPResult]:
        """
        Fetches SERP data for a given keyword.
        Prioritizes the local SERPCrawler if available, otherwise uses the API client.
        """
        if self.serp_crawler and config_loader.get("serp_crawler.playwright.enabled"):
            self.logger.info(f"Using SERPCrawler to fetch SERP data for '{keyword}' from {search_engine}.")
            return await self.serp_crawler.get_serp_data(keyword, num_results, search_engine)
        else:
            self.logger.info(f"Using SERP API client to fetch SERP data for '{keyword}'.")
            # The API client's get_serp_results method does not take 'search_engine' as an argument.
            # It's assumed the API client is configured for a specific search engine or handles it internally.
            return await self.api_client.get_serp_results(keyword, num_results)
