"""
SecurityTrails Client - Interacts with the SecurityTrails API.
File: Link_Profiler/clients/security_trails_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
import json # For parsing JSON response
import random
# Removed time import as it's no longer needed for manual performance measurement

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient # Import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class SecurityTrailsClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Client for fetching data from SecurityTrails API.
    Requires an API key.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".SecurityTrailsClient")
        self.api_key = config_loader.get("technical_auditor.security_trails_api.api_key")
        self.base_url = config_loader.get("technical_auditor.security_trails_api.base_url")
        self.enabled = config_loader.get("technical_auditor.security_trails_api.enabled", False)
        
        if not self.enabled:
            self.logger.info("SecurityTrails API is disabled by configuration.")
        elif not self.api_key:
            self.logger.warning("SecurityTrails API is enabled but API key is missing. SecurityTrails API will be disabled.")
            self.enabled = False # Effectively disable if key is missing

    async def __aenter__(self):
        """Initialise aiohttp session and set API key in headers."""
        await super().__aenter__() # Call BaseAPIClient's __aenter__
        if self.enabled:
            self.logger.info("Entering SecurityTrailsClient context.")
            # Set API key in headers for the session manager's client session
            if self.session_manager._session:
                self.session_manager._session.headers.update({'APIKEY': self.api_key})
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        await super().__aexit__(exc_type, exc_val, exc_tb) # Call BaseAPIClient's __aexit__
        if self.enabled:
            self.logger.info("Exiting SecurityTrailsClient context.")

    @api_rate_limited(service="security_trails_api", api_client_type="security_trails_client", endpoint="get_subdomains")
    async def get_subdomains(self, domain: str) -> List[str]:
        """
        Fetches subdomains for a given domain.
        
        Args:
            domain (str): The domain name to query.
            
        Returns:
            List[str]: A list of subdomains.
        """
        if not self.enabled:
            self.logger.warning(f"SecurityTrails API is disabled. Cannot fetch subdomains for {domain}.")
            return []

        endpoint = f"{self.base_url}/domain/{domain}/subdomains"
        
        self.logger.info(f"Calling SecurityTrails API for subdomains of {domain}...")
        subdomains = []
        try:
            # Enforce 1s throttle between calls
            await asyncio.sleep(1)
            data = await self._make_request("GET", endpoint)
            
            for subdomain_prefix in data.get('subdomains', []):
                subdomains.append(f"{subdomain_prefix}.{domain}")
            self.logger.info(f"Found {len(subdomains)} subdomains for {domain}.")
            return subdomains
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Network/API error fetching subdomains for {domain} (Status: {e.status}): {e}", exc_info=True)
            return [] # Return empty on error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching subdomains for {domain}: {e}", exc_info=True)
            return [] # Return empty on error

    @api_rate_limited(service="security_trails_api", api_client_type="security_trails_client", endpoint="get_dns_history")
    async def get_dns_history(self, domain: str, record_type: str = 'a') -> Optional[Dict[str, Any]]:
        """
        Fetches DNS history for a given domain and record type.
        
        Args:
            domain (str): The domain name to query.
            record_type (str): The type of DNS record (e.g., 'a', 'mx', 'ns', 'txt').
            
        Returns:
            Optional[Dict[str, Any]]: The JSON response containing DNS history, or None.
        """
        if not self.enabled:
            self.logger.warning(f"SecurityTrails API is disabled. Cannot fetch DNS history for {domain}.")
            return None

        endpoint = f"{self.base_url}/history/{domain}/dns/{record_type}"
        
        self.logger.info(f"Calling SecurityTrails API for DNS history of {domain} ({record_type})...")
        all_records = []
        page = 1
        # SecurityTrails API uses 'records' and 'has_next_page' for pagination.
        # The 'cursor' parameter is not explicitly documented for DNS history,
        # but 'page' is used. The existing loop handles this.
        while True:
            params = {"page": page}
            try:
                # Enforce 1s throttle between calls (including between pages)
                await asyncio.sleep(1)
                data = await self._make_request("GET", endpoint, params=params)
                    
                records_on_page = data.get("records", [])
                all_records.extend(records_on_page)
                
                if not data.get("has_next_page") or not records_on_page:
                    break # No more pages or no records on current page
                
                page += 1
            except aiohttp.ClientResponseError as e:
                self.logger.error(f"Network/API error fetching DNS history for {domain} ({record_type}, page {page}) (Status: {e.status}): {e}", exc_info=True)
                return None # Return None on error
            except Exception as e:
                self.logger.error(f"Unexpected error fetching DNS history for {domain} ({record_type}, page {page}): {e}", exc_info=True)
                return None # Return None on error

        self.logger.info(f"DNS history for {domain} ({record_type}) fetched successfully. Total records: {len(all_records)}.")
        return {
            "records": all_records,
            "record_type": record_type.upper(),
            "total_pages": page # Total pages fetched
        }
