"""
SecurityTrails Client - Interacts with the SecurityTrails API.
File: Link_Profiler/clients/security_trails_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
import json # For parsing JSON response
import random # Import random for simulation

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

class SecurityTrailsClient:
    """
    Client for fetching data from SecurityTrails API.
    Requires an API key.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SecurityTrailsClient")
        self.api_key = config_loader.get("technical_auditor.security_trails_api.api_key")
        self.base_url = config_loader.get("technical_auditor.security_trails_api.base_url")
        self.enabled = config_loader.get("technical_auditor.security_trails_api.enabled", False)
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.enabled:
            self.logger.info("SecurityTrails API is disabled by configuration.")
        elif not self.api_key:
            self.logger.warning("SecurityTrails API is enabled but API key is missing. Functionality will be simulated.")
            self.enabled = False # Effectively disable if key is missing

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering SecurityTrailsClient context.")
            if self._session is None or self._session.closed:
                headers = {'APIKEY': self.api_key}
                self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled and self._session and not self._session.closed:
            self.logger.info("Exiting SecurityTrailsClient context. Closing aiohttp session.")
            await self._session.close()
            self._session = None

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
            self.logger.warning(f"SecurityTrails API is disabled. Simulating subdomains for {domain}.")
            return self._simulate_subdomains(domain)

        endpoint = f"{self.base_url}/domain/{domain}/subdomains"
        
        self.logger.info(f"Calling SecurityTrails API for subdomains of {domain}...")
        subdomains = []
        try:
            async with self._session.get(endpoint, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                
                for subdomain_prefix in data.get('subdomains', []):
                    subdomains.append(f"{subdomain_prefix}.{domain}")
            self.logger.info(f"Found {len(subdomains)} subdomains for {domain}.")
            return subdomains
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error fetching subdomains for {domain}: {e}", exc_info=True)
            return self._simulate_subdomains(domain) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching subdomains for {domain}: {e}", exc_info=True)
            return self._simulate_subdomains(domain) # Fallback to simulation on error

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
            self.logger.warning(f"SecurityTrails API is disabled. Simulating DNS history for {domain}.")
            return self._simulate_dns_history(domain, record_type)

        endpoint = f"{self.base_url}/history/{domain}/dns/{record_type}"
        
        self.logger.info(f"Calling SecurityTrails API for DNS history of {domain} ({record_type})...")
        try:
            async with self._session.get(endpoint, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                self.logger.info(f"DNS history for {domain} ({record_type}) fetched successfully.")
                return data
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error fetching DNS history for {domain}: {e}", exc_info=True)
            return self._simulate_dns_history(domain, record_type) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching DNS history for {domain}: {e}", exc_info=True)
            return self._simulate_dns_history(domain, record_type) # Fallback to simulation on error

    def _simulate_subdomains(self, domain: str) -> List[str]:
        """Helper to generate simulated subdomains."""
        self.logger.info(f"Simulating SecurityTrails subdomains for {domain}.")
        return [
            f"www.{domain}",
            f"blog.{domain}",
            f"app.{domain}",
            f"dev.{domain}",
            f"mail.{domain}",
            f"shop.{domain}",
            f"cdn{random.randint(1,5)}.{domain}"
        ]

    def _simulate_dns_history(self, domain: str, record_type: str) -> Dict[str, Any]:
        """Helper to generate simulated DNS history."""
        self.logger.info(f"Simulating SecurityTrails DNS history for {domain} ({record_type}).")
        from datetime import datetime, timedelta

        records = []
        for i in range(random.randint(1, 5)):
            timestamp = datetime.now() - timedelta(days=random.randint(30, 365*3))
            if record_type.lower() == 'a':
                value = f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            elif record_type.lower() == 'mx':
                value = f"10 mail.{domain}"
            elif record_type.lower() == 'ns':
                value = f"ns{random.randint(1,2)}.{domain}"
            else:
                value = f"simulated_value_{random.randint(100,999)}"

            records.append({
                "values": [{"value": value}],
                "first_seen": timestamp.strftime("%Y-%m-%d"),
                "last_seen": (timestamp + timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d"),
                "organizations": [f"Simulated Org {random.randint(1,10)}"]
            })
        
        return {
            "records": records,
            "record_type": record_type.upper(),
            "total_pages": 1
        }
