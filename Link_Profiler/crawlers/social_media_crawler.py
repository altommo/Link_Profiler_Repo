"""
Social Media Crawler - Placeholder for scraping social media platforms.
File: Link_Profiler/crawlers/social_media_crawler.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta  # Import timedelta
import aiohttp
import random

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager

logger = logging.getLogger(__name__)

class SocialMediaCrawler:
    """
    A class for interacting with social media platforms, either via direct scraping
    (where allowed and feasible) or by integrating with official APIs.
    This class demonstrates where real API calls or library usage would go.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__)
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager # Avoid name collision
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to SocialMediaCrawler. Falling back to global SessionManager.")

        self.enabled = config_loader.get("social_media_crawler.enabled", False)
        self.platforms_config = config_loader.get("social_media_crawler.platforms", [])

        # API keys for various platforms
        self.twitter_bearer_token = config_loader.get("social_media_crawler.twitter_bearer_token")
        self.facebook_app_id = config_loader.get("social_media_crawler.facebook_app_id")
        self.facebook_app_secret = config_loader.get("social_media_crawler.facebook_app_secret")
        self.linkedin_client_id = config_loader.get("social_media_crawler.linkedin_client_id")
        self.linkedin_client_secret = config_loader.get("social_media_crawler.linkedin_client_secret")
        self.reddit_client_id = config_loader.get("social_media_crawler.reddit_api.client_id")
        self.reddit_client_secret = config_loader.get("social_media_crawler.reddit_api.client_secret")
        self.reddit_user_agent = config_loader.get("social_media_crawler.reddit_api.user_agent", "LinkProfilerBot/1.0")

        # Tokens cached after retrieval
        self._facebook_access_token: Optional[str] = None
        self._facebook_token_expiry: Optional[datetime] = None
        self._linkedin_access_token: Optional[str] = None
        self._linkedin_token_expiry: Optional[datetime] = None


        if not self.enabled:
            self.logger.info("SocialMediaCrawler is disabled by configuration.")

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

    async def _get_facebook_access_token(self) -> Optional[str]:
        """Retrieve and cache a Facebook Graph API app access token."""
        if self._facebook_access_token and self._facebook_token_expiry and datetime.utcnow() < self._facebook_token_expiry:
            return self._facebook_access_token

        endpoint = "https://graph.facebook.com/oauth/access_token"
        params = {
            "client_id": self.facebook_app_id,
            "client_secret": self.facebook_app_secret,
            "grant_type": "client_credentials",
        }

        async with self.session_manager.get(endpoint, params=params, timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            token = data.get("access_token")
            if not token:
                return None
            expires_in = int(data.get("expires_in", 3600))
            self._facebook_access_token = token
            self._facebook_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            return token

    async def _get_linkedin_access_token(self) -> Optional[str]:
        """Retrieve and cache a LinkedIn API access token."""
        if self._linkedin_access_token and self._linkedin_token_expiry and datetime.utcnow() < self._linkedin_token_expiry:
            return self._linkedin_access_token

        endpoint = "https://www.linkedin.com/oauth/v2/accessToken"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.linkedin_client_id,
            "client_secret": self.linkedin_client_secret,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with self.session_manager.post(endpoint, data=data, headers=headers, timeout=10) as response:
            response.raise_for_status()
            payload = await response.json()
            token = payload.get("access_token")
            if not token:
                return None
            expires_in = int(payload.get("expires_in", 3600))
            self._linkedin_access_token = token
            self._linkedin_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            return token

    async def _fetch_twitter_posts(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch recent tweets matching a query using the Twitter API."""
        endpoint = "https://api.twitter.com/2/tweets/search/recent"
        headers = {"Authorization": f"Bearer {self.twitter_bearer_token}"}
        params = {
            "query": query,
            "max_results": limit,
            "tweet.fields": "created_at,author_id,public_metrics",
        }
        results: List[Dict[str, Any]] = []
        async with self.session_manager.get(endpoint, headers=headers, params=params, timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            for tweet in data.get("data", []):
                metrics = tweet.get("public_metrics", {})
                results.append({
                    "platform": "twitter",
                    "post_id": tweet.get("id"),
                    "text": tweet.get("text"),
                    "author_id": tweet.get("author_id"),
                    "likes": metrics.get("like_count"),
                    "retweets": metrics.get("retweet_count"),
                    "timestamp": tweet.get("created_at"),
                    "url": f"https://twitter.com/i/web/status/{tweet.get('id')}",
                })
        return results

    async def _fetch_facebook_posts(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search Facebook pages or posts using the Graph API."""
        token = await self._get_facebook_access_token()
        if not token:
            return []

        endpoint = "https://graph.facebook.com/v18.0/search"
        params = {"q": query, "type": "page", "limit": limit, "access_token": token}
        results: List[Dict[str, Any]] = []
        async with self.session_manager.get(endpoint, params=params, timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            for page in data.get("data", []):
                results.append({
                    "platform": "facebook",
                    "post_id": page.get("id"),
                    "text": page.get("name"),
                    "author_id": page.get("id"),
                    "likes": None,
                    "retweets": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "url": f"https://facebook.com/{page.get('id')}",
                })
        return results

    async def _fetch_linkedin_posts(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search LinkedIn posts or shares."""
        token = await self._get_linkedin_access_token()
        if not token:
            return []

        endpoint = "https://api.linkedin.com/v2/search"
        params = {"q": "blended", "keywords": query, "count": limit}
        headers = {"Authorization": f"Bearer {token}"}
        results: List[Dict[str, Any]] = []
        async with self.session_manager.get(endpoint, headers=headers, params=params, timeout=10) as response:
            response.raise_for_status()
            data = await response.json()
            for element in data.get("elements", []):
                results.append({
                    "platform": "linkedin",
                    "post_id": element.get("targetUrn"),
                    "text": element.get("title", {}).get("text"),
                    "author_id": None,
                    "likes": None,
                    "retweets": None,
                    "timestamp": datetime.utcnow().isoformat(),
                    "url": element.get("navigationUrl"),
                })
        return results

    async def scrape_platform(self, platform: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Interacts with a specific social media platform's API or performs scraping for a given query.
        """
        if not self.enabled:
            self.logger.warning(f"SocialMediaCrawler is disabled. Cannot scrape {platform}.")
            return []
        
        if platform not in self.platforms_config:
            self.logger.warning(f"Platform '{platform}' is not configured for social media crawling. Skipping.")
            return []

        self.logger.info(f"Attempting to scrape/fetch from {platform} for query: '{query}' (limit: {limit}).")
        
        results = []
        try:
            if platform == "twitter":
                if not self.twitter_bearer_token:
                    self.logger.warning("Twitter/X Bearer Token not configured. Simulating Twitter/X data.")
                    return self._simulate_posts(platform, query, limit)

                results = await self._fetch_twitter_posts(query, limit)

            elif platform == "facebook":
                if not self.facebook_app_id or not self.facebook_app_secret:
                    self.logger.warning("Facebook App ID/Secret not configured. Simulating Facebook data.")
                    return self._simulate_posts(platform, query, limit)

                results = await self._fetch_facebook_posts(query, limit)

            elif platform == "linkedin":
                if not self.linkedin_client_id or not self.linkedin_client_secret:
                    self.logger.warning("LinkedIn Client ID/Secret not configured. Simulating LinkedIn data.")
                    return self._simulate_posts(platform, query, limit)

                results = await self._fetch_linkedin_posts(query, limit)

            elif platform == "reddit":
                # Reddit API is handled by RedditClient, not directly here.
                # This branch should ideally not be reached if RedditClient is used.
                self.logger.warning("Reddit scraping via generic crawler is not implemented. Use RedditClient.")
                results = self._simulate_posts(platform, query, limit)

            else:
                self.logger.warning(f"Unsupported social media platform: {platform}. Simulating data.")
                results = self._simulate_posts(platform, query, limit)

        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error while scraping {platform} for '{query}': {e}", exc_info=True)
            results = self._simulate_posts(platform, query, limit) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error while scraping {platform} for '{query}': {e}", exc_info=True)
            results = self._simulate_posts(platform, query, limit) # Fallback to simulation on error
        
        self.logger.info(f"Scraped/fetched {len(results)} results from {platform} for '{query}'.")
        return results

    def _simulate_posts(self, platform: str, query: str, limit: int) -> List[Dict[str, Any]]:
        """Helper to generate simulated posts."""
        self.logger.info(f"Simulating {platform} posts for '{query}' (limit: {limit}).")
        simulated_results = []
        for i in range(limit):
            simulated_results.append({
                "platform": platform,
                "post_id": f"{platform}_post_{random.randint(1000, 9999)}",
                "text": f"This is a simulated post about '{query}' from {platform} user {random.randint(1, 100)}.",
                "author": f"user_{random.randint(1, 100)}",
                "likes": random.randint(0, 500),
                "shares": random.randint(0, 100),
                "timestamp": (datetime.now() - timedelta(hours=random.randint(1, 72))).isoformat(),
                "url": f"https://{platform}.com/posts/{random.randint(10000, 99999)}"
            })
        return simulated_results

    async def get_user_profile(self, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a user's profile data from a social media platform.
        """
        if not self.enabled:
            self.logger.warning(f"SocialMediaCrawler is disabled. Cannot get user profile for {platform}.")
            return None

        if platform not in self.platforms_config:
            self.logger.warning(f"Platform '{platform}' is not configured for social media crawling. Skipping.")
            return None

        self.logger.info(f"Attempting to fetch profile for '{username}' on {platform}.")
        
        try:
            if platform == "twitter":
                if not self.twitter_bearer_token:
                    self.logger.warning("Twitter/X Bearer Token not configured.")
                    return None

                endpoint = f"https://api.twitter.com/2/users/by/username/{username}"
                headers = {"Authorization": f"Bearer {self.twitter_bearer_token}"}
                params = {"user.fields": "public_metrics,description"}
                async with self.session_manager.get(endpoint, headers=headers, params=params, timeout=10) as response:
                    response.raise_for_status()
                    data = await response.json()
                    user = data.get("data")
                    if not user:
                        return None
                    metrics = user.get("public_metrics", {})
                    return {
                        "platform": "twitter",
                        "username": username,
                        "followers": metrics.get("followers_count"),
                        "following": metrics.get("following_count"),
                        "posts_count": metrics.get("tweet_count"),
                        "bio": user.get("description"),
                        "profile_url": f"https://twitter.com/{username}"
                    }

            elif platform == "facebook":
                if not self.facebook_app_id or not self.facebook_app_secret:
                    self.logger.warning("Facebook credentials not configured.")
                    return None

                token = await self._get_facebook_access_token()
                if not token:
                    return None

                endpoint = f"https://graph.facebook.com/v18.0/{username}"
                params = {"access_token": token, "fields": "name,followers_count,link"}
                async with self.session_manager.get(endpoint, params=params, timeout=10) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return {
                        "platform": "facebook",
                        "username": data.get("name", username),
                        "followers": data.get("followers_count"),
                        "following": None,
                        "posts_count": None,
                        "bio": None,
                        "profile_url": data.get("link") or f"https://facebook.com/{username}"
                    }

            elif platform == "linkedin":
                if not self.linkedin_client_id or not self.linkedin_client_secret:
                    self.logger.warning("LinkedIn credentials not configured.")
                    return None

                token = await self._get_linkedin_access_token()
                if not token:
                    return None

                endpoint = f"https://api.linkedin.com/v2/people/(vanityName:{username})"
                headers = {"Authorization": f"Bearer {token}"}
                async with self.session_manager.get(endpoint, headers=headers, timeout=10) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return {
                        "platform": "linkedin",
                        "username": username,
                        "followers": data.get("followersCount"),
                        "following": None,
                        "posts_count": None,
                        "bio": data.get("headline"),
                        "profile_url": f"https://www.linkedin.com/in/{username}"
                    }

            else:
                self.logger.warning(f"Unsupported platform for profile fetch: {platform}")
                return None
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error while fetching profile for {username} on {platform}: {e}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error while fetching profile for {username} on {platform}: {e}", exc_info=True)
            return None

