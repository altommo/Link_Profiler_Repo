"""
Social Media Service - Provides functionalities for crawling and analyzing social media data.
File: Link_Profiler/services/social_media_service.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import redis.asyncio as redis
import uuid # Import uuid for SocialMention ID

from Link_Profiler.crawlers.social_media_crawler import SocialMediaCrawler # Import the social media crawler
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.reddit_client import RedditClient # New: Import RedditClient
from Link_Profiler.clients.youtube_client import YouTubeClient # New: Import YouTubeClient
from Link_Profiler.clients.news_api_client import NewsAPIClient # New: Import NewsAPIClient
from Link_Profiler.database.database import Database # Import Database for DB operations
from Link_Profiler.core.models import SocialMention # Import SocialMention model
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class SocialMediaService:
    """
    Service for interacting with social media platforms.
    This service orchestrates calls to various social media API clients.
    """
    def __init__(self, database: Database, session_manager: SessionManager, social_media_crawler: Optional[SocialMediaCrawler] = None,
                 reddit_client: Optional[RedditClient] = None, youtube_client: Optional[YouTubeClient] = None, news_api_client: Optional[NewsAPIClient] = None,
                 resilience_manager: Optional[DistributedResilienceManager] = None, redis_client: Optional[redis.Redis] = None): # Added redis_client
        self.logger = logging.getLogger(__name__)
        self.db = database # Store database instance
        self.session_manager = session_manager # Store session manager instance
        self.resilience_manager = resilience_manager # Store resilience manager
        if self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")
        self.redis_client = redis_client # Stored redis_client

        # Pass resilience_manager to clients
        # Note: SocialMediaCrawler, RedditClient, YouTubeClient, NewsAPIClient need to be updated
        # to accept resilience_manager in their constructors.
        self.social_media_crawler = social_media_crawler
        self.reddit_client = reddit_client
        self.youtube_client = youtube_client
        self.news_api_client = news_api_client

        self.enabled = config_loader.get("social_media_crawler.enabled", False)
        self.allow_live = config_loader.get("social_media_service.allow_live", False)
        self.staleness_threshold = timedelta(hours=config_loader.get("social_media_service.staleness_threshold_hours", 24))

        if not self.enabled:
            self.logger.info("Social Media Service is disabled by configuration.")
        elif not (self.social_media_crawler or self.reddit_client or self.youtube_client or self.news_api_client):
            self.logger.warning("Social Media Service is enabled but no crawler or API clients provided. Functionality will be limited to simulation.")

    async def __aenter__(self):
        """Async context manager entry for SocialMediaService."""
        self.logger.debug("Entering SocialMediaService context.")
        await self.session_manager.__aenter__() # Enter session manager context
        if self.social_media_crawler:
            await self.social_media_crawler.__aenter__()
        if self.reddit_client:
            await self.reddit_client.__aenter__()
        if self.youtube_client:
            await self.youtube_client.__aenter__()
        if self.news_api_client:
            await self.news_api_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for SocialMediaService."""
        self.logger.debug("Exiting SocialMediaService context.")
        if self.social_media_crawler:
            await self.social_media_crawler.__aexit__(exc_type, exc_val, exc_tb)
        if self.reddit_client:
            await self.reddit_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.youtube_client:
            await self.youtube_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.news_api_client:
            await self.news_api_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb) # Exit session manager context

    async def _fetch_live_social_media_data(self, query: str, platforms: Optional[List[str]] = None) -> List[SocialMention]:
        """
        Crawls social media platforms for a given query (e.g., hashtag, username) directly from APIs.
        This method is intended for internal use by the service when a live fetch is required.
        """
        self.logger.info(f"Fetching LIVE social media data for query: '{query}' on platforms: {platforms or 'all'}")

        extracted_data: List[SocialMention] = []
        
        # Determine target platforms from config or provided list
        target_platforms = platforms if platforms else config_loader.get("social_media_crawler.platforms", [])
        if not target_platforms:
            self.logger.warning("No social media platforms configured or provided for LIVE crawling.")
            return []

        tasks = []
        for platform in target_platforms:
            if platform == "reddit" and self.reddit_client and self.reddit_client.enabled:
                tasks.append(self.reddit_client.search_mentions(query))
            elif platform == "youtube" and self.youtube_client and self.youtube_client.enabled:
                tasks.append(self.youtube_client.search_videos(query))
            elif platform == "newsapi" and self.news_api_client and self.news_api_client.enabled:
                tasks.append(self.news_api_client.search_news(query))
            elif self.social_media_crawler: # Fallback to generic crawler if specific API not enabled
                tasks.append(self.social_media_crawler.scrape_platform(platform, query))
            else:
                self.logger.warning(f"No client or crawler available for platform '{platform}'. Skipping LIVE fetch.")
        
        # Execute all tasks concurrently
        results_from_tasks = await asyncio.gather(*tasks, return_exceptions=True)

        now = datetime.utcnow()
        for result in results_from_tasks:
            if isinstance(result, Exception):
                self.logger.error(f"Error during LIVE social media data fetch: {result}", exc_info=True)
                continue
            if result:
                for item in result:
                    # Convert raw dict to SocialMention dataclass
                    mention = SocialMention(
                        id=str(uuid.uuid4()), # Generate ID if not present
                        query=query,
                        platform=item.get('platform', 'unknown'),
                        mention_url=item.get('url', ''),
                        mention_text=item.get('text', item.get('title', '')),
                        author=item.get('author'),
                        published_date=datetime.fromisoformat(item['published_at']) if item.get('published_at') else now,
                        sentiment=item.get('sentiment'),
                        engagement_score=item.get('engagement_score', item.get('score')),
                        raw_data=item.get('raw_data', item), # Use raw_data if present, else the item itself
                        last_fetched_at=now # Set last_fetched_at for live data
                    )
                    extracted_data.append(mention)
        
        self.logger.info(f"LIVE social media crawl for '{query}' completed. Found {len(extracted_data)} posts.")
        return extracted_data

    async def crawl_social_media(self, query: str, platforms: Optional[List[str]] = None, source: str = "cache") -> List[SocialMention]:
        """
        Crawls social media platforms for a given query (e.g., hashtag, username).
        Returns a list of SocialMention objects.
        Prioritizes cached data, but can fetch live if requested and allowed.
        """
        if not self.enabled:
            self.logger.warning("Social Media Service is disabled. Cannot perform crawl.")
            return []

        cached_mentions = self.db.get_latest_social_mentions_for_query(query)
        
        # Determine the latest fetch time from cached mentions
        latest_fetched_at = None
        if cached_mentions:
            latest_fetched_at = max((sm.last_fetched_at for sm in cached_mentions if sm.last_fetched_at), default=None)
        
        now = datetime.utcnow()

        if source == "live" and self.allow_live:
            if not latest_fetched_at or (now - latest_fetched_at) > self.staleness_threshold:
                self.logger.info(f"Live fetch requested or cache stale for {query}. Fetching live social media data.")
                live_mentions = await self._fetch_live_social_media_data(query, platforms)
                if live_mentions:
                    self.db.add_social_mentions(live_mentions) # Save/update the fresh data
                    return live_mentions
                else:
                    self.logger.warning(f"Live fetch failed for {query}. Returning cached data if available.")
                    return cached_mentions # Fallback to cache
            else:
                self.logger.info(f"Live fetch requested for {query}, but cache is fresh. Fetching live anyway.")
                live_mentions = await self._fetch_live_social_media_data(query, platforms)
                if live_mentions:
                    self.db.add_social_mentions(live_mentions)
                    return live_mentions
                else:
                    self.logger.warning(f"Live fetch failed for {query}. Returning cached data.")
                    return cached_mentions # Fallback to cache
        else:
            self.logger.info(f"Returning cached social media data for {query}.")
            return cached_mentions

    async def get_brand_mentions(self, brand_name: str, platforms: Optional[List[str]] = None, source: str = "cache") -> List[SocialMention]:
        """
        Retrieves mentions of a specific brand across social media platforms.
        This would typically leverage the `crawl_social_media` method with specific queries.
        """
        self.logger.info(f"Getting brand mentions for '{brand_name}' on platforms: {platforms or 'all'}.")
        query = f"#{brand_name} OR \"{brand_name}\"" # Example query
        return await self.crawl_social_media(query, platforms, source=source)

    async def get_b2b_link_opportunities(self, industry_keywords: List[str]) -> List[Dict[str, Any]]:
        """
        Identifies potential B2B link opportunities by searching for industry-relevant discussions
        and profiles on platforms like LinkedIn or industry forums.
        This is a highly conceptual feature.
        """
        self.logger.info(f"Identifying B2B link opportunities for keywords: {industry_keywords}.")
        
        if not self.enabled:
            self.logger.warning("Social Media Service is disabled. Cannot identify B2B opportunities.")
            return []

        platforms = config_loader.get("social_media_crawler.platforms", [])
        opportunities = []

        for keyword in industry_keywords:
            if "linkedin" in platforms and self.social_media_crawler:
                try:
                    linkedin_posts = await self.social_media_crawler.scrape_platform(
                        "linkedin", keyword, limit=10
                    )
                    for post in linkedin_posts:
                        opportunities.append(
                            {
                                "type": "LinkedIn Post",
                                "url": post.get("url"),
                                "relevance": post.get("text"),
                                "contact_hint": "Connect on LinkedIn",
                                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
                            }
                        )
                except Exception as e:
                    self.logger.error(
                        f"Error fetching LinkedIn opportunities for '{keyword}': {e}",
                        exc_info=True,
                    )

            if (
                "reddit" in platforms
                and self.reddit_client
                and self.reddit_client.enabled
            ):
                try:
                    reddit_threads = await self.reddit_client.search_mentions(
                        keyword, limit=10
                    )
                    for thread in reddit_threads:
                        opportunities.append(
                            {
                                "type": "Reddit Discussion",
                                "url": thread.get("url"),
                                "relevance": thread.get("mention_text"),
                                "contact_hint": "Participate in discussion",
                                "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
                            }
                        )
                except Exception as e:
                    self.logger.error(
                        f"Error fetching Reddit opportunities for '{keyword}': {e}",
                        exc_info=True,
                    )

        self.logger.info(f"Found {len(opportunities)} B2B link opportunities.")
        return opportunities
