"""
Historical Data Service - Provides functionalities for fetching historical web data.
File: Link_Profiler/services/historical_data_service.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import json
import redis.asyncio as redis
from datetime import datetime # Import datetime for domain age calculation

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.wayback_machine_client import WaybackClient
from Link_Profiler.clients.common_crawl_client import CommonCrawlClient

logger = logging.getLogger(__name__)

class HistoricalDataService:
    """
    Service for fetching historical web data from sources like Wayback Machine and Common Crawl.
    """
    def __init__(self, wayback_client: WaybackClient, common_crawl_client: CommonCrawlClient, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600):
        self.logger = logging.getLogger(__name__)
        self.wayback_client = wayback_client
        self.common_crawl_client = common_crawl_client
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.enabled = config_loader.get("historical_data.wayback_machine_api.enabled", False) or \
                       config_loader.get("historical_data.common_crawl_api.enabled", False)

        if not self.enabled:
            self.logger.info("Historical Data Service is disabled by configuration (Wayback Machine and Common Crawl APIs are disabled).")

    async def __aenter__(self):
        """Async context manager entry for HistoricalDataService."""
        self.logger.debug("Entering HistoricalDataService context.")
        await self.wayback_client.__aenter__()
        await self.common_crawl_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for HistoricalDataService."""
        self.logger.debug("Exiting HistoricalDataService context.")
        await self.wayback_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.common_crawl_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.redis_client:
            await self.redis_client.close()

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

    async def get_historical_snapshots(self, url: str, limit: int = 10, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches historical snapshots for a URL from Wayback Machine.
        """
        if not self.wayback_client.enabled:
            self.logger.warning("Wayback Machine client is disabled. Cannot fetch historical snapshots.")
            return []
        
        cache_key = f"wayback_snapshots:{url}:{limit}:{from_date or ''}:{to_date or ''}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            return cached_result

        snapshots = await self.wayback_client.get_snapshots(url, limit, from_date, to_date)
        if snapshots:
            await self._set_cached_response(cache_key, snapshots)
        return snapshots

    async def get_common_crawl_records(self, domain: str, match_type: str = 'domain', limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetches records for a domain from Common Crawl.
        """
        if not self.common_crawl_client.enabled:
            self.logger.warning("Common Crawl client is disabled. Cannot fetch Common Crawl records.")
            return []

        cache_key = f"common_crawl_records:{domain}:{match_type}:{limit}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            return cached_result

        records = await self.common_crawl_client.search_domain(domain, match_type, limit)
        if records:
            await self._set_cached_response(cache_key, records)
        return records

    async def get_domain_age_from_wayback(self, domain: str) -> Optional[datetime]:
        """
        Estimates domain age by finding the earliest snapshot in Wayback Machine.
        """
        if not self.wayback_client.enabled:
            self.logger.warning("Wayback Machine client is disabled. Cannot estimate domain age.")
            return None
        
        # Fetch just one snapshot, the earliest one
        snapshots = await self.wayback_client.get_snapshots(domain, limit=1, from_date="19960101") # Start from earliest possible
        
        if snapshots:
            earliest_snapshot = snapshots[0]
            timestamp_str = earliest_snapshot.get('timestamp')
            if timestamp_str:
                try:
                    return datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
                except ValueError:
                    self.logger.warning(f"Could not parse timestamp from Wayback Machine: {timestamp_str}")
        return None
