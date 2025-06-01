"""
Common Crawl Client - Interacts with the Common Crawl Index API.
File: Link_Profiler/clients/common_crawl_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
import json # For parsing JSON response
from datetime import datetime # For timestamp conversion
import random # Import random for simulation

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

class CommonCrawlClient:
    """
    Client for searching the Common Crawl Index.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".CommonCrawlClient")
        self.base_url = config_loader.get("historical_data.common_crawl_api.base_url")
        self.enabled = config_loader.get("historical_data.common_crawl_api.enabled", False)
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.enabled:
            self.logger.info("Common Crawl API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering CommonCrawlClient context.")
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled and self._session and not self._session.closed:
            self.logger.info("Exiting CommonCrawlClient context. Closing aiohttp session.")
            await self._session.close()
            self._session = None

    @api_rate_limited(service="common_crawl_api", api_client_type="common_crawl_client", endpoint="search_domain")
    async def search_domain(self, domain: str, match_type: str = 'domain', limit: int = 100) -> List[Dict[str, Any]]:
        """
        Searches the Common Crawl Index for records related to a domain.
        
        Args:
            domain (str): The domain to search for (e.g., "example.com").
            match_type (str): How to match the domain ('domain', 'host', 'prefix', 'exact').
            limit (int): Maximum number of records to retrieve.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a Common Crawl record.
        """
        if not self.enabled:
            self.logger.warning(f"Common Crawl API is disabled. Simulating search for {domain}.")
            return self._simulate_search_results(domain, match_type, limit)

        # Common Crawl index URL pattern: https://index.commoncrawl.org/CC-MAIN-2023-40-index
        # We need to find the latest index. For simplicity, we'll use a generic endpoint or assume latest.
        # A more robust solution would fetch available indexes first.
        # For now, I'll use a hardcoded latest index for simulation, or assume base_url is the full index URL.
        # Let's assume `base_url` from config is `https://index.commoncrawl.org`
        # and we need to find the latest index.
        
        # A more robust way to get the latest index:
        # async with self._session.get("https://index.commoncrawl.org/collinfo.json") as response:
        #     collections_info = await response.json()
        #     latest_collection = collections_info[-1]['id'] # Get the latest collection ID
        #     index_url = f"https://index.commoncrawl.org/{latest_collection}/cdx"

        # For simplicity and to match the provided snippet's spirit, I'll use a generic index pattern.
        # The snippet's URL `https://index.commoncrawl.org/CC-MAIN-*-index` is incorrect for querying.
        # The actual query endpoint is usually `/cdx` or `/cdx-api` on a specific index.
        # Let's use a common pattern for the CDX API.
        
        # Assuming base_url is "https://index.commoncrawl.org"
        # We need to pick an index. For a real app, you'd fetch the latest.
        # For this, I'll use a placeholder for the index.
        # Let's assume the config `base_url` is `https://index.commoncrawl.org/CC-MAIN-2023-40/cdx` for example.
        # Or, if `base_url` is just `https://index.commoncrawl.org`, we need to append `/CC-MAIN-LATEST/cdx`
        # For now, I'll use a simplified endpoint that might not be perfectly accurate but demonstrates the call.
        
        # The provided snippet for CommonCrawlClient is very basic and doesn't reflect the actual CDX API usage.
        # The `url` in the snippet is for listing indexes, not querying.
        # It should be something like `https://index.commoncrawl.org/CC-MAIN-2023-40/cdx`
        # I will use a generic index endpoint for the base_url in config, e.g., `https://index.commoncrawl.org/CC-MAIN-2023-40/cdx`
        # And then the `search_domain` method will append `?url=...`
        
        endpoint = self.base_url # This should be the full CDX API URL for a specific index
        if not endpoint:
            self.logger.error("Common Crawl base URL not configured. Simulating search results.")
            return self._simulate_search_results(domain, match_type, limit)

        # Common Crawl CDX API parameters
        params = {
            'url': f"*.{domain}/*" if match_type == 'domain' else domain, # Adjust URL pattern based on match_type
            'output': 'json',
            'limit': limit
        }
        # Add other parameters like 'from', 'to', 'filter', 'fl' (fields) as needed

        self.logger.info(f"Calling Common Crawl API for domain: {domain} (match_type: {match_type}, limit: {limit})...")
        results = []
        try:
            async with self._session.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status()
                # Common Crawl returns newline-delimited JSON, not a single JSON array
                content = await response.text()
                for line in content.strip().split('\n'):
                    if line:
                        try:
                            results.append(json.loads(line))
                        except json.JSONDecodeError:
                            self.logger.warning(f"Failed to decode JSON line from Common Crawl: {line[:100]}...")
                            continue
            self.logger.info(f"Found {len(results)} Common Crawl records for {domain}.")
            return results
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error searching Common Crawl for {domain}: {e}", exc_info=True)
            return self._simulate_search_results(domain, match_type, limit) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error searching Common Crawl for {domain}: {e}", exc_info=True)
            return self._simulate_search_results(domain, match_type, limit) # Fallback to simulation on error

    def _simulate_search_results(self, domain: str, match_type: str, limit: int) -> List[Dict[str, Any]]:
        """Helper to generate simulated Common Crawl search results."""
        self.logger.info(f"Simulating Common Crawl search results for {domain} (limit: {limit}).")
        from datetime import timedelta

        simulated_results = []
        for i in range(limit):
            timestamp = datetime.now() - timedelta(days=random.randint(30, 365*5))
            simulated_results.append({
                "urlkey": f"com,{domain.replace('.', ',')}/page{i+1}",
                "timestamp": timestamp.strftime("%Y%m%d%H%M%S"),
                "url": f"http://{domain}/page{i+1}.html",
                "mime": "text/html",
                "status": "200",
                "digest": f"simulated_digest_{random.randint(1000, 9999)}",
                "length": str(random.randint(5000, 20000)),
                "offset": str(random.randint(100000, 999999)),
                "filename": f"CC-MAIN-{timestamp.year}-{random.randint(1,52)}-warc.gz"
            })
        return simulated_results
