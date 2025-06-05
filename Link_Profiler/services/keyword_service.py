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
from Link_Profiler.clients.google_trends_client import GoogleTrendsClient # New: Import GoogleTrendsClient
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.monitoring.prometheus_metrics import API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL # Import Prometheus metrics
from Link_Profiler.database.database import Database # Import Database for DB operations

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
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__ + ".SimulatedKeywordAPIClient")
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to SimulatedKeywordAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to SimulatedKeywordAPIClient. Falling back to global instance.")


    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedKeywordAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedKeywordAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="keyword_api", api_client_type="simulated_api", endpoint="get_keyword_suggestions")
    async def get_keyword_suggestions(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Simulates fetching keyword suggestions for a given seed keyword.
        """
        self.logger.info(f"Simulating API call for keyword suggestions for seed: '{seed_keyword}'")
        
        try:
            # Simulate an actual HTTP request, even if it's to a dummy URL
            # Use resilience manager for the actual HTTP request
            await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(f"http://localhost:8080/simulate_keywords/{seed_keyword}"),
                url=f"http://localhost:8080/simulate_keywords/{seed_keyword}" # Pass the URL for circuit breaker naming
            )
        except aiohttp.ClientConnectorError:
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated keyword fetch: {e}")

        suggestions = []
        for i in range(num_suggestions):
            suggested_keyword = f"{seed_keyword} {random.choice(['ideas', 'tools', 'analysis', 'strategy'])} {i+1}"
            search_volume = random.randint(100, 10000)
            cpc_estimate = round(random.uniform(0.5, 5.0), 2)
            
            suggestions.append(
                KeywordSuggestion(
                    keyword=suggested_keyword,
                    search_volume=search_volume,
                    cpc=cpc_estimate,
                    competition=random.uniform(0.1, 0.9), # Competition as float 0-1
                    difficulty=random.randint(1, 100), # Difficulty as int 0-100
                    relevance=random.uniform(0.5, 1.0),
                    source="Simulated",
                    last_fetched_at=datetime.utcnow() # Set last_fetched_at for simulated data
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
    def __init__(self, api_key: str, base_url: str, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__ + ".RealKeywordAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to RealKeywordAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to RealKeywordAPIClient. Falling back to global instance.")


    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealKeywordAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealKeywordAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

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

        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(endpoint, params=params, timeout=30),
                url=endpoint # Pass the endpoint for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            
            suggestions = []
            # --- Replace with actual parsing logic for your chosen API ---
            # Example: assuming 'suggestions' key with list of dicts
            for item in data.get("suggestions", []):
                suggestions.append(
                    KeywordSuggestion(
                        keyword=item.get("keyword"),
                        search_volume=item.get("search_volume"),
                        cpc=item.get("cpc"),
                        competition=item.get("competition"),
                        difficulty=item.get("difficulty"),
                        relevance=item.get("relevance"),
                        source=item.get("source", "RealAPI"),
                        last_fetched_at=datetime.utcnow() # Set last_fetched_at for live data
                    )
                )
            self.logger.info(f"RealKeywordAPIClient: Fetched {len(suggestions)} keyword suggestions for '{seed_keyword}'.")
            return suggestions

        except Exception as e:
            self.logger.error(f"Error fetching real keyword suggestions for '{seed_keyword}': {e}. Returning empty list.", exc_info=True)
            return []

class RealKeywordMetricsAPIClient(BaseKeywordAPIClient):
    """
    A client for a real Keyword Metrics API (e.g., Ahrefs, SEMrush, Google Ads API).
    This client would fetch search volume, CPC, and competition level.
    This implementation demonstrates where actual API calls would go.
    """
    def __init__(self, api_key: str, base_url: str, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__ + ".RealKeywordMetricsAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to RealKeywordMetricsAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to RealKeywordMetricsAPIClient. Falling back to global instance.")


    async def __aenter__(self):
        self.logger.info("Entering RealKeywordMetricsAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("Exiting RealKeywordMetricsAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="keyword_api", api_client_type="metrics_api", endpoint="get_metrics")
    async def get_keyword_metrics(self, keyword: str) -> Dict[str, Any]:
        """
        Fetches detailed metrics for a single keyword from a real API.
        Replace with actual API call logic for your chosen provider.
        """
        endpoint = f"{self.base_url}/metrics" # Hypothetical endpoint
        params = {"keyword": keyword, "apiKey": self.api_key}
        self.logger.info(f"Attempting real API call for keyword metrics: {endpoint}?keyword={keyword}...")

        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(endpoint, params=params, timeout=10),
                url=endpoint # Pass the endpoint for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            # --- Replace with actual parsing logic for your chosen API ---
            # Example:
            return {
                "search_volume": data.get("volume"),
                "cpc": data.get("cpc"),
                "competition": data.get("competition"),
                "difficulty": data.get("difficulty"),
                "relevance": data.get("relevance"),
                "source": data.get("source", "RealMetricsAPI"),
                "last_fetched_at": datetime.utcnow() # Set last_fetched_at for live data
            }
        except Exception as e:
            self.logger.error(f"Error fetching real keyword metrics for '{keyword}': {e}. Returning empty metrics.", exc_info=True)
            return {}

    # This client doesn't provide suggestions, only metrics for given keywords
    async def get_keyword_suggestions(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        raise NotImplementedError("This client is for metrics, not suggestions.")


class KeywordService:
    """
    Service for fetching Keyword Research data.
    """
    def __init__(self, database: Optional[Database] = None, api_client: Optional[BaseKeywordAPIClient] = None, keyword_scraper: Optional[KeywordScraper] = None, google_trends_client: Optional[GoogleTrendsClient] = None, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__)
        self.db = database # Store database instance
        self.session_manager = session_manager # Store the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to KeywordService. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to KeywordService. Falling back to global instance.")

        # Determine which API client to use based on config_loader priority
        if config_loader.get("keyword_api.real_api.enabled"):
            real_api_key = config_loader.get("keyword_api.real_api.api_key")
            real_api_base_url = config_loader.get("keyword_api.real_api.base_url")
            if not real_api_key or not real_api_base_url:
                self.logger.error("Real Keyword API enabled but API key or base_url not found in config. Falling back to simulated Keyword API.")
                self.api_client = SimulatedKeywordAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)
            else:
                self.logger.info("Using RealKeywordAPIClient for keyword lookups.")
                self.api_client = RealKeywordAPIClient(api_key=real_api_key, base_url=real_api_base_url, session_manager=self.session_manager, resilience_manager=self.resilience_manager)
        else:
            self.logger.info("Using SimulatedKeywordAPIClient for keyword lookups.")
            self.api_client = SimulatedKeywordAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)
            
        self.keyword_scraper = keyword_scraper # Store the KeywordScraper instance
        self.google_trends_client = google_trends_client # New: Store GoogleTrendsClient instance
        
        # Initialize the metrics API client separately
        self.metrics_api_client: Optional[RealKeywordMetricsAPIClient] = None
        if config_loader.get("keyword_api.metrics_api.enabled"):
            metrics_api_key = config_loader.get("keyword_api.metrics_api.api_key")
            metrics_api_base_url = config_loader.get("keyword_api.metrics_api.base_url")
            if not metrics_api_key or not metrics_api_base_url:
                self.logger.error("Real Keyword Metrics API enabled but API key or base_url not found in config. Metrics will be simulated.")
            else:
                self.logger.info("Using RealKeywordMetricsAPIClient for keyword metrics.")
                self.metrics_api_client = RealKeywordMetricsAPIClient(api_key=metrics_api_key, base_url=metrics_api_base_url, session_manager=self.session_manager, resilience_manager=self.resilience_manager)

        self.allow_live = config_loader.get("keyword_api.keyword_service.allow_live", False)
        self.staleness_threshold = timedelta(hours=config_loader.get("keyword_api.keyword_service.staleness_threshold_hours", 24))

    async def __aenter__(self):
        """Async context manager entry for KeywordService."""
        self.logger.debug("Entering KeywordService context.")
        await self.api_client.__aenter__()
        if self.keyword_scraper: # Also enter the KeywordScraper's context if it exists
            await self.keyword_scraper.__aenter__()
        if self.metrics_api_client: # Enter metrics client's context
            await self.metrics_api_client.__aenter__()
        if self.google_trends_client: # New: Enter GoogleTrendsClient's context
            await self.google_trends_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for KeywordService."""
        self.logger.debug("Exiting KeywordService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.keyword_scraper: # Also exit the KeywordScraper's context if it exists
            await self.keyword_scraper.__aexit__(exc_type, exc_val, exc_tb)
        if self.metrics_api_client: # Exit metrics client's context
            await self.metrics_api_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.google_trends_client: # New: Exit GoogleTrendsClient's context
            await self.google_trends_client.__aexit__(exc_type, exc_val, exc_tb)

    async def _fetch_live_keyword_data(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Fetches keyword suggestions and enriches them with metrics directly from external APIs/scrapers.
        This method is intended for internal use by the service when a live fetch is required.
        """
        self.logger.info(f"Fetching LIVE keyword data for '{seed_keyword}'.")
        suggestions: List[KeywordSuggestion] = []
        
        if self.keyword_scraper and config_loader.get("keyword_scraper.enabled"):
            self.logger.info(f"Using KeywordScraper to fetch LIVE keyword suggestions for '{seed_keyword}'.")
            suggestions = await self.keyword_scraper.get_keyword_data(seed_keyword, num_suggestions)
        else:
            self.logger.info(f"Using Keyword API client to fetch LIVE keyword suggestions for '{seed_keyword}'.")
            # Assuming self.api_client (Simulated/RealKeywordAPIClient) can get suggestions
            suggestions = await self.api_client.get_keyword_suggestions(seed_keyword, num_suggestions)
        
        # Enrich suggestions with metrics if metrics API client is enabled
        if self.metrics_api_client and config_loader.get("keyword_api.metrics_api.enabled"):
            self.logger.info(f"Enriching LIVE keyword suggestions with metrics using RealKeywordMetricsAPIClient.")
            for suggestion in suggestions:
                metrics = await self.metrics_api_client.get_keyword_metrics(suggestion.keyword)
                if metrics:
                    suggestion.search_volume = metrics.get("search_volume", suggestion.search_volume)
                    suggestion.cpc = metrics.get("cpc", suggestion.cpc)
                    suggestion.competition = metrics.get("competition", suggestion.competition)
                    suggestion.difficulty = metrics.get("difficulty", suggestion.difficulty)
                    suggestion.relevance = metrics.get("relevance", suggestion.relevance)
                    suggestion.source = metrics.get("source", suggestion.source)
        else:
            self.logger.info("Keyword metrics API not enabled or configured. Using simulated metrics for LIVE fetch.")
            # If metrics API is not enabled, ensure simulated values are present
            for suggestion in suggestions:
                if suggestion.search_volume is None:
                    suggestion.search_volume = random.randint(100, 10000)
                if suggestion.cpc is None:
                    suggestion.cpc = round(random.uniform(0.5, 5.0), 2)
                if suggestion.competition is None:
                    suggestion.competition = random.uniform(0.1, 0.9)
                if suggestion.difficulty is None:
                    suggestion.difficulty = random.randint(1, 100)
                if suggestion.relevance is None:
                    suggestion.relevance = random.uniform(0.5, 1.0)
                if suggestion.source is None:
                    suggestion.source = "Simulated"

        # New: Fetch keyword trends using GoogleTrendsClient if enabled
        if self.google_trends_client and self.google_trends_client.enabled and suggestions:
            self.logger.info(f"Fetching LIVE Google Trends for top suggestions for '{seed_keyword}'.")
            # Only fetch trends for the top 5 keywords to avoid hitting limits
            keywords_for_trends = [s.keyword for s in suggestions[:5]]
            if keywords_for_trends:
                trends_data = await self.google_trends_client.get_interest_over_time(keywords_for_trends)
                if trends_data: # trends_data is a dict of keyword -> list of floats
                    for suggestion in suggestions:
                        if suggestion.keyword in trends_data:
                            suggestion.keyword_trend = trends_data[suggestion.keyword]
                            self.logger.debug(f"Added LIVE trend data for {suggestion.keyword}.")
                else:
                    self.logger.warning(f"No LIVE trend data found from Google Trends for {keywords_for_trends}.")
            else:
                self.logger.info("No keywords to fetch trends for LIVE.")
        
        # Set last_fetched_at for all suggestions
        now = datetime.utcnow()
        for sug in suggestions:
            sug.last_fetched_at = now

        return suggestions

    async def get_keyword_data(self, seed_keyword: str, num_suggestions: int = 10, source: str = "cache") -> List[KeywordSuggestion]:
        """
        Retrieves keyword suggestions for a given seed keyword.
        Prioritizes cached data, but can fetch live if requested and allowed.
        """
        cached_suggestions = self.db.get_latest_keyword_suggestions_for_seed(seed_keyword)
        
        # Determine the latest fetch time from cached suggestions
        latest_fetched_at = None
        if cached_suggestions:
            latest_fetched_at = max((sug.last_fetched_at for sug in cached_suggestions if sug.last_fetched_at), default=None)
        
        now = datetime.utcnow()

        if source == "live" and self.allow_live:
            if not latest_fetched_at or (now - latest_fetched_at) > self.staleness_threshold:
                self.logger.info(f"Live fetch requested or cache stale for {seed_keyword}. Fetching live keyword data.")
                live_suggestions = await self._fetch_live_keyword_data(seed_keyword, num_suggestions)
                if live_suggestions:
                    self.db.add_keyword_suggestions(live_suggestions) # Save/update the fresh data
                    return live_suggestions
                else:
                    self.logger.warning(f"Live fetch failed for {seed_keyword}. Returning cached data if available.")
                    return cached_suggestions # Fallback to cache
            else:
                self.logger.info(f"Live fetch requested for {seed_keyword}, but cache is fresh. Fetching live anyway.")
                live_suggestions = await self._fetch_live_keyword_data(seed_keyword, num_suggestions)
                if live_suggestions:
                    self.db.add_keyword_suggestions(live_suggestions)
                    return live_suggestions
                else:
                    self.logger.warning(f"Live fetch failed for {seed_keyword}. Returning cached data.")
                    return cached_suggestions # Fallback to cache
        else:
            self.logger.info(f"Returning cached keyword data for {seed_keyword}.")
            return cached_suggestions
