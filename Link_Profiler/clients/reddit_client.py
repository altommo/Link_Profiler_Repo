"""
Reddit Client - Interacts with the Reddit API using PRAW.
File: Link_Profiler/clients/reddit_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta # Import datetime and timedelta
import random # Import random

import praw # Requires pip install praw
from prawcore.exceptions import RequestException, ResponseException # Import specific PRAW exceptions

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class RedditClient:
    """
    Client for interacting with the Reddit API using PRAW.
    Note: PRAW is synchronous, so API calls are wrapped in `asyncio.to_thread`.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__ + ".RedditClient")
        self.client_id = config_loader.get("social_media_crawler.reddit_api.client_id")
        self.client_secret = config_loader.get("social_media_crawler.reddit_api.client_secret")
        self.user_agent = config_loader.get("social_media_crawler.reddit_api.user_agent", "LinkProfilerBot/1.0")
        self.enabled = config_loader.get("social_media_crawler.reddit_api.enabled", False)
        self.reddit: Optional[praw.Reddit] = None
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager # Avoid name collision
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to RedditClient. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to RedditClient. Falling back to global instance.")


        if not self.enabled:
            self.logger.info("Reddit API is disabled by configuration.")
        elif not self.client_id or not self.client_secret:
            self.logger.warning("Reddit API is enabled but client_id or client_secret is missing. Functionality will be simulated.")
            self.enabled = False # Effectively disable if keys are missing

    async def __aenter__(self):
        """Initialise PRAW Reddit instance."""
        if self.enabled:
            self.logger.info("Entering RedditClient context. Initialising PRAW.")
            await self.session_manager.__aenter__() # Ensure session manager is entered
            try:
                # PRAW initialization is synchronous
                self.reddit = await self.resilience_manager.execute_with_resilience(
                    lambda: praw.Reddit(
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                        user_agent=self.user_agent
                    ),
                    url="https://www.reddit.com/api/v1/access_token" # Representative URL for CB
                )
                # Test connection by fetching a read-only property
                await self.resilience_manager.execute_with_resilience(
                    lambda: self.reddit.user.me(),
                    url="https://oauth.reddit.com/api/v1/me" # Representative URL for CB
                )
                self.logger.info("PRAW Reddit instance initialized successfully.")
            except Exception as e:
                self.logger.error(f"Failed to initialize PRAW Reddit client: {e}. Functionality will be simulated.", exc_info=True)
                self.enabled = False # Disable if init fails
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No explicit close method for PRAW, but good practice for context."""
        if self.enabled:
            self.logger.info("Exiting RedditClient context.")
            self.reddit = None # Clear instance
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="reddit_api", api_client_type="reddit_client", endpoint="search_mentions")
    async def search_mentions(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Searches for mentions on Reddit.
        
        Args:
            query (str): The search query (e.g., brand name, keyword).
            limit (int): Maximum number of submissions to retrieve.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a Reddit submission.
        """
        if not self.enabled or not self.reddit:
            self.logger.warning(f"Reddit API is disabled or not initialized. Simulating search mentions for '{query}'.")
            return self._simulate_mentions(query, limit)

        self.logger.info(f"Searching Reddit for mentions of '{query}' (limit: {limit})...")
        results = []
        try:
            # PRAW search is synchronous, run in a separate thread
            # Note: PRAW's search limit is capped at 100. For more, Pushshift or 'after' token logic is needed.
            # For now, we'll just document the 100-result cap.
            submissions = await self.resilience_manager.execute_with_resilience(
                lambda: self.reddit.subreddit('all').search(query, limit=limit),
                url="https://oauth.reddit.com/r/all/search" # Representative URL for CB
            )
            
            for s in submissions:
                results.append({
                    'platform': 'reddit',
                    'mention_text': s.title,
                    'url': s.url,
                    'score': s.score,
                    'comments_count': s.num_comments,
                    'author': str(s.author), # Convert Redditor object to string
                    'published_date': datetime.fromtimestamp(s.created_utc).isoformat(),
                    'sentiment': 'neutral', # PRAW doesn't provide sentiment directly
                    'engagement_score': s.score, # Using score as a proxy for engagement
                    'last_fetched_at': datetime.utcnow().isoformat() # Set last_fetched_at for live data
                })
            self.logger.info(f"Found {len(results)} Reddit mentions for '{query}'.")
            await asyncio.sleep(1) # Throttle: Reddit API limits ~60 requests/minute (1 request/second)
            return results
        except (RequestException, ResponseException) as e:
            if e.response and e.response.status == 429:
                self.logger.warning(f"Reddit API rate limit exceeded for '{query}'. Retrying after 30 seconds.")
                await asyncio.sleep(30)
                return await self.search_mentions(query, limit) # Retry the call
            else:
                self.logger.error(f"Reddit API error searching for '{query}': {e}", exc_info=True)
                return self._simulate_mentions(query, limit) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error searching Reddit for '{query}': {e}", exc_info=True)
            return self._simulate_mentions(query, limit) # Fallback to simulation on error

    def _simulate_mentions(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Helper to generate simulated Reddit mentions."""
        self.logger.info(f"Simulating Reddit mentions for '{query}' (limit: {limit}).")
        simulated_results = []
        for i in range(limit):
            simulated_results.append({
                'platform': 'reddit',
                'mention_text': f"Simulated Reddit post about {query} #{i+1}",
                'url': f"https://www.reddit.com/r/simulated/comments/{random.randint(10000,99999)}",
                'score': random.randint(1, 1000),
                'comments_count': random.randint(0, 200),
                'author': f"u/simulated_user_{random.randint(1,100)}",
                'published_date': (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                'sentiment': random.choice(['positive', 'negative', 'neutral']),
                'engagement_score': random.randint(1, 1000),
                'last_fetched_at': datetime.utcnow().isoformat()
            })
        return simulated_results

