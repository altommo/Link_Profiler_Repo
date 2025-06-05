"""
NewsAPI Client - Interacts with NewsAPI.org.
File: Link_Profiler/clients/news_api_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import aiohttp
import random

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class NewsAPIClient:
    """
    Client for fetching news articles from NewsAPI.org.
    Requires an API key.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__ + ".NewsAPIClient")
        self.api_key = config_loader.get("social_media_crawler.news_api.api_key")
        self.base_url = config_loader.get("social_media_crawler.news_api.base_url")
        self.enabled = config_loader.get("social_media_crawler.news_api.enabled", False)
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager # Avoid name collision
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to NewsAPIClient. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to NewsAPIClient. Falling back to global instance.")


        if not self.enabled:
            self.logger.info("NewsAPI.org is disabled by configuration.")
        elif not self.api_key:
            self.logger.warning("NewsAPI.org is enabled but API key is missing. Functionality will be simulated.")
            self.enabled = False # Effectively disable if key is missing

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering NewsAPIClient context.")
            await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled:
            self.logger.info("Exiting NewsAPIClient context. Closing aiohttp session.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="news_api", api_client_type="news_api_client", endpoint="search_news")
    async def search_news(self, query: str, sort_by: str = 'publishedAt', language: str = 'en', page_size: int = 20) -> List[Dict[str, Any]]:
        """
        Searches for news articles matching a query.
        
        Args:
            query (str): The search query.
            sort_by (str): How to sort the articles (e.g., 'relevancy', 'popularity', 'publishedAt').
            language (str): The 2-letter ISO-639-1 code of the language.
            page_size (int): The number of results to return per page (max 100 for developers).
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a news article.
        """
        if not self.enabled:
            self.logger.warning(f"NewsAPI.org is disabled. Simulating news search for '{query}'.")
            return self._simulate_articles(query, page_size)

        endpoint = f"{self.base_url}/everything" # Or /top-headlines
        
        all_articles: List[Dict[str, Any]] = []
        max_pages = 5 # NewsAPI free tier allows pages 1-5
        
        for page in range(1, max_pages + 1):
            params = {
                'q': query,
                'sortBy': sort_by,
                'language': language,
                'pageSize': page_size,
                'apiKey': self.api_key,
                'page': page
            }

            self.logger.info(f"Calling NewsAPI.org for news search: '{query}' (page: {page}, page_size: {page_size})...")
            try:
                response = await self.resilience_manager.execute_with_resilience(
                    lambda: self.session_manager.get(endpoint, params=params, timeout=15),
                    url=endpoint # Pass the endpoint for circuit breaker naming
                )
                response.raise_for_status()
                data = await response.json()
                
                articles_on_page = data.get('articles', [])
                if not articles_on_page:
                    self.logger.info(f"No more articles found for '{query}' on page {page}. Breaking pagination loop.")
                    break # No more articles
                
                for article in articles_on_page:
                    all_articles.append({
                        'platform': 'newsapi',
                        'title': article.get('title'),
                        'description': article.get('description'),
                        'url': article.get('url'),
                        'author': article.get('author'),
                        'source': article.get('source', {}).get('name'),
                        'published_at': article.get('publishedAt'),
                        'content': article.get('content'),
                        'last_fetched_at': datetime.utcnow().isoformat() # Set last_fetched_at for live data
                    })
                
                # NewsAPI free tier limits total results, so we might not get all pages
                if len(articles_on_page) < page_size:
                    self.logger.info(f"Less than page_size articles on page {page}. Assuming last page for '{query}'.")
                    break # Last page
                
                await asyncio.sleep(1) # Delay between pages to avoid rate limits

            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    self.logger.warning(f"NewsAPI.org rate limit exceeded for '{query}'. Retrying after 60 seconds.")
                    await asyncio.sleep(60) # Wait for 1 minute
                    continue # Retry the current page
                else:
                    self.logger.error(f"Network/API error searching NewsAPI.org for '{query}' (page: {page}): {e}", exc_info=True)
                    break # Break on other errors
            except Exception as e:
                self.logger.error(f"Unexpected error searching NewsAPI.org for '{query}' (page: {page}): {e}", exc_info=True)
                break # Break on unexpected errors

        self.logger.info(f"Found {len(all_articles)} news articles for '{query}'.")
        return all_articles

    def _simulate_articles(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Helper to generate simulated news articles."""
        self.logger.info(f"Simulating NewsAPI.org articles for '{query}' (limit: {limit}).")
        simulated_results = []
        for i in range(limit):
            simulated_results.append({
                'platform': 'newsapi',
                'title': f"Breaking News: {query} Update #{i+1}",
                'description': f"A simulated news article discussing the latest developments in {query}.",
                'url': f"https://simulated-news.com/article/{random.randint(10000, 99999)}",
                'author': f"Reporter {random.randint(1, 50)}",
                'source': f"Simulated News Outlet {random.randint(1, 10)}",
                'published_at': (datetime.now() - timedelta(hours=random.randint(1, 24*7))).isoformat(),
                'content': f"Full content of the simulated news article about {query}...",
                'last_fetched_at': datetime.utcnow().isoformat()
            })
        return simulated_results

