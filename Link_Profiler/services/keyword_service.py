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
import json # Import json for caching
import redis.asyncio as redis # Import redis for caching

from Link_Profiler.core.models import KeywordSuggestion # Absolute import
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper # New import
from Link_Profiler.config.config_loader import config_loader # Import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited # Import the rate limiter
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager

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
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            self._session = aiohttp.ClientSession(headers=headers)
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
            
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
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
    This implementation demonstrates where actual API calls would go.
    """
    def __init__(self, api_key: str, base_url: str):
        self.logger = logging.getLogger(__name__ + ".RealKeywordAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealKeywordAPIClient context.")
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self.api_key}"} # Common header for API keys
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealKeywordAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @api_rate_limited(service="keyword_api", api_client_type="real_api", endpoint="suggestions")
    async def get_keyword_suggestions(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Fetches keyword suggestions for a given seed keyword from a real API.
        Replace with actual API call logic for your chosen provider.
        """
        endpoint = f"{self.base_url}/keywords/suggestions" # Hypothetical endpoint
        params = {
            "keyword": seed_keyword,
            "limit": num_suggestions,
            "apiKey": self.api_key # Some APIs use query param for key
        }
        self.logger.info(f"Attempting real API call for keyword suggestions: {endpoint}?keyword={seed_keyword}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealKeywordAPIClient: aiohttp session not active. Creating temporary session for this call.")
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                
                suggestions = []
                # --- Replace with actual parsing logic for your chosen API ---
                # Example: assuming 'suggestions' key with list of dicts
                # for item in data.get("suggestions", []):
                #     suggestions.append(
                #         KeywordSuggestion(
                #             seed_keyword=seed_keyword,
                #             suggested_keyword=item.get("keyword"),
                #             search_volume_monthly=item.get("search_volume"),
                #             cpc_estimate=item.get("cpc"),
                #             keyword_trend=item.get("trend", []),
                #             competition_level=item.get("competition"),
                #             data_timestamp=datetime.now()
                #         )
                #     )
                self.logger.warning("RealKeywordAPIClient: Returning simulated data. Replace with actual API response parsing.")
                return SimulatedKeywordAPIClient().get_keyword_suggestions(seed_keyword, num_suggestions) # Fallback to simulation

        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real keyword suggestions for '{seed_keyword}': {e}. Returning empty list.")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in real keyword fetch for '{seed_keyword}': {e}. Returning empty list.")
            return []
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

class RealKeywordMetricsAPIClient(BaseKeywordAPIClient):
    """
    A client for a real Keyword Metrics API (e.g., Ahrefs, SEMrush, Google Ads API).
    This client would fetch search volume, CPC, and competition level.
    This implementation demonstrates where actual API calls would go.
    """
    def __init__(self, api_key: str, base_url: str):
        self.logger = logging.getLogger(__name__ + ".RealKeywordMetricsAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.logger.info("Entering RealKeywordMetricsAPIClient context.")
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("Exiting RealKeywordMetricsAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @api_rate_limited(service="keyword_api", api_client_type="metrics_api", endpoint="get_metrics")
    async def get_keyword_metrics(self, keyword: str) -> Dict[str, Any]:
        """
        Fetches detailed metrics for a single keyword from a real API.
        Replace with actual API call logic for your chosen provider.
        """
        endpoint = f"{self.base_url}/metrics" # Hypothetical endpoint
        params = {"keyword": keyword, "apiKey": self.api_key}
        self.logger.info(f"Attempting real API call for keyword metrics: {endpoint}?keyword={keyword}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealKeywordMetricsAPIClient: aiohttp session not active. Creating temporary session for this call.")
            
            headers = {"Authorization": f"Bearer {self.api_key}"}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
            close_session_after_use = True

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                # --- Replace with actual parsing logic for your chosen API ---
                # Example:
                # return {
                #     "search_volume_monthly": data.get("volume"),
                #     "cpc_estimate": data.get("cpc"),
                #     "competition_level": data.get("competition")
                # }
                
                self.logger.warning("RealKeywordMetricsAPIClient: Returning simulated metrics. Replace with actual API response parsing.")
                # Simulate data for now
                domain_hash = sum(ord(c) for c in keyword.lower())
                return {
                    "search_volume_monthly": (domain_hash % 9900) + 100, # 100-10000
                    "cpc_estimate": round(random.uniform(0.5, 5.0), 2),
                    "competition_level": random.choice(["Low", "Medium", "High"])
                }
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real keyword metrics for '{keyword}': {e}. Returning empty metrics.")
            return {}
        except Exception as e:
            self.logger.error(f"Unexpected error in real keyword metrics fetch for '{keyword}': {e}. Returning empty metrics.")
            return {}
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

    # This client doesn't provide suggestions, only metrics for given keywords
    async def get_keyword_suggestions(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        raise NotImplementedError("This client is for metrics, not suggestions.")


class KeywordService:
    """
    Service for fetching Keyword Research data.
    """
    def __init__(self, api_client: Optional[BaseKeywordAPIClient] = None, keyword_scraper: Optional[KeywordScraper] = None, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600):
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.api_cache_enabled = config_loader.get("api_cache.enabled", False)
        
        # Determine which API client to use based on config_loader priority
        if config_loader.get("keyword_api.real_api.enabled"):
            real_api_key = config_loader.get("keyword_api.real_api.api_key")
            real_api_base_url = config_loader.get("keyword_api.real_api.base_url")
            if not real_api_key or not real_api_base_url:
                self.logger.error("Real Keyword API enabled but API key or base_url not found in config. Falling back to simulated Keyword API.")
                self.api_client = SimulatedKeywordAPIClient()
            else:
                self.logger.info("Using RealKeywordAPIClient for keyword lookups.")
                self.api_client = RealKeywordAPIClient(api_key=real_api_key, base_url=real_api_base_url)
        else:
            self.logger.info("Using SimulatedKeywordAPIClient for keyword lookups.")
            self.api_client = SimulatedKeywordAPIClient()
            
        self.keyword_scraper = keyword_scraper # Store the KeywordScraper instance
        
        # Initialize the metrics API client separately
        self.metrics_api_client: Optional[RealKeywordMetricsAPIClient] = None
        if config_loader.get("keyword_api.metrics_api.enabled"):
            metrics_api_key = config_loader.get("keyword_api.metrics_api.api_key")
            metrics_api_base_url = config_loader.get("keyword_api.metrics_api.base_url")
            if not metrics_api_key or not metrics_api_base_url:
                self.logger.error("Real Keyword Metrics API enabled but API key or base_url not found in config. Metrics will be simulated.")
            else:
                self.logger.info("Using RealKeywordMetricsAPIClient for keyword metrics.")
                self.metrics_api_client = RealKeywordMetricsAPIClient(api_key=metrics_api_key, base_url=metrics_api_base_url)

    async def __aenter__(self):
        """Async context manager entry for KeywordService."""
        self.logger.debug("Entering KeywordService context.")
        await self.api_client.__aenter__()
        if self.keyword_scraper: # Also enter the KeywordScraper's context if it exists
            await self.keyword_scraper.__aenter__()
        if self.metrics_api_client: # Enter metrics client's context
            await self.metrics_api_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for KeywordService."""
        self.logger.debug("Exiting KeywordService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.keyword_scraper: # Also exit the KeywordScraper's context if it exists
            await self.keyword_scraper.__aexit__(exc_type, exc_val, exc_tb)
        if self.metrics_api_client: # Exit metrics client's context
            await self.metrics_api_client.__aexit__(exc_type, exc_val, exc_tb)

    async def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        if self.api_cache_enabled and self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                self.logger.error(f"Error retrieving from cache for {cache_key}: {e}", exc_info=True)
        return None

    async def _set_cached_response(self, cache_key: str, data: Any):
        if self.api_cache_enabled and self.redis_client:
            try:
                await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
                self.logger.debug(f"Cached {cache_key} with TTL {self.cache_ttl}")
            except Exception as e:
                self.logger.error(f"Error setting cache for {cache_key}: {e}", exc_info=True)

    async def get_keyword_data(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Fetches keyword suggestions for a given seed keyword and enriches them with metrics.
        Prioritizes the local KeywordScraper if available, otherwise uses the API client.
        Uses caching.
        """
        cache_key = f"keyword_suggestions:{seed_keyword}:{num_suggestions}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result is not None:
            return [KeywordSuggestion.from_dict(ks_data) for ks_data in cached_result]

        suggestions: List[KeywordSuggestion] = []
        
        if self.keyword_scraper and config_loader.get("keyword_scraper.enabled"):
            self.logger.info(f"Using KeywordScraper to fetch keyword suggestions for '{seed_keyword}'.")
            suggestions = await self.keyword_scraper.get_keyword_data(seed_keyword, num_suggestions)
        else:
            self.logger.info(f"Using Keyword API client to fetch keyword suggestions for '{seed_keyword}'.")
            # Assuming self.api_client (Simulated/RealKeywordAPIClient) can get suggestions
            suggestions = await self.api_client.get_keyword_suggestions(seed_keyword, num_suggestions)
        
        # Enrich suggestions with metrics if metrics API client is enabled
        if self.metrics_api_client and config_loader.get("keyword_api.metrics_api.enabled"):
            self.logger.info(f"Enriching keyword suggestions with metrics using RealKeywordMetricsAPIClient.")
            for suggestion in suggestions:
                metrics_cache_key = f"keyword_metrics:{suggestion.suggested_keyword}"
                cached_metrics = await self._get_cached_response(metrics_cache_key)
                if cached_metrics:
                    metrics = cached_metrics
                else:
                    metrics = await self.metrics_api_client.get_keyword_metrics(suggestion.suggested_keyword)
                    if metrics:
                        await self._set_cached_response(metrics_cache_key, metrics)

                if metrics:
                    suggestion.search_volume_monthly = metrics.get("search_volume_monthly", suggestion.search_volume_monthly)
                    suggestion.cpc_estimate = metrics.get("cpc_estimate", suggestion.cpc_estimate)
                    suggestion.competition_level = metrics.get("competition_level", suggestion.competition_level)
        else:
            self.logger.info("Keyword metrics API not enabled or configured. Using simulated metrics.")
            # If metrics API is not enabled, ensure simulated values are present
            for suggestion in suggestions:
                if suggestion.search_volume_monthly is None:
                    suggestion.search_volume_monthly = random.randint(100, 10000)
                if suggestion.cpc_estimate is None:
                    suggestion.cpc_estimate = round(random.uniform(0.5, 5.0), 2)
                if suggestion.competition_level is None:
                    suggestion.competition_level = random.choice(["Low", "Medium", "High"])

        if suggestions:
            await self._set_cached_response(cache_key, [s.to_dict() for s in suggestions]) # Cache as list of dicts
        return suggestions
