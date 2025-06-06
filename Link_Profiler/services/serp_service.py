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
from urllib.parse import urlparse # Added missing import

from Link_Profiler.core.models import SERPResult, SEOMetrics # Absolute import CrawlResult
from Link_Profiler.crawlers.serp_crawler import SERPCrawler # New import
from Link_Profiler.config.config_loader import config_loader # New import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited # Import the rate limiter
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager
from Link_Profiler.clients.google_pagespeed_client import PageSpeedClient # New: Import PageSpeedClient
from Link_Profiler.monitoring.prometheus_metrics import API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL # Import Prometheus metrics
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # New: Import APIQuotaManager
from Link_Profiler.clients.serpstack_client import SerpstackClient # New: Import SerpstackClient
from Link_Profiler.clients.valueserp_client import ValueserpClient # New: Import ValueserpClient
from Link_Profiler.services.api_routing_service import APIRoutingService # New: Import APIRoutingService

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
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept ResilienceManager
        self.logger = logging.getLogger(__name__ + ".SimulatedSERPAPIClient")
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to SimulatedSERPAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to SimulatedSERPAPIClient. Falling back to global instance.")


    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedSERPAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedSERPAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="serp_api", api_client_type="simulated_api", endpoint="get_serp_results")
    async def get_serp_results(self, keyword: str, num_results: int = 10, search_engine: str = "google") -> List[SERPResult]:
        """
        Simulates fetching SERP results for a given keyword.
        """
        self.logger.info(f"Simulating API call for SERP results for keyword: '{keyword}' from {search_engine}.")
        
        try:
            # Simulate an actual HTTP request, even if it's to a dummy URL
            # Use resilience manager for the actual HTTP request
            await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(f"http://localhost:8080/simulate_serp/{keyword}"),
                url=f"http://localhost:8080/simulate_serp/{keyword}" # Pass the URL for circuit breaker naming
            )
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
            
            serp_results.append(
                SERPResult(
                    keyword=keyword,
                    rank=position,
                    url=result_url,
                    title=title_text,
                    snippet=snippet_text,
                    domain=urlparse(result_url).netloc,
                    position_type="organic",
                    timestamp=datetime.now()
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
    def __init__(self, api_key: str, base_url: str, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept ResilienceManager
        self.logger = logging.getLogger(__name__ + ".RealSERPAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to RealSERPAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to RealSERPAPIClient. Falling back to global instance.")


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
        Fetches SERP results for a given keyword from SerpApi.
        Implements proper SerpApi response parsing.
        """
        # SerpApi endpoint
        endpoint = self.base_url
        
        # SerpApi parameters
        params = {
            "q": keyword,
            "num": min(num_results, 100),  # SerpApi limits to 100 per request
            "engine": search_engine,
            "api_key": self.api_key,
            "hl": "en",  # Language
            "gl": "us",  # Country
            "start": 0,   # Starting position
            "safe": "off",  # Safe search
            "device": "desktop"  # Device type
        }
        
        # Add search engine specific parameters
        if search_engine == "google":
            params["google_domain"] = "google.com"
        elif search_engine == "bing":
            params["cc"] = "US"
        elif search_engine == "yahoo":
            params["yahoo_domain"] = "search.yahoo.com"
        
        self.logger.info(f"Attempting SerpApi call for SERP results: {keyword} from {search_engine}...")

        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(endpoint, params=params, timeout=60),
                url=endpoint
            )
            response.raise_for_status()
            data = await response.json()
            
            serp_results = []
            
            # Parse organic results
            organic_results = data.get("organic_results", [])
            for item in organic_results:
                try:
                    url = item.get("link")
                    if not url:
                        continue
                        
                    domain = urlparse(url).netloc if url else ""
                    
                    serp_result = SERPResult(
                        keyword=keyword,
                        rank=item.get("position", 0),
                        url=url,
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        domain=domain,
                        position_type="organic",
                        timestamp=datetime.now()
                    )
                    
                    # Add additional SerpApi specific data
                    if "rich_snippet" in item:
                        rich_snippet = item["rich_snippet"]
                        serp_result.snippet += f" | {rich_snippet.get('top', {}).get('extensions', '')}"
                    
                    serp_results.append(serp_result)
                    
                except Exception as parse_error:
                    self.logger.warning(f"Error parsing organic result: {parse_error}")
                    continue
            
            # Parse paid/ads results if available
            ads_results = data.get("ads", [])
            for item in ads_results:
                try:
                    url = item.get("link")
                    if not url:
                        continue
                        
                    domain = urlparse(url).netloc if url else ""
                    
                    serp_result = SERPResult(
                        keyword=keyword,
                        rank=item.get("position", 0),
                        url=url,
                        title=item.get("title", ""),
                        snippet=item.get("snippet", ""),
                        domain=domain,
                        position_type="ad",
                        timestamp=datetime.now()
                    )
                    
                    serp_results.append(serp_result)
                    
                except Exception as parse_error:
                    self.logger.warning(f"Error parsing ad result: {parse_error}")
                    continue
            
            # Parse knowledge graph if available
            knowledge_graph = data.get("knowledge_graph")
            if knowledge_graph:
                try:
                    url = knowledge_graph.get("website")
                    if url:
                        domain = urlparse(url).netloc if url else ""
                        
                        serp_result = SERPResult(
                            keyword=keyword,
                            rank=0,  # Knowledge graph doesn't have traditional ranking
                            url=url,
                            title=knowledge_graph.get("title", ""),
                            snippet=knowledge_graph.get("description", ""),
                            domain=domain,
                            position_type="knowledge_graph",
                            timestamp=datetime.now()
                        )
                        
                        serp_results.append(serp_result)
                        
                except Exception as parse_error:
                    self.logger.warning(f"Error parsing knowledge graph: {parse_error}")
            
            # Sort results by rank for organic results
            organic_results_only = [r for r in serp_results if r.position_type == "organic"]
            other_results = [r for r in serp_results if r.position_type != "organic"]
            organic_results_only.sort(key=lambda x: x.rank)
            
            final_results = organic_results_only + other_results
            
            self.logger.info(f"RealSERPAPIClient: Fetched {len(final_results)} SERP results for '{keyword}' from SerpApi.")
            return final_results[:num_results]  # Limit to requested number

        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                self.logger.error(f"SerpApi authentication failed. Check your API key.")
            elif e.status == 429:
                self.logger.error(f"SerpApi rate limit exceeded.")
            elif e.status == 402:
                self.logger.error(f"SerpApi quota exceeded or subscription issue.")
            else:
                self.logger.error(f"SerpApi HTTP error {e.status}: {e.message}")
            raise # Re-raise to trigger fallback in APIRoutingService
        except Exception as e:
            self.logger.error(f"Error fetching SerpApi results for '{keyword}': {e}.", exc_info=True)
            raise # Re-raise to trigger fallback in APIRoutingService


class SERPService:
    """
    Service for fetching Search Engine Results Page (SERP) data.
    """
    def __init__(self, api_client: Optional[BaseSERPAPIClient] = None, serp_crawler: Optional[SERPCrawler] = None, pagespeed_client: Optional[PageSpeedClient] = None, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None, api_routing_service: Optional[APIRoutingService] = None): # New: Accept APIRoutingService
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.api_cache_enabled = config_loader.get("api_cache.enabled", False)
        self.session_manager = session_manager # Store the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to SERPService. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to SERPService. Falling back to global instance.")

        self.api_quota_manager = api_quota_manager
        if self.api_quota_manager is None:
            from Link_Profiler.utils.api_quota_manager import api_quota_manager as global_api_quota_manager
            self.api_quota_manager = global_api_quota_manager
            logger.warning("No APIQuotaManager provided to SERPService. Falling back to global instance.")

        self.api_routing_service = api_routing_service # New: Store APIRoutingService
        if self.api_routing_service is None:
            # This service is enabled but no APIRoutingService was provided.
            # This indicates a configuration error or missing dependency injection.
            raise ValueError(f"{self.__class__.__name__} is enabled but no APIRoutingService was provided.")

        # Initialize all potential SERP API clients
        self._serp_clients: Dict[str, BaseSERPAPIClient] = {
            "simulated_serp_search": SimulatedSERPAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)
        }
        if config_loader.get("external_apis.serpstack.enabled"):
            self._serp_clients["serpstack"] = SerpstackClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager, api_quota_manager=self.api_quota_manager)
        if config_loader.get("external_apis.valueserp.enabled"):
            self._serp_clients["valueserp"] = ValueserpClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager, api_quota_manager=self.api_quota_manager)
        # Add other real SERP API clients here if they exist in config

        self.serp_crawler = serp_crawler # Store the SERPCrawler instance
        self.pagespeed_client = pagespeed_client # New: Store PageSpeedClient instance

    async def __aenter__(self):
        """Enter context for all underlying API clients."""
        self.logger.debug("Entering SERPService context.")
        for client in self._serp_clients.values():
            await client.__aenter__()
        if self.serp_crawler: # Also enter the SERPCrawler's context if it exists
            await self.serp_crawler.__aenter__()
        if self.pagespeed_client: # New: Enter PageSpeedClient's context
            await self.pagespeed_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context for all underlying API clients."""
        self.logger.debug("Exiting SERPService context.")
        for client in self._serp_clients.values():
            await client.__aexit__(exc_type, exc_val, exc_tb)
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

    async def get_serp_data(self, keyword: str, num_results: int = 10, search_engine: str = "google", optimize_for_cost: bool = False) -> List[SERPResult]:
        """
        Fetches SERP data for a given keyword, applying a multi-tiered fallback strategy.
        Prioritizes the local SERPCrawler if available, then uses APIRoutingService for external API selection,
        and finally falls back to simulated data.
        """
        cache_key = f"serp_data:{keyword}:{num_results}:{search_engine}"
        cached_result = await self._get_cached_response(cache_key, "serp_api", "get_serp_data")
        if cached_result is not None:
            return [SERPResult.from_dict(sr_data) for sr_data in cached_result]

        serp_results: List[SERPResult] = []

        # Tier 1: Try SERPCrawler first if enabled
        if self.serp_crawler and config_loader.get("serp_crawler.playwright.enabled"):
            try:
                self.logger.info(f"Attempting to fetch SERP data via SERPCrawler for '{keyword}'.")
                serp_results = await self.serp_crawler.get_serp_data(keyword, num_results, search_engine)
                if serp_results:
                    self.logger.info(f"Successfully fetched SERP results via SERPCrawler for '{keyword}'.")
                    await self._set_cached_response(cache_key, [sr.to_dict() for sr in serp_results], "serp_api", "get_serp_data_crawler")
                    return serp_results
            except Exception as e:
                self.logger.warning(f"SERP Crawler failed for '{keyword}': {e}. Proceeding to external API fallback.")

        # Tier 2: Use APIRoutingService to select and try external APIs
        try:
            self.logger.info(f"Routing SERP data request for '{keyword}' via APIRoutingService.")
            # The api_call_func needs to be a partial function or lambda that takes the client instance
            # and then the specific arguments for the client's method.
            serp_results = await self.api_routing_service.route_api_call(
                query_type="serp_search",
                api_call_func=lambda client, **k: client.search(**k), # client.search(query, num_results, search_engine)
                api_name_prefix="serp", # Used to identify relevant clients (serpstack, valueserp, simulated_serp_search)
                optimize_for_cost=optimize_for_cost,
                ml_enabled=config_loader.get("api_routing.ml_enabled", False),
                query=keyword, # Pass actual arguments for client.search
                num_results=num_results,
                search_engine=search_engine
            )
            if serp_results:
                await self._set_cached_response(cache_key, [sr.to_dict() for sr in serp_results], "serp_api", "get_serp_data_routed")
                return serp_results
        except Exception as e:
            self.logger.error(f"APIRoutingService failed to route SERP data for '{keyword}': {e}. Falling back to simulated data.", exc_info=True)

        # Tier 3: Final Fallback to simulated data if all real APIs and crawler failed
        self.logger.info(f"All real SERP data sources failed for '{keyword}'. Falling back to simulated data.")
        simulated_client = self._serp_clients["simulated_serp_search"] # Directly use the simulated client
        serp_results = await simulated_client.get_serp_results(keyword, num_results, search_engine)
        await self._set_cached_response(cache_key, [sr.to_dict() for sr in serp_results], "serp_api", "get_serp_data_simulated")
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
