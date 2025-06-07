import logging
from typing import Dict, Any, Optional, Type, List
from datetime import datetime
import asyncio

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_quota_manager import APIQuotaManager
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager

# Import all specific API clients that this router will manage
from Link_Profiler.clients.google_search_console_client import GoogleSearchConsoleClient
from Link_Profiler.clients.google_pagespeed_client import PageSpeedClient
from Link_Profiler.clients.google_trends_client import GoogleTrendsClient
from Link_Profiler.clients.whois_client import WHOISClient
from Link_Profiler.clients.dns_client import DNSClient
from Link_Profiler.clients.reddit_client import RedditClient
from Link_Profiler.clients.youtube_client import YouTubeClient
from Link_Profiler.clients.news_api_client import NewsAPIClient
from Link_Profiler.clients.serpstack_client import SerpstackClient
from Link_Profiler.clients.valueserp_client import ValueserpClient
from Link_Profiler.clients.webscraping_ai_client import WebscrapingAIClient
from Link_Profiler.clients.hunter_io_client import HunterIOClient
from Link_Profiler.clients.builtwith_client import BuiltWithClient
from Link_Profiler.clients.security_trails_client import SecurityTrailsClient

logger = logging.getLogger(__name__)

class SmartAPIRouterService:
    """
    A central service for routing API requests to the most optimal external API client.
    It uses APIQuotaManager to determine the best client based on various factors
    like quality, cost, remaining quota, and performance.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SmartAPIRouterService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self,
                 config: Dict[str, Any],
                 session_manager: SessionManager,
                 resilience_manager: DistributedResilienceManager,
                 api_quota_manager: APIQuotaManager,
                 # Pass all specific client instances here
                 google_search_console_client: GoogleSearchConsoleClient,
                 google_pagespeed_client: PageSpeedClient,
                 google_trends_client: GoogleTrendsClient,
                 whois_client: WHOISClient,
                 dns_client: DNSClient,
                 reddit_client: RedditClient,
                 youtube_client: YouTubeClient,
                 news_api_client: NewsAPIClient,
                 serpstack_client: SerpstackClient,
                 valueserp_client: ValueserpClient,
                 webscraping_ai_client: WebscrapingAIClient,
                 hunter_io_client: HunterIOClient,
                 builtwith_client: BuiltWithClient,
                 security_trails_client: SecurityTrailsClient
                 ):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".SmartAPIRouterService")
        self.config = config
        self.session_manager = session_manager
        self.resilience_manager = resilience_manager
        self.api_quota_manager = api_quota_manager

        # Store references to all managed API clients
        self.clients: Dict[str, Any] = {
            "google_search_console": google_search_console_client,
            "google_pagespeed": google_pagespeed_client,
            "google_trends": google_trends_client,
            "whois": whois_client,
            "dns": dns_client,
            "reddit": reddit_client,
            "youtube": youtube_client,
            "news_api": news_api_client,
            "serpstack": serpstack_client,
            "valueserp": valueserp_client,
            "webscraping_ai": webscraping_ai_client,
            "hunter_io": hunter_io_client,
            "builtwith": builtwith_client,
            "security_trails": security_trails_client
        }

        self.ml_enabled_for_routing = config.get("api_routing.ml_enabled", False)
        self.default_routing_strategy = config.get("api_routing.default_strategy", "best_quality")

        self.logger.info("SmartAPIRouterService initialized.")

    async def __aenter__(self):
        """Context manager entry point."""
        self.logger.info("SmartAPIRouterService entered context.")
        # No specific async setup needed for this class, clients are managed externally
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point."""
        self.logger.info("SmartAPIRouterService exited context.")
        # No specific async cleanup needed for this class
        pass

    async def _select_api_client(self, api_type: str, query_type: Optional[str] = None) -> Optional[Any]:
        """
        Selects the best API client for a given API type and query type
        using the APIQuotaManager.
        """
        # Filter available APIs by the requested api_type (e.g., "serpstack", "valueserp" for "serp" type)
        # This requires a mapping from a generic 'api_type' (e.g., 'serp') to specific client names.
        # For now, assume api_type directly maps to client name or is a prefix.
        
        # Get all available APIs from the quota manager that match the api_type prefix
        # Example: if api_type is 'serp', it should consider 'serpstack', 'valueserp'
        candidate_api_names = [
            name for name in self.api_quota_manager.quotas.keys()
            if name.startswith(api_type) or api_type in self.api_quota_manager.quotas[name].get('supported_query_types', [])
        ]
        
        if not candidate_api_names:
            self.logger.warning(f"No API clients configured for type: {api_type}")
            return None

        # Filter by actual availability (quota, circuit breaker)
        available_candidates = []
        for name in candidate_api_names:
            if name in self.clients: # Ensure we have an instantiated client for this API
                remaining = self.api_quota_manager.get_remaining_quota(name)
                cb = self.resilience_manager.get_circuit_breaker(name)
                cb_status = await cb.get_status()

                if (remaining is None or remaining > 0) and cb_status['state'] != "OPEN":
                    available_candidates.append(name)
            else:
                self.logger.warning(f"API client '{name}' is configured but not instantiated in SmartAPIRouterService.")

        if not available_candidates:
            self.logger.warning(f"No available API clients for type: {api_type} after filtering by quota/circuit breaker.")
            return None

        # Use APIQuotaManager to select the best one among available candidates
        # This requires a slight modification to APIQuotaManager to select from a subset
        # For now, we'll iterate and score them here.
        
        best_api_name = None
        best_score = -float('inf')

        for api_name in available_candidates:
            score = await self.api_quota_manager._calculate_api_score(
                api_name,
                strategy=self.default_routing_strategy,
                ml_enabled=self.ml_enabled_for_routing
            )
            if score > best_score:
                best_score = score
                best_api_name = api_name
        
        if best_api_name:
            self.logger.debug(f"Selected API client '{best_api_name}' for type '{api_type}' with score {best_score:.2f}")
            return self.clients[best_api_name]
        
        self.logger.warning(f"Could not select an API client for type: {api_type}. No suitable client found.")
        return None

    async def make_request(self,
                           api_type: str,
                           method: str,
                           url: str,
                           query_type: Optional[str] = None,
                           **kwargs) -> Any:
        """
        Makes an API request by first selecting the most optimal client.

        :param api_type: A generic type of API (e.g., "serp", "domain_info", "whois").
                         This maps to the client names (e.g., "serpstack", "valueserp", "whois").
        :param method: HTTP method (e.g., "GET", "POST").
        :param url: The URL endpoint for the request.
        :param query_type: Specific type of query (e.g., "organic_results", "image_search").
        :param kwargs: Additional keyword arguments for the request (e.g., params, json, headers).
        :return: The response from the API.
        :raises Exception: If no suitable API client is found or request fails.
        """
        selected_client = await self._select_api_client(api_type, query_type)

        if not selected_client:
            raise Exception(f"No suitable API client found for type: {api_type}, query_type: {query_type}")

        try:
            self.logger.info(f"Routing request for {api_type} ({query_type}) to {selected_client.__class__.__name__}")
            # Assuming all BaseAPIClient subclasses have a _make_request method
            response = await selected_client._make_request(method, url, **kwargs)
            return response
        except Exception as e:
            self.logger.error(f"Request via {selected_client.__class__.__name__} failed: {e}")
            # Potentially re-attempt with another client if configured for retry
            raise # Re-raise the exception for upstream handling

# Singleton instance
smart_api_router_service: Optional['SmartAPIRouterService'] = None
