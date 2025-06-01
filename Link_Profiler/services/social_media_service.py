"""
Social Media Service - Provides functionalities for crawling and analyzing social media data.
File: Link_Profiler/services/social_media_service.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import json
import redis.asyncio as redis

from Link_Profiler.crawlers.social_media_crawler import SocialMediaCrawler # Import the social media crawler
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.reddit_client import RedditClient # New: Import RedditClient
from Link_Profiler.clients.youtube_client import YouTubeClient # New: Import YouTubeClient
from Link_Profiler.clients.news_api_client import NewsAPIClient # New: Import NewsAPIClient

logger = logging.getLogger(__name__)

class SocialMediaService:
    """
    Service for interacting with social media platforms.
    This service orchestrates calls to various social media API clients.
    """
    def __init__(self, social_media_crawler: Optional[SocialMediaCrawler] = None, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600,
                 reddit_client: Optional[RedditClient] = None, youtube_client: Optional[YouTubeClient] = None, news_api_client: Optional[NewsAPIClient] = None): # New: Accept clients
        self.logger = logging.getLogger(__name__)
        self.social_media_crawler = social_media_crawler
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.enabled = config_loader.get("social_media_crawler.enabled", False)

        self.reddit_client = reddit_client # New
        self.youtube_client = youtube_client # New
        self.news_api_client = news_api_client # New

        if not self.enabled:
            self.logger.info("Social Media Service is disabled by configuration.")
        elif not (self.social_media_crawler or self.reddit_client or self.youtube_client or self.news_api_client):
            self.logger.warning("Social Media Service is enabled but no crawler or API clients provided. Functionality will be limited to simulation.")

    async def __aenter__(self):
        """Async context manager entry for SocialMediaService."""
        self.logger.debug("Entering SocialMediaService context.")
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

    async def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                self.logger.error(f"Error retrieving from cache for {cache_key}: {e}", exc_info=True)
        return None

    async def _set_cached_response(self, cache_key: str, data: Any):
        if self.redis_client:
            try:
                await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
                self.logger.debug(f"Cached {cache_key} with TTL {self.cache_ttl}")
            except Exception as e:
                self.logger.error(f"Error setting cache for {cache_key}: {e}", exc_info=True)

    async def crawl_social_media(self, query: str, platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Crawls social media platforms for a given query (e.g., hashtag, username).
        Returns a dictionary of extracted data.
        """
        if not self.enabled:
            self.logger.warning("Social Media Service is disabled. Cannot perform crawl.")
            return {"status": "disabled", "posts_found": 0, "extracted_data": []}

        cache_key = f"social_media_crawl:{query}:{'_'.join(sorted(platforms)) if platforms else 'all'}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            return cached_result

        self.logger.info(f"Starting social media crawl for query: '{query}' on platforms: {platforms or 'all'}")

        extracted_data = []
        posts_found = 0
        
        # Determine target platforms from config or provided list
        target_platforms = platforms if platforms else config_loader.get("social_media_crawler.platforms", [])
        if not target_platforms:
            self.logger.warning("No social media platforms configured or provided for crawling.")
            return {"status": "no_platforms_configured", "posts_found": 0, "extracted_data": []}

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
                self.logger.warning(f"No client or crawler available for platform '{platform}'. Skipping.")
        
        # Execute all tasks concurrently
        results_from_tasks = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results_from_tasks:
            if isinstance(result, Exception):
                self.logger.error(f"Error during social media data fetch: {result}", exc_info=True)
                continue
            if result:
                extracted_data.extend(result)
                posts_found += len(result)
        
        result = {
            "status": "completed",
            "query": query,
            "platforms_crawled": target_platforms,
            "posts_found": posts_found,
            "extracted_data": extracted_data
        }
        
        await self._set_cached_response(cache_key, result)
        self.logger.info(f"Social media crawl for '{query}' completed. Found {posts_found} posts.")
        return result

    async def get_brand_mentions(self, brand_name: str, platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Retrieves mentions of a specific brand across social media platforms.
        This would typically leverage the `crawl_social_media` method with specific queries.
        """
        self.logger.info(f"Getting brand mentions for '{brand_name}' on platforms: {platforms or 'all'}.")
        query = f"#{brand_name} OR \"{brand_name}\"" # Example query
        return await self.crawl_social_media(query, platforms)

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

        opportunities = []
        for keyword in industry_keywords:
            # This would involve more complex logic, potentially using the crawler to find relevant discussions
            # or directly querying LinkedIn/Reddit APIs for specific content types.
            # For now, we'll simulate finding some opportunities.
            if "linkedin" in config_loader.get("social_media_crawler.platforms", []):
                opportunities.append({
                    "type": "LinkedIn Profile",
                    "url": f"https://linkedin.com/in/simulated-expert-{random.randint(1,100)}",
                    "relevance": f"Discusses '{keyword}'",
                    "contact_hint": "Connect on LinkedIn"
                })
            if "reddit" in config_loader.get("social_media_crawler.platforms", []):
                opportunities.append({
                    "type": "Reddit Discussion",
                    "url": f"https://reddit.com/r/simulated_industry/comments/{random.randint(1000,9999)}",
                    "relevance": f"Thread about '{keyword}'",
                    "contact_hint": "Participate in discussion"
                })
        
        self.logger.info(f"Simulated {len(opportunities)} B2B link opportunities.")
        return opportunities
