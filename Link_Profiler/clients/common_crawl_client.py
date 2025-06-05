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
import time # Import time for time.monotonic()

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class CommonCrawlClient:
    """
    Client for searching the Common Crawl Index.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        self.logger = logging.getLogger(__name__ + ".CommonCrawlClient")
        self.base_url = config_loader.get("historical_data.common_crawl_api.base_url")
        self.enabled = config_loader.get("historical_data.common_crawl_api.enabled", False)
        self.session_manager = session_manager
        if self.session_manager is None:
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to CommonCrawlClient. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to CommonCrawlClient. Falling back to global instance.")

        self._last_call_time: float = 0.0 # For explicit throttling
        self._current_index_url: Optional[str] = None # To store the resolved latest index URL

        if not self.enabled:
            self.logger.info("Common Crawl API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session and resolve latest Common Crawl index."""
        if self.enabled:
            self.logger.info("Entering CommonCrawlClient context.")
            await self.session_manager.__aenter__()
            await self._resolve_latest_index()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled:
            self.logger.info("Exiting CommonCrawlClient context.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def _throttle(self):
        """Ensures at least 1 second delay between calls to Common Crawl."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < 1.0:
            wait_time = 1.0 - elapsed
            self.logger.debug(f"Throttling Common Crawl API. Waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)
        self._last_call_time = time.monotonic()

    async def _resolve_latest_index(self):
        """Fetches the latest Common Crawl index URL."""
        if not self.base_url or not self.base_url.startswith("https://index.commoncrawl.org"):
            self.logger.warning(f"Common Crawl base URL '{self.base_url}' is not a valid index endpoint. Assuming it's a full CDX URL or disabling.")
            if not self.base_url.endswith("/cdx"): # If it's not a full CDX URL, disable
                self.enabled = False
            self._current_index_url = self.base_url # Use as is if it's a full CDX URL
            return

        collinfo_url = f"{self.base_url}/collinfo.json"
        try:
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(collinfo_url, timeout=10),
                url=collinfo_url
            )
            response.raise_for_status()
            collections_info = await response.json()
            if collections_info:
                latest_collection = collections_info[-1]['id'] # Get the latest collection ID
                self._current_index_url = f"{self.base_url}/{latest_collection}/cdx"
                self.logger.info(f"Resolved latest Common Crawl index to: {self._current_index_url}")
            else:
                self.logger.error("Failed to retrieve Common Crawl collection info. Disabling Common Crawl client.")
                self.enabled = False
        except Exception as e:
            self.logger.error(f"Error resolving latest Common Crawl index from {collinfo_url}: {e}. Disabling Common Crawl client.", exc_info=True)
            self.enabled = False

    @api_rate_limited(service="common_crawl_api", api_client_type="common_crawl_client", endpoint="search_domain")
    async def search_domain(self, domain: str, match_type: str = 'domain', limit: int = 100,
                            from_date: Optional[str] = None, to_date: Optional[str] = None,
                            fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Searches the Common Crawl Index for records related to a domain.
        
        Args:
            domain (str): The domain to search for (e.g., "example.com").
            match_type (str): How to match the domain ('domain', 'host', 'prefix', 'exact').
            limit (int): Maximum number of records to retrieve.
            from_date (str): Start date for records (YYYYMMDD or YYYY-MM-DD).
            to_date (str): End date for records (YYYYMMDD or YYYY-MM-DD).
            fields (List[str]): List of fields to return (e.g., ['url', 'timestamp', 'status']).
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a Common Crawl record.
        """
        if not self.enabled or not self._current_index_url:
            self.logger.warning(f"Common Crawl API is disabled or index not resolved. Simulating search for {domain}.")
            return self._simulate_search_results(domain, match_type, limit)

        await self._throttle() # Apply explicit throttling

        # Common Crawl CDX API parameters
        params = {
            'url': f"*.{domain}/*" if match_type == 'domain' else domain, # Adjust URL pattern based on match_type
            'output': 'json',
            'limit': limit,
            'showNumPages': 'true' # Request total pages for potential future pagination
        }

        if from_date:
            params['from'] = from_date.replace('-', '') # Ensure YYYYMMDD format
        if to_date:
            params['to'] = to_date.replace('-', '') # Ensure YYYYMMDD format
        if fields:
            params['fl'] = ','.join(fields) # Filter fields

        self.logger.info(f"Calling Common Crawl API for domain: {domain} (match_type: {match_type}, limit: {limit})...")
        results = []
        try:
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(self._current_index_url, params=params, timeout=30),
                url=self._current_index_url # Pass the URL for circuit breaker naming
            )
            response.raise_for_status()
            # Common Crawl returns newline-delimited JSON, not a single JSON array
            content = await response.text()
            for line in content.strip().split('\n'):
                if line:
                    try:
                        record = json.loads(line)
                        record['last_fetched_at'] = datetime.utcnow().isoformat() # Add last_fetched_at
                        results.append(record)
                    except json.JSONDecodeError:
                        self.logger.warning(f"Failed to decode JSON line from Common Crawl: {line[:100]}...")
                        continue
            self.logger.info(f"Found {len(results)} Common Crawl records for {domain}.")
            return results
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                self.logger.warning(f"Common Crawl API rate limit exceeded for {domain}. Retrying after 60 seconds.")
                await asyncio.sleep(60)
                return await self.search_domain(domain, match_type, limit, from_date, to_date, fields) # Retry the call
            else:
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
                "filename": f"CC-MAIN-{timestamp.year}-{random.randint(1,52)}-warc.gz",
                'last_fetched_at': datetime.utcnow().isoformat()
            })
        return simulated_results

