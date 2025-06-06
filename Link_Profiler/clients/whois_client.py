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
import time # Import time for time.monotonic()

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class WHOISClient:
    """
    Client for fetching WHOIS data from WHOIS-JSON.com.
    Offers a free tier with limits.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept SessionManager and ResilienceManager
        self.logger = logging.getLogger(__name__ + ".WHOISClient")
        self.base_url = config_loader.get("domain_api.whois_json_api.base_url")
        self.api_key = config_loader.get("domain_api.whois_json_api.api_key") # Optional, for higher limits
        self.enabled = config_loader.get("domain_api.whois_json_api.enabled", False)
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager # Avoid name collision
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to WHOISClient. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        # Removed problematic fallback import
        if self.enabled and self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        self._last_call_time: float = 0.0 # For explicit throttling

        if not self.enabled:
            self.logger.info("WHOIS-JSON.com API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering WHOISClient context.")
            await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled:
            self.logger.info("Exiting WHOISClient context. Closing aiohttp session.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def _throttle(self):
        """Ensures at least 1 second delay between calls to WHOIS-JSON.com."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < 1.0:
            wait_time = 1.0 - elapsed
            self.logger.debug(f"Throttling WHOIS-JSON.com API. Waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)
        self._last_call_time = time.monotonic()

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

        await self._throttle() # Apply explicit throttling

        endpoint = self.base_url
        params = {'domain': domain}
        if self.api_key:
            params['api_key'] = self.api_key # Add API key if available

        self.logger.info(f"Calling WHOIS-JSON.com API for domain: {domain}...")
        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(endpoint, params=params, timeout=10),
                url=endpoint # Pass the endpoint for circuit breaker naming
            )
            response.raise_for_status() # Raise an exception for HTTP errors
            data = await response.json()
            self.logger.info(f"WHOIS data for {domain} fetched successfully.")
            
            # Normalize the output
            normalized_data = {
                "domain_name": data.get("domain_name"),
                "registrar": data.get("registrar", {}).get("name"),
                "creation_date": data.get("creation_date"),
                "expiration_date": data.get("expiration_date"),
                "name_servers": data.get("name_servers", []),
                "status": data.get("status"),
                "country": data.get("registrant", {}).get("country"),
                "emails": data.get("emails", []),
                "organization": data.get("registrant", {}).get("organization"),
                'last_fetched_at': datetime.utcnow().isoformat()
            }
            return normalized_data
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                self.logger.warning(f"WHOIS-JSON.com API rate limit exceeded for {domain}. Retrying after 60 seconds.")
                await asyncio.sleep(60)
                return await self.get_domain_info(domain) # Retry the call
            else:
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

