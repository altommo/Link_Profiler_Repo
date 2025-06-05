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
import json # Import json for caching
import redis.asyncio as redis # Import redis for type hinting

from Link_Profiler.core.models import SERPResult, SEOMetrics # Absolute import CrawlResult
from Link_Profiler.crawlers.serp_crawler import SERPCrawler # New import
from Link_Profiler.config.config_loader import config_loader # New import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited # Import the rate limiter
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager
from Link_Profiler.clients.google_pagespeed_client import PageSpeedClient # New: Import PageSpeedClient
from Link_Profiler.monitoring.prometheus_metrics import API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL # Import Prometheus metrics
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager

logger = logging.getLogger(__name__)

class BaseSERPAPIClient:
    """
    Base class for a SERP API client.
    Real implementations would connect to external services like Google Search API, SerpApi, etc.
    """
    async def get_serp_results(self, keyword: str, num_results: int = 10, search_engine: str = "google") -> List[SERPResult]:
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
    def __init__(self, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__ + ".SimulatedSERPAPIClient")
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to SimulatedSERPAPIClient. Falling back to local SessionManager.")

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedSERPAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedSERPAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def get_serp_results(self, keyword: str, num_results: int = 10, search_engine: str = "google") -> List[SERPResult]:
        """
        Simulates fetching SERP results for a given keyword.
        """
        self.logger.info(f"Simulating API call for SERP results for keyword: '{keyword}' from {search_engine}")
        
        try:
            # Simulate an actual HTTP request, even if it's to a dummy URL
            async with await self.session_manager.get(f"http://localhost:8080/simulate_serp/{keyword}") as response:
                # We don't care about the actual response, just that the request was made
                pass
        except aiohttp.ClientConnectorError:
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated SERP fetch: {e}")

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
    This implementation demonstrates where actual API calls would go.
    """
    def __init__(self, api_key: str, base_url: str, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__ + ".RealSERPAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to RealSERPAPIClient. Falling back to local SessionManager.")

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealSERPAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealSERPAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="serp_api", api_client_type="real_api", endpoint="search")
    async def get_serp_results(self, keyword: str, num_results: int = 10, search_engine: str = "google") -> List[SERPResult]:
        """
        Fetches SERP results for a given keyword from a real API.
        Replace with actual API call logic for your chosen provider.
        """
        # Example for SerpApi: https://serpapi.com/search-api
        # Example for BrightData SERP API: https://brightdata.com/products/serp-api
        
        endpoint = f"{self.base_url}/search" # Hypothetical endpoint
        params = {
            "q": keyword,
            "num": num_results,
            "engine": search_engine, # Pass search engine
            "api_key": self.api_key # Some APIs use query param for key
        }
        self.logger.info(f"Attempting real API call for SERP results: {endpoint}?q={keyword} from {search_engine}...")

        try:
            async with await self.session_manager.get(endpoint, params=params) as response:
                response.raise_for_status() # Raise an exception for HTTP errors
                data = await response.json()
                
                serp_results = []
                # --- Replace with actual parsing logic for your chosen API ---
                # Example: assuming 'organic_results' key with list of dicts
                # for i, item in enumerate(data.get("organic_results", [])):
                #     serp_results.append(
                #         SERPResult(
                #             keyword=keyword,
                #             position=item.get("position", i + 1),
                #             result_url=item.get("link"),
                #             title_text=item.get("title"),
                #             snippet_text=item.get("snippet"),
                #             rich_features=item.get("rich_features", []), # Assuming API provides this
                #             page_load_time=item.get("page_load_time"), # Assuming API provides this
                #             crawl_timestamp=datetime.now()
                #         )
                #     )
                self.logger.warning("RealSERPAPIClient: Returning simulated data. Replace with actual API response parsing.")
                return SimulatedSERPAPIClient(session_manager=self.session_manager).get_serp_results(keyword, num_results, search_engine) # Fallback to simulation

        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real SERP results for '{keyword}': {e}. Returning empty list.")
            return [] # Return empty list on network/client error
        except Exception as e:
            self.logger.error(f"Unexpected error in real SERP fetch for '{keyword}': {e}. Returning empty list.")
            return []


class SERPService:
    """
    Service for fetching Search Engine Results Page (SERP) data.
    """
    def __init__(self, api_client: Optional[BaseSERPAPIClient] = None, serp_crawler: Optional[SERPCrawler] = None, pagespeed_client: Optional[PageSpeedClient] = None, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600, session_manager: Optional[SessionManager] = None): # New: Accept session_manager
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.api_cache_enabled = config_loader.get("api_cache.enabled", False)
        self.session_manager = session_manager # Store the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to SERPService. Falling back to local SessionManager.")
        
        # Determine which API client to use based on config_loader priority
        if config_loader.get("serp_api.real_api.enabled"):
            real_api_key = config_loader.get("serp_api.real_api.api_key")
            real_api_base_url = config_loader.get("serp_api.real_api.base_url")
            if not real_api_key or not real_api_base_url:
                self.logger.error("Real SERP API enabled but API key or base_url not found in config. Falling back to simulated SERP API.")
                self.api_client = SimulatedSERPAPIClient(session_manager=self.session_manager)
            else:
                self.logger.info("Using RealSERPAPIClient for SERP lookups.")
                self.api_client = RealSERPAPIClient(api_key=real_api_key, base_url=real_api_base_url, session_manager=self.session_manager)
        else:
            self.logger.info("Using SimulatedSERPAPIClient for SERP lookups.")
            self.api_client = SimulatedSERPAPIClient(session_manager=self.session_manager)
            
        self.serp_crawler = serp_crawler # Store the SERPCrawler instance
        self.pagespeed_client = pagespeed_client # New: Store PageSpeedClient instance

    async def __aenter__(self):
        """Async context manager entry for SERPService."""
        self.logger.debug("Entering SERPService context.")
        await self.api_client.__aenter__()
        if self.serp_crawler: # Also enter the SERPCrawler's context if it exists
            await self.serp_crawler.__aenter__()
        if self.pagespeed_client: # New: Enter PageSpeedClient's context
            await self.pagespeed_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for SERPService."""
        self.logger.debug("Exiting SERPService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.serp_crawler: # Also exit the SERPCrawler's context if it exists
            await self.serp_crawler.__aexit__(exc_type, exc_val, exc_tb)
        if self.pagespeed_client: # New: Exit PageSpeedClient's context
            await self.pagespeed_client.__aexit__(exc_type, exc_val, exc_tb)

    async def _get_cached_response(self, cache_key: str, service_name: str, endpoint_name: str) -> Optional[Any]:
        if self.api_cache_enabled and self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    API_CACHE_HITS_TOTAL.labels(service=service_name, endpoint=endpoint_name).inc()
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
                else:
                    API_CACHE_MISSES_TOTAL.labels(service=service_name, endpoint=endpoint_name).inc()
            except Exception as e:
                API_CACHE_ERRORS_TOTAL.labels(service=service_name, endpoint=endpoint_name, error_type=type(e).__name__).inc()
                self.logger.error(f"Error retrieving from cache for {cache_key}: {e}", exc_info=True)
        return None

    async def _set_cached_response(self, cache_key: str, data: Any, service_name: str, endpoint_name: str):
        if self.api_cache_enabled and self.redis_client:
            try:
                await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
                API_CACHE_SET_TOTAL.labels(service=service_name, endpoint=endpoint_name).inc()
                self.logger.debug(f"Cached {cache_key} with TTL {self.cache_ttl}")
            except Exception as e:
                API_CACHE_ERRORS_TOTAL.labels(service=service_name, endpoint=endpoint_name, error_type=type(e).__name__).inc()
                self.logger.error(f"Error setting cache for {cache_key}: {e}", exc_info=True)

    async def get_serp_data(self, keyword: str, num_results: int = 10, search_engine: str = "google") -> List[SERPResult]:
        """
        Fetches SERP data for a given keyword.
        Prioritizes the local SERPCrawler if available, otherwise uses the API client.
        Uses caching.
        """
        cache_key = f"serp_data:{keyword}:{num_results}:{search_engine}"
        cached_result = await self._get_cached_response(cache_key, "serp_api", "get_serp_data")
        if cached_result is not None:
            return [SERPResult.from_dict(sr_data) for sr_data in cached_result]

        serp_results: List[SERPResult] = []
        if self.serp_crawler and config_loader.get("serp_crawler.playwright.enabled"):
            self.logger.info(f"Using SERPCrawler to fetch SERP data for '{keyword}' from {search_engine}.")
            serp_results = await self.serp_crawler.get_serp_data(keyword, num_results, search_engine)
        else:
            self.logger.info(f"Using SERP API client to fetch SERP data for '{keyword}'.")
            serp_results = await self.api_client.get_serp_results(keyword, num_results, search_engine)
        
        if serp_results:
            await self._set_cached_response(cache_key, [sr.to_dict() for sr in serp_results], "serp_api", "get_serp_data") # Cache as list of dicts
        return serp_results

    async def get_pagespeed_metrics_for_url(self, url: str, strategy: str = 'mobile') -> Optional[SEOMetrics]:
        """
        Fetches PageSpeed Insights metrics for a given URL and converts them to SEOMetrics.
        """
        if not self.pagespeed_client or not self.pagespeed_client.enabled:
            self.logger.warning("PageSpeed Insights client is not enabled. Cannot fetch PageSpeed metrics.")
            return None
        
        self.logger.info(f"Fetching PageSpeed Insights metrics for {url} ({strategy}).")
        pagespeed_data = await self.pagespeed_client.analyze_url(url, strategy)

        if not pagespeed_data:
            self.logger.warning(f"No PageSpeed data returned for {url}.")
            return None

        # Parse PageSpeed data into SEOMetrics format
        lighthouse_result = pagespeed_data.get("lighthouseResult", {})
        categories = lighthouse_result.get("categories", {})
        audits = lighthouse_result.get("audits", {})

        seo_metrics = SEOMetrics(
            url=url,
            http_status=200, # PageSpeed API doesn't directly give HTTP status of the URL itself
            response_time_ms=audits.get("server-response-time", {}).get("numericValue"),
            performance_score=categories.get("performance", {}).get("score") * 100 if categories.get("performance", {}).get("score") is not None else None,
            mobile_friendly=True, # PageSpeed API doesn't directly give a boolean, but performance score implies it
            accessibility_score=categories.get("accessibility", {}).get("score") * 100 if categories.get("accessibility", {}).get("score") is not None else None,
            seo_score=categories.get("seo", {}).get("score") * 100 if categories.get("seo", {}).get("score") is not None else None,
            audit_timestamp=datetime.fromisoformat(pagespeed_data.get("analysisUTCTimestamp").replace('Z', '+00:00')) if pagespeed_data.get("analysisUTCTimestamp") else None,
            # Populate other fields from PageSpeed data if available and relevant
            title_length=len(audits.get("title-text", {}).get("displayValue", "")) if audits.get("title-text") else 0,
            meta_description_length=len(audits.get("meta-description", {}).get("displayValue", "")) if audits.get("meta-description") else 0,
            has_canonical=audits.get("canonical", {}).get("score", 1) == 1, # Score 1 means passed
            has_robots_meta=audits.get("robots-txt", {}).get("score", 1) == 1, # Score 1 means passed
            has_schema_markup=audits.get("structured-data", {}).get("score", 0) == 1, # Score 1 means passed
            # Broken links are not directly provided by PageSpeed, but can be inferred from failed requests
            # Page size is also not directly provided in a simple metric, needs to be calculated from network requests
        )
        seo_metrics.calculate_seo_score() # Recalculate overall SEO score based on new data
        return seo_metrics
