import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp # Import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class NewsAPIClient(BaseAPIClient):
    """
    Client for interacting with the NewsAPI.org API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Pass api_quota_manager to base class
        self.logger = logging.getLogger(__name__ + ".NewsAPIClient")
        self.base_url = config_loader.get("social_media_crawler.news_api.base_url")
        self.api_key = config_loader.get("social_media_crawler.news_api.api_key")
        self.enabled = config_loader.get("social_media_crawler.news_api.enabled", False)

        # Removed redundant check as BaseAPIClient handles resilience_manager validation
        # if self.enabled and self.resilience_manager is None:
        #     raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

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
        all_articles = []
        
        # NewsAPI.org has a max page size of 100, and free tier limits total results.
        # Loop pages 1-5 to accumulate up to 100 articles (20 articles per page * 5 pages)
        # or up to the requested limit.
        articles_per_page = min(limit, 20) # NewsAPI default page size is 20, max 100. Let's use 20 for more pages.
        max_pages = 5 # Loop up to 5 pages as requested

        for page in range(1, max_pages + 1):
            if len(all_articles) >= limit:
                break

            params = {
                "q": query,
                "apiKey": self.api_key,
                "pageSize": articles_per_page,
                "page": page,
                "language": "en",
                "sortBy": "relevancy"
            }

            self.logger.info(f"Searching NewsAPI.org for query: '{query}' (Page: {page}, PageSize: {articles_per_page})...")
            
            retries = 1 # One retry for 429 specifically
            for attempt in range(retries + 1):
                try:
                    # _make_request now handles resilience and adds 'last_fetched_at'
                    response_data = await self._make_request("GET", endpoint, params=params)
                    
                    articles_on_page = response_data.get("articles", [])
                    for article in articles_on_page:
                        all_articles.append({
                            "platform": "newsapi",
                            "title": article.get("title"),
                            "url": article.get("url"),
                            "text": article.get("description"),
                            "author": article.get("author"),
                            "published_at": article.get("publishedAt"),
                            "source_name": article.get("source", {}).get("name"),
                            "raw_data": article,
                            "last_fetched_at": response_data.get('last_fetched_at') # Get from _make_request
                        })
                    
                    if len(articles_on_page) < articles_per_page: # No more articles on this page
                        break # Exit page loop
                    
                    break # Break retry loop on success
                except aiohttp.ClientResponseError as e:
                    if e.status == 429 and attempt < retries:
                        self.logger.warning(f"NewsAPI.org rate limit hit (429) for '{query}'. Backing off 60 seconds, then retrying...")
                        await asyncio.sleep(60) # Back off 60 seconds
                    else:
                        self.logger.error(f"Network/API error searching NewsAPI.org for '{query}' (Status: {e.status}): {e}", exc_info=True)
                        return [] # Return empty on persistent error
                except Exception as e:
                    self.logger.error(f"Error searching NewsAPI.org for '{query}': {e}", exc_info=True)
                    return [] # Return empty on general error
            
            # Throttle 1 second between requests
            if page < max_pages and len(all_articles) < limit:
                await asyncio.sleep(1)

        self.logger.info(f"Found {len(all_articles)} news articles for '{query}'.")
        return all_articles[:limit] # Ensure we don't exceed the requested limit
