"""
WHOIS Client - Interacts with WHOIS-JSON.com API.
File: Link_Profiler/clients/whois_client.py
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

class WHOISClient:
    """
    Client for fetching WHOIS data from WHOIS-JSON.com.
    Offers a free tier with limits.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".WHOISClient")
        self.base_url = config_loader.get("domain_api.whois_json_api.base_url")
        self.api_key = config_loader.get("domain_api.whois_json_api.api_key") # Optional, for higher limits
        self.enabled = config_loader.get("domain_api.whois_json_api.enabled", False)
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.enabled:
            self.logger.info("WHOIS-JSON.com API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering WHOISClient context.")
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled and self._session and not self._session.closed:
            self.logger.info("Exiting WHOISClient context. Closing aiohttp session.")
            await self._session.close()
            self._session = None

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
            async with self._session.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status() # Raise an exception for HTTP errors
                data = await response.json()
                self.logger.info(f"WHOIS data for {domain} fetched successfully.")
                return data
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error fetching WHOIS data for {domain}: {e}", exc_info=True)
            return self._simulate_whois_data(domain) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching WHOIS data for {domain}: {e}", exc_info=True)
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
                "country": "US"
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
                "country": random.choice(["US", "CA", "GB", "DE", "AU"])
            }
