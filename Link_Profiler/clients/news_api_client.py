import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager

logger = logging.getLogger(__name__)

class NewsAPIClient(BaseAPIClient):
    """
    Client for interacting with the NewsAPI.org API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        super().__init__(session_manager, resilience_manager)
        self.logger = logging.getLogger(__name__ + ".NewsAPIClient")
        self.base_url = config_loader.get("social_media_crawler.news_api.base_url")
        self.api_key = config_loader.get("social_media_crawler.news_api.api_key")
        self.enabled = config_loader.get("social_media_crawler.news_api.enabled", False)

        if self.enabled and self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        if not self.enabled:
            self.logger.info("NewsAPI.org is disabled by configuration.")
        elif not self.api_key:
            self.logger.warning("NewsAPI.org API key is missing. NewsAPI.org will be disabled.")
            self.enabled = False

    @api_rate_limited(service="news_api", api_client_type="news_api_client", endpoint="search_news")
    async def search_news(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches NewsAPI.org for articles matching a query.
        
        Args:
            query (str): The search query.
            limit (int): Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a news article.
        """
        if not self.enabled:
            self.logger.warning(f"NewsAPI.org client not enabled. Skipping search for '{query}'.")
            return []

        endpoint = f"{self.base_url}/everything"
        params = {
            "q": query,
            "apiKey": self.api_key,
            "pageSize": limit,
            "language": "en",
            "sortBy": "relevancy"
        }

        self.logger.info(f"Searching NewsAPI.org for query: '{query}' (Limit: {limit})...")
        results = []
        try:
            # _make_request now handles resilience
            response_data = await self._make_request("GET", endpoint, params=params)
            
            for article in response_data.get("articles", []):
                results.append({
                    "platform": "newsapi",
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "text": article.get("description"),
                    "author": article.get("author"),
                    "published_at": article.get("publishedAt"),
                    "source_name": article.get("source", {}).get("name"),
                    "raw_data": article
                })
            self.logger.info(f"Found {len(results)} news articles for '{query}'.")
            return results
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Network/API error searching NewsAPI.org for '{query}' (Status: {e.status}): {e}", exc_info=True)
            return []
        except Exception as e:
            self.logger.error(f"Error searching NewsAPI.org for '{query}': {e}", exc_info=True)
            return []
