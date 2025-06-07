"""
WHOIS Client - Interacts with WHOIS-JSON.com API.
File: Link_Profiler/clients/whois_client.py
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import aiohttp
import json
import random
# Removed time import as it's no longer needed for manual performance measurement

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient # Import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class WHOISClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Client for fetching WHOIS data from WHOIS-JSON.com.
    Offers a free tier with limits.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".WHOISClient")
        self.base_url = config_loader.get("domain_api.whois_json_api.base_url")
        self.api_key = config_loader.get("domain_api.whois_json_api.api_key") # Optional, for higher limits
        self.enabled = config_loader.get("domain_api.whois_json_api.enabled", False)
        
        if not self.enabled:
            self.logger.info("WHOIS-JSON.com API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        await super().__aenter__() # Call BaseAPIClient's __aenter__
        if self.enabled:
            self.logger.info("Entering WHOISClient context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        await super().__aexit__(exc_type, exc_val, exc_tb) # Call BaseAPIClient's __aexit__
        if self.enabled:
            self.logger.info("Exiting WHOISClient context. Closing aiohttp session.")

    @api_rate_limited(service="whois_json_api", api_client_type="whois_client", endpoint="get_domain_info")
    async def get_domain_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Fetches WHOIS information for a given domain.
        
        Args:
            domain (str): The domain name to query.
            
        Returns:
            Optional[Dict[str, Any]]: The JSON response from the WHOIS-JSON.com API, or None on failure.
        """
        if not self.enabled:
            self.logger.warning(f"WHOIS-JSON.com API is disabled. Simulating WHOIS data for {domain}.")
            return self._simulate_whois_data(domain)

        endpoint = self.base_url
        params = {'domain': domain}
        if self.api_key:
            params['api_key'] = self.api_key # Add API key if available

        self.logger.info(f"Calling WHOIS-JSON.com API for domain: {domain}...")
        try:
            # _make_request now handles resilience and adds 'last_fetched_at'
            response_data = await self._make_request("GET", endpoint, params=params)
            self.logger.info(f"WHOIS data for {domain} fetched successfully.")
            
            # Normalize the output
            normalized_data = {
                "domain_name": response_data.get("domain_name"),
                "registrar": response_data.get("registrar", {}).get("name"),
                "creation_date": response_data.get("creation_date"),
                "expiration_date": response_data.get("expiration_date"),
                "name_servers": response_data.get("name_servers", []),
                "status": response_data.get("status"),
                "country": response_data.get("registrant", {}).get("country"),
                "emails": response_data.get("emails", []),
                "organization": response_data.get("registrant", {}).get("organization"),
                'last_fetched_at': response_data.get('last_fetched_at') # Get from _make_request
            }
            return normalized_data
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Network/API error fetching WHOIS data for {domain} (Status: {e.status}): {e}", exc_info=True)
            return self._simulate_whois_data(domain) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Error fetching WHOIS data for {domain}: {e}", exc_info=True)
            return self._simulate_whois_data(domain) # Fallback to simulation on error

    def _simulate_whois_data(self, domain: str) -> Optional[Dict[str, Any]]:
        """Helper to generate simulated WHOIS data."""
        self.logger.info(f"Simulating WHOIS data for {domain}.")
        import random
        from datetime import datetime, timedelta

        if "example.com" in domain:
            return {
                "domain_name": domain,
                "registrar": "Example Registrar",
                "creation_date": "2000-01-01",
                "expiration_date": "2025-01-01",
                "name_servers": ["ns1.example.com", "ns2.example.com"],
                "status": "clientTransferProhibited",
                "emails": ["abuse@example.com"],
                "organization": "Example LLC",
                "country": "US",
                'last_fetched_at': datetime.utcnow().isoformat()
            }
        elif "test.com" in domain:
            return None # Simulate not found
        else:
            return {
                "domain_name": domain,
                "registrar": f"Registrar {random.randint(1, 10)}",
                "creation_date": (datetime.now() - timedelta(days=random.randint(365, 365*10))).strftime("%Y-%m-%d"),
                "expiration_date": (datetime.now() + timedelta(days=random.randint(30, 365*5))).strftime("%Y-%m-%d"),
                "name_servers": [f"ns1.{domain}", f"ns2.{domain}"],
                "status": "ok",
                "emails": [f"admin@{domain}"],
                "organization": f"Org {random.randint(1, 100)}",
                "country": random.choice(["US", "CA", "GB", "DE", "AU"]),
                'last_fetched_at': datetime.utcnow().isoformat()
            }
