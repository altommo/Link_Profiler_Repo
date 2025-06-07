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
from Link_Profiler.clients.base_client import BaseAPIClient # Import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class CommonCrawlClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Client for searching the Common Crawl Index.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".CommonCrawlClient")
        self.base_url = config_loader.get("historical_data.common_crawl_api.base_url")
        self.enabled = config_loader.get("historical_data.common_crawl_api.enabled", False)
        
        self._current_index_url: Optional[str] = None # To store the resolved latest index URL

        if not self.enabled:
            self.logger.info("Common Crawl API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session and resolve latest Common Crawl index."""
        await super().__aenter__() # Call BaseAPIClient's __aenter__
        if self.enabled:
            self.logger.info("Entering CommonCrawlClient context.")
            await self._resolve_latest_index()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        await super().__aexit__(exc_type, exc_val, exc_tb) # Call BaseAPIClient's __aexit__
        if self.enabled:
            self.logger.info("Exiting CommonCrawlClient context.")

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
            # Use _make_request for fetching collection info
            collections_info = await self._make_request("GET", collinfo_url)
            
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
            # Use _make_request for fetching data. It returns raw text for non-JSON responses.
            # Common Crawl returns newline-delimited JSON, so we need to process the text.
            response_text = await self._make_request("GET", self._current_index_url, params=params, return_json=False)
            
            for line in response_text.strip().split('\n'):
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

