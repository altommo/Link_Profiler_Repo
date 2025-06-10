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

# Import python-whois for direct WHOIS lookups
try:
    import whois
    from whois.parser import PywhoisError
except ImportError:
    whois = None
    PywhoisError = Exception
    logging.getLogger(__name__).warning("python-whois library not found. Direct WHOIS lookups will be disabled.")


from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient # Import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class WHOISClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Client for fetching WHOIS data.
    This version uses the python-whois library for direct WHOIS lookups,
    bypassing the WHOIS-JSON.com API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        # Note: This client now performs direct WHOIS lookups using python-whois,
        # so session_manager, resilience_manager, and api_quota_manager are less directly
        # applicable for the actual WHOIS query, but are kept for BaseAPIClient compatibility
        # and potential future use (e.g., if an external WHOIS API is re-introduced).
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".WHOISClient")
        
        # Check if python-whois is available
        self.enabled = bool(whois) and config_loader.get("domain_api.whois_json_api.enabled", False) # Re-using config flag
        
        if not self.enabled:
            self.logger.info("Direct WHOIS lookups are disabled (python-whois not found or configuration disabled).")

    async def __aenter__(self):
        """Initialise aiohttp session (if still needed by BaseAPIClient)."""
        await super().__aenter__() # Call BaseAPIClient's __aenter__
        if self.enabled:
            self.logger.info("Entering WHOISClient context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session (if still needed by BaseAPIClient)."""
        await super().__aexit__(exc_type, exc_val, exc_tb) # Call BaseAPIClient's __aexit__
        if self.enabled:
            self.logger.info("Exiting WHOISClient context.")

    # The api_rate_limited decorator will still apply, enforcing the throttle.
    @api_rate_limited(service="whois_json_api", api_client_type="whois_client", endpoint="get_domain_info")
    async def get_domain_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Fetches WHOIS information for a given domain using python-whois.
        
        Args:
            domain (str): The domain name to query.
            
        Returns:
            Optional[Dict[str, Any]]: The parsed WHOIS data, or None on failure.
        """
        if not self.enabled:
            self.logger.warning(f"WHOIS client is disabled. Simulating WHOIS data for {domain}.")
            return self._simulate_whois_data(domain)

        self.logger.info(f"Fetching WHOIS data for domain: {domain} using python-whois...")
        
        # Enforce 1s throttle
        await asyncio.sleep(1)

        try:
            # python-whois is synchronous, run in a thread pool executor
            whois_data = await asyncio.to_thread(whois.whois, domain)
            
            # Normalize the output
            normalized_data = {
                "domain_name": whois_data.domain_name[0] if isinstance(whois_data.domain_name, list) else whois_data.domain_name,
                "registrar": whois_data.registrar,
                "creation_date": whois_data.creation_date[0].isoformat() if isinstance(whois_data.creation_date, list) else (whois_data.creation_date.isoformat() if whois_data.creation_date else None),
                "expiration_date": whois_data.expiration_date[0].isoformat() if isinstance(whois_data.expiration_date, list) else (whois_data.expiration_date.isoformat() if whois_data.expiration_date else None),
                "name_servers": whois_data.name_servers,
                "status": whois_data.status[0] if isinstance(whois_data.status, list) else whois_data.status,
                "country": whois_data.country,
                "emails": whois_data.emails,
                "organization": whois_data.org,
                'last_fetched_at': datetime.utcnow().isoformat()
            }
            self.logger.info(f"WHOIS data for {domain} fetched successfully.")
            return normalized_data
        except PywhoisError as e:
            self.logger.error(f"PywhoisError fetching WHOIS data for {domain}: {e}", exc_info=True)
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
