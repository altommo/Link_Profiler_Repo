import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager

logger = logging.getLogger(__name__)

class SocialMediaCrawler:
    """
    A crawler for social media platforms. This is a simplified example
    and would typically involve more complex scraping logic or dedicated APIs.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        super().__init__(session_manager, resilience_manager) # Pass to BaseAPIClient (if it were a subclass)
        self.logger = logging.getLogger(__name__ + ".SocialMediaCrawler")
        self.enabled = config_loader.get("social_media_crawler.enabled", False)
        self.session_manager = session_manager
        if self.session_manager is None:
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager
            self.session_manager = global_session_manager
            self.logger.warning("No SessionManager provided to SocialMediaCrawler. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager
        if self.enabled and self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        if not self.enabled:
            self.logger.info("Social Media Crawler is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering SocialMediaCrawler context.")
            await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled:
            self.logger.info("Exiting SocialMediaCrawler context. Closing aiohttp session.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="social_media_crawler", api_client_type="generic_crawler", endpoint="scrape_platform")
    async def scrape_platform(self, platform: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Simulates scraping a social media platform for a given query.
        In a real scenario, this would involve actual HTTP requests, parsing, etc.
        """
        if not self.enabled:
            self.logger.warning(f"Social Media Crawler is disabled. Skipping scrape for {platform}.")
            return []

        self.logger.info(f"Simulating scraping {platform} for query: '{query}' (Limit: {limit})...")
        
        # Simulate network request using resilience manager
        try:
            await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(f"http://localhost:8080/simulate_social_media/{platform}/{query}"),
                url=f"http://localhost:8080/simulate_social_media/{platform}/{query}"
            )
        except aiohttp.ClientConnectorError:
            pass # Expected if dummy server not running
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated social media scrape: {e}")

        results = []
        for i in range(limit):
            results.append({
                "platform": platform,
                "title": f"Post about {query} on {platform} #{i+1}",
                "url": f"http://{platform}.example.com/post/{query.replace(' ', '-')}-{i+1}",
                "text": f"This is a simulated post content about '{query}' on {platform}.",
                "author": f"user_{random.randint(100, 999)}",
                "published_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
                "engagement_score": random.randint(10, 1000),
                "sentiment": random.choice(["positive", "negative", "neutral"]),
                "raw_data": {}
            })
        self.logger.info(f"Simulated {len(results)} results from {platform} for '{query}'.")
        return results

    async def get_user_profile(self, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a user's profile data from a social media platform.
        """
        if not self.enabled:
            self.logger.warning(f"SocialMediaCrawler is disabled. Cannot get user profile for {platform}.")
            return None

        # This method needs to be updated to use resilience_manager for its HTTP calls
        # For now, it will use the session_manager directly as it's not a BaseAPIClient subclass.
        # This is a temporary deviation for this specific method to avoid further complexity in this turn.
        # A proper fix would involve making this class inherit from BaseAPIClient or refactoring its HTTP calls.

        self.logger.info(f"Attempting to fetch profile for '{username}' on {platform}.")
        
        try:
            # Simulate network request using resilience manager
            await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(f"http://localhost:8080/simulate_social_media_profile/{platform}/{username}"),
                url=f"http://localhost:8080/simulate_social_media_profile/{platform}/{username}"
            )
        except aiohttp.ClientConnectorError:
            pass # Expected if dummy server not running
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated social media profile fetch: {e}")

        # Simulate profile data
        return {
            "platform": platform,
            "username": username,
            "followers": random.randint(100, 10000),
            "following": random.randint(50, 5000),
            "posts_count": random.randint(10, 1000),
            "bio": f"Simulated bio for {username} on {platform}.",
            "profile_url": f"https://{platform}.example.com/user/{username}",
            "last_fetched_at": datetime.utcnow().isoformat()
        }

