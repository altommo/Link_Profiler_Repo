import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import HTTPException, status # Import HTTPException and status for access control

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.database import db, clickhouse_client
from Link_Profiler.utils.api_cache import APICache
from Link_Profiler.core.models import (
    Domain, Backlink, SEOMetrics, SERPResult, KeywordSuggestion,
    GSCBacklink, KeywordTrend, User # Import User for tier checking
)
from Link_Profiler.utils.auth_utils import get_user_tier # Import get_user_tier

logger = logging.getLogger(__name__)

class DataService:
    """
    Service layer for fetching and managing data, implementing cache-first logic.
    This layer orchestrates data retrieval from cache, PostgreSQL, ClickHouse,
    and external API clients.
    """
    def __init__(self, database_client=None, ch_client=None, cache_client=None):
        self.db = database_client if database_client else db
        self.ch_client = ch_client if ch_client else clickhouse_client
        self.cache = cache_client if cache_client else APICache()
        self.logger = logging.getLogger(__name__ + ".DataService")
        self.allow_live_data_fetching = config_loader.get("data_fetching.allow_live_data_fetching", False)

    async def _fetch_and_cache(self, cache_key: str, fetch_func, ttl: int, force_live: bool = False):
        """
        Generic method to fetch data, apply cache-first logic, and store in cache.
        
        Args:
            cache_key (str): The key to use for caching.
            fetch_func (callable): An async function that fetches the live data.
            ttl (int): Time-to-live for the cache entry in seconds.
            force_live (bool): If True, bypass cache and fetch live data.
        """
        if not self.cache.enabled:
            self.logger.debug(f"Cache is disabled. Fetching live data for {cache_key}.")
            return await fetch_func()

        if force_live:
            self.logger.info(f"Force live data fetch requested for {cache_key}. Bypassing cache.")
            data = await fetch_func()
            if data is not None:
                await self.cache.set(cache_key, data, service="data_service", endpoint="generic_fetch", ttl=ttl)
            return data
        
        cached_data = await self.cache.get(cache_key, service="data_service", endpoint="generic_fetch")
        if cached_data:
            self.logger.debug(f"Returning cached data for {cache_key}.")
            return cached_data
        
        self.logger.info(f"Cache miss for {cache_key}. Fetching live data.")
        data = await fetch_func()
        if data is not None:
            await self.cache.set(cache_key, data, service="data_service", endpoint="generic_fetch", ttl=ttl)
        return data

    def validate_live_access(self, user: User, feature: str):
        """
        Checks if the user has permission to access live data for a specific feature.
        Raises HTTPException if access is denied.
        """
        # Check global config
        if not self.allow_live_data_fetching:
            self.logger.warning(f"Live data fetching requested for feature '{feature}' but is globally disabled.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live data temporarily unavailable due to system configuration."
            )
        
        user_tier = get_user_tier(user) # Get user tier from auth_utils
        
        # Define which tiers can access live data for which features
        # This is a simplified example; you might have a more granular configuration
        PREMIUM_LIVE_FEATURES = ["backlinks", "gsc_backlinks_analytical", "keyword_trends_analytical"] # Example features requiring premium
        
        if user_tier == "free":
            self.logger.warning(f"Live data access denied for user {user.username} (tier: {user_tier}) for feature '{feature}'.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Live data requires a paid plan."
            )
        
        if user_tier == "basic" and feature in PREMIUM_LIVE_FEATURES:
            self.logger.warning(f"Live data access denied for user {user.username} (tier: {user_tier}) for feature '{feature}'. Requires Pro plan.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Live {feature} requires a Pro plan."
            )
        
        # Placeholder for usage limits (e.g., daily live API calls)
        # if user.live_api_calls_today >= user.plan_limits.live_calls_per_day:
        #     raise HTTPException(
        #         status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        #         detail="Live data quota exceeded for today."
        #     )
        
        # If all checks pass, track usage (placeholder)
        # self.increment_live_api_usage(user.id, feature)
        self.logger.info(f"Live data access granted for user {user.username} (tier: {user_tier}) for feature '{feature}'.")

    async def get_all_crawl_jobs(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all crawl jobs, cache-first.
        """
        feature = "crawl_jobs"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)
        
        async def fetch_live():
            jobs = self.db.get_all_crawl_jobs()
            return [job.to_dict() for job in jobs]
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_all_link_profiles(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all link profiles, cache-first.
        """
        feature = "link_profiles"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            profiles = self.db.get_all_link_profiles()
            return [profile.to_dict() for profile in profiles]
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_all_domains(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all domains, cache-first.
        """
        feature = "domains"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            domains = self.db.get_all_domains()
            return [domain.to_dict() for domain in domains]
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_all_backlinks(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all backlinks, cache-first.
        Note: For large datasets, this might be better served directly from ClickHouse.
        """
        feature = "backlinks"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            # Example of fetching from PostgreSQL
            backlinks = self.db.get_all_backlinks()
            return [bl.to_dict() for bl in backlinks]
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_gsc_backlinks_analytical(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves GSC backlinks from ClickHouse, cache-first.
        """
        feature = "gsc_backlinks_analytical"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            # This would typically involve calling the GSC client and then inserting into ClickHouse
            # For now, we'll assume data is already in ClickHouse and fetch from there.
            # In a real scenario, you'd call GoogleSearchConsoleClient.fetch_backlinks() here.
            # Since ClickHouseClient doesn't have a direct 'get_all' method, this is a placeholder.
            self.logger.warning("Direct fetch for GSC backlinks analytical data is a placeholder. Implement actual ClickHouse query.")
            # Example: return self.ch_client.get_all_gsc_backlinks() if such a method existed
            return [] # Placeholder for actual ClickHouse query results
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_keyword_trends_analytical(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves keyword trends from ClickHouse, cache-first.
        """
        feature = "keyword_trends_analytical"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            # Similar to GSC backlinks, this is a placeholder for ClickHouse query.
            self.logger.warning("Direct fetch for keyword trends analytical data is a placeholder. Implement actual ClickHouse query.")
            # Example: return self.ch_client.get_all_keyword_trends() if such a method existed
            return [] # Placeholder for actual ClickHouse query results
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

# Initialize the service with the singleton database clients
data_service = DataService(database_client=db, ch_client=clickhouse_client, cache_client=APICache())
