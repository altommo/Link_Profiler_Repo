"""
SSL Labs Client - Interacts with the SSL Labs API.
File: Link_Profiler/clients/ssl_labs_client.py
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import aiohttp
import json # For parsing JSON response
import random # Import random for simulation
# Removed time import as it's no longer needed for manual performance measurement
from datetime import datetime # Import datetime

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient # Import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class SSLLabsClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Client for fetching SSL/TLS analysis from SSL Labs API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".SSLLabsClient")
        self.base_url = config_loader.get("technical_auditor.ssl_labs_api.base_url")
        self.enabled = config_loader.get("technical_auditor.ssl_labs_api.enabled", False)
        
        if not self.enabled:
            self.logger.info("SSL Labs API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        await super().__aenter__() # Call BaseAPIClient's __aenter__
        if self.enabled:
            self.logger.info("Entering SSLLabsClient context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        await super().__aexit__(exc_type, exc_val, exc_tb) # Call BaseAPIClient's __aexit__
        if self.enabled:
            self.logger.info("Exiting SSLLabsClient context.")

    @api_rate_limited(service="ssl_labs_api", api_client_type="ssl_labs_client", endpoint="analyze_ssl")
    async def analyze_ssl(self, host: str, publish: str = 'off', all_results: str = 'done') -> Optional[Dict[str, Any]]:
        """
        Analyzes the SSL/TLS configuration of a given host.
        
        Args:
            host (str): The hostname to analyze.
            publish (str): 'on' to publish results, 'off' to keep private.
            all_results (str): 'on' to return all results, 'done' to wait for completion.
            
        Returns:
            Optional[Dict[str, Any]]: The JSON response from the SSL Labs API, or None on failure.
        """
        if not self.enabled:
            self.logger.warning(f"SSL Labs API is disabled. Cannot perform SSL analysis for {host}.")
            return None

        endpoint = self.base_url
        params = {
            'host': host,
            'publish': publish,
            'all': all_results,
            'fromCache': 'on', # Try to get from cache first to save time/requests
            'maxAge': 86400 # Use cached results up to 24 hours old
        }

        self.logger.info(f"Calling SSL Labs API for SSL analysis of {host}...")
        
        retries = 3 # Up to 3 retries for 429/5xx
        for attempt in range(retries + 1):
            try:
                data = await self._make_request("GET", endpoint, params=params)
                
                # Implement polling logic
                while data.get('status') in ('IN_PROGRESS', 'DNS'):
                    self.logger.info(f"SSL Labs analysis for {host} is {data.get('status')}. Polling in 10 seconds...")
                    await asyncio.sleep(10) # Poll every 10 seconds
                    
                    # Re-fetch data for polling, using _make_request for resilience
                    data = await self._make_request("GET", endpoint, params=params) 
                
                if data.get('status') == 'READY':
                    self.logger.info(f"SSL analysis for {host} completed with grade: {data.get('endpoints', [{}])[0].get('grade')}.")
                    return data
                elif data.get('status') == 'ERROR':
                    self.logger.error(f"SSL Labs analysis for {host} returned an error status: {data.get('statusMessage')}")
                    return None # Analysis failed
                else:
                    self.logger.warning(f"SSL Labs analysis for {host} returned unexpected status: {data.get('status')}. Data: {data}")
                    return None # Unexpected status
            except aiohttp.ClientResponseError as e:
                if e.status in [429, 500, 502, 503, 504] and attempt < retries:
                    self.logger.warning(f"SSL Labs API {e.status} error fetching SSL analysis for {host}. Backing off, then retrying...")
                    await asyncio.sleep(2 ** attempt * 5) # Exponential backoff
                else:
                    self.logger.error(f"Network/API error fetching SSL analysis for {host} (Status: {e.status}): {e}", exc_info=True)
                    return None # Return None on persistent error
            except Exception as e:
                self.logger.error(f"Unexpected error fetching SSL analysis for {host}: {e}", exc_info=True)
                return None # Return None on general error
        return None # Should not be reached if retries are handled
