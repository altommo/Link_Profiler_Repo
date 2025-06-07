import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random

import praw # Requires pip install praw
from prawcore.exceptions import RequestException, ResponseException # Import specific PRAW exceptions

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class RedditClient(BaseAPIClient):
    """
    Client for interacting with the Reddit API (via PRAW).
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Pass api_quota_manager to base class
        self.logger = logging.getLogger(__name__ + ".RedditClient")
        self.enabled = config_loader.get("social_media_crawler.reddit_api.enabled", False)
        self.client_id = config_loader.get("social_media_crawler.reddit_api.client_id")
        self.client_secret = config_loader.get("social_media_crawler.reddit_api.client_secret")
        self.user_agent = config_loader.get("social_media_crawler.reddit_api.user_agent", "LinkProfilerBot/1.0")

        # Removed redundant check as BaseAPIClient handles resilience_manager validation
        # if self.enabled and self.resilience_manager is None:
        #     raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        if not self.enabled:
            self.logger.info("Reddit API is disabled by configuration.")
        elif not self.client_id or not self.client_secret:
            self.logger.warning("Reddit API client_id or client_secret is missing. Reddit API will be disabled.")
            self.enabled = False
        
        self.reddit = None # PRAW Reddit instance

    async def __aenter__(self):
        """Initializes the PRAW Reddit instance."""
        if not self.enabled:
            return self

        self.logger.info("Entering RedditClient context. Initializing PRAW.")
        try:
            import praw
            # PRAW handles its own session management, but we need to ensure it's within our async context.
            # PRAW's Reddit instance is synchronous, so we'll wrap its calls in asyncio.to_thread.
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            # Test authentication by fetching redditor info
            await self.resilience_manager.execute_with_resilience(
                lambda: self.reddit.user.me(),
                url="https://oauth.reddit.com/api/v1/me" # Representative URL for CB
            )
            self.logger.info("PRAW Reddit instance initialized and authenticated.")
        except ImportError:
            self.logger.error("PRAW library not found. Reddit API functionality will be disabled. Install with 'pip install praw'.")
            self.enabled = False
        except Exception as e:
            self.logger.error(f"Error initializing PRAW Reddit client: {e}. Reddit API functionality will be disabled.", exc_info=True)
            self.enabled = False
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific cleanup needed for PRAW Reddit instance."""
        if self.enabled:
            self.logger.info("Exiting RedditClient context.")
        pass

    @api_rate_limited(service="reddit_api", api_client_type="reddit_client", endpoint="search_mentions")
    async def search_mentions(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches Reddit for mentions of a given query.
        
        Args:
            query (str): The search query (e.g., "LinkProfiler", "#SEO").
            limit (int): Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a Reddit submission.
        """
        if not self.enabled or not self.reddit:
            self.logger.warning(f"Reddit client not enabled or initialized. Skipping search for '{query}'.")
            return []

        self.logger.info(f"Searching Reddit for query: '{query}' (Limit: {limit})...")
        results = []
        try:
            # PRAW search is synchronous, run in a thread pool executor
            # We use resilience_manager to wrap the synchronous call to PRAW
            # The URL for the circuit breaker is a placeholder as PRAW doesn't expose a direct API endpoint.
            search_results = await self.resilience_manager.execute_with_resilience(
                lambda: list(self.reddit.subreddit("all").search(query, limit=limit)),
                url="https://www.reddit.com/search" # Representative URL for CB
            )
            
            for submission in search_results:
                results.append({
                    "platform": "reddit",
                    "id": submission.id,
                    "title": submission.title,
                    "url": submission.url,
                    "text": submission.selftext,
                    "author": submission.author.name if submission.author else "[deleted]",
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "created_utc": datetime.fromtimestamp(submission.created_utc).isoformat(),
                    "subreddit": submission.subreddit.display_name,
                    "raw_data": submission.__dict__ # Store raw PRAW object dict
                })
            self.logger.info(f"Found {len(results)} Reddit mentions for '{query}'.")
            return results
        except Exception as e:
            self.logger.error(f"Error searching Reddit for '{query}': {e}", exc_info=True)
            return []

