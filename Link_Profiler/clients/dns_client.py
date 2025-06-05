"""
DNS Client - Performs DNS lookups (e.g., A, AAAA, NS, MX records).
File: Link_Profiler/clients/dns_client.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import aiohttp
import json
import random
import time # Import time for time.monotonic()
from datetime import datetime # For last_fetched_at

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class DNSClient:
    """
    Client for performing DNS lookups using DNS-over-HTTPS (DoH) providers.
    Supports Cloudflare and Google DoH endpoints.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept ResilienceManager
        self.logger = logging.getLogger(__name__ + ".DNSClient")
        self.cloudflare_url = config_loader.get("domain_api.dns_over_https_api.cloudflare_url")
        self.google_url = config_loader.get("domain_api.dns_over_https_api.google_url")
        self.enabled = config_loader.get("domain_api.dns_over_https_api.enabled", False)
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager # Avoid name collision
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to DNSClient. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to DNSClient. Falling back to global instance.")

        self._last_call_time: float = 0.0 # For explicit throttling

        self.providers = []
        if self.cloudflare_url:
            self.providers.append(self.cloudflare_url)
        if self.google_url:
            self.providers.append(self.google_url)
        
        if not self.enabled:
            self.logger.info("DNS over HTTPS API is disabled by configuration.")
        elif not self.providers:
            self.logger.error("DNS over HTTPS API enabled but no provider URLs configured.")
            self.enabled = False

    async def __aenter__(self):
        """Async context manager entry for client session."""
        if self.enabled:
            self.logger.info("Entering DNSClient context.")
            await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        if self.enabled:
            self.logger.info("Exiting DNSClient context.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def _throttle(self):
        """Ensures at least 0.2 second delay between calls to DoH providers."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < 0.2:
            wait_time = 0.2 - elapsed
            self.logger.debug(f"Throttling DNS API. Waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)
        self._last_call_time = time.monotonic()

    @api_rate_limited(service="dns_over_https_api", api_client_type="dns_client", endpoint="resolve_domain")
    async def resolve_domain(self, domain: str, record_type: str = "A") -> Optional[str]:
        """
        Performs a DNS lookup for a given domain and record type.
        Returns the first IP address found for 'A' or 'AAAA' records.
        """
        if not self.enabled:
            self.logger.warning("DNSClient is disabled. Cannot perform DNS lookup.")
            return None

        if not self.providers:
            self.logger.error("No DNS-over-HTTPS providers configured.")
            return None

        await self._throttle() # Apply explicit throttling

        provider_url = random.choice(self.providers) # Randomly choose a provider
        params = {"name": domain, "type": record_type}
        headers = {"Accept": "application/dns-json"} # Standard for DoH JSON

        self.logger.info(f"Resolving DNS for {domain} ({record_type} record) using {provider_url}...")

        try:
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(provider_url, params=params, headers=headers, timeout=10),
                url=provider_url # Pass the URL for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            
            if data and data.get("Answer"):
                for answer in data["Answer"]:
                    if answer["type"] == 1 and record_type == "A": # A record
                        return answer["data"]
                    if answer["type"] == 28 and record_type == "AAAA": # AAAA record
                        return answer["data"]
                self.logger.info(f"No {record_type} record found for {domain}.")
                return None

        except aiohttp.ClientResponseError as e:
            if e.status in (429, 500, 502, 503, 504):
                self.logger.warning(f"DNS API returned {e.status} for {domain}. Retrying after 1 second.")
                await asyncio.sleep(1)
                return await self.resolve_domain(domain, record_type) # Retry the call
            else:
                self.logger.error(f"Network/API error resolving DNS for {domain}: {e}. Returning None.", exc_info=True)
                return None
        except Exception as e:
            self.logger.error(f"Error resolving DNS for {domain}: {e}. Returning None.", exc_info=True)
            return None

    @api_rate_limited(service="dns_over_https_api", api_client_type="dns_client", endpoint="get_all_records")
    async def get_all_records(self, domain: str) -> List[Dict[str, Any]]:
        """
        Fetches all available DNS records for a given domain.
        """
        if not self.enabled:
            self.logger.warning("DNSClient is disabled. Cannot fetch all DNS records.")
            return []

        if not self.providers:
            self.logger.error("No DNS-over-HTTPS providers configured.")
            return []

        await self._throttle() # Apply explicit throttling

        provider_url = random.choice(self.providers)
        params = {"name": domain, "type": "ANY"} # Request all record types
        headers = {"Accept": "application/dns-json"}

        self.logger.info(f"Fetching all DNS records for {domain} using {provider_url}...")

        try:
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(provider_url, params=params, headers=headers, timeout=15),
                url=provider_url # Pass the URL for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            
            if data and data.get("Answer"):
                # Add last_fetched_at to each answer entry
                now = datetime.utcnow().isoformat()
                normalized_records = []
                for answer in data["Answer"]:
                    normalized_records.append({
                        "name": answer.get("name"),
                        "type": answer.get("type"), # Numeric type
                        "type_str": {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 15: "MX", 16: "TXT", 28: "AAAA", 33: "SRV", 65: "HTTPS"}.get(answer.get("type"), "UNKNOWN"), # Map numeric type to string
                        "TTL": answer.get("TTL"),
                        "data": answer.get("data"),
                        "last_fetched_at": now
                    })
                return normalized_records
            else:
                self.logger.info(f"No DNS records found for {domain}.")
                return []

        except aiohttp.ClientResponseError as e:
            if e.status in (429, 500, 502, 503, 504):
                self.logger.warning(f"DNS API returned {e.status} for {domain}. Retrying after 1 second.")
                await asyncio.sleep(1)
                return await self.get_all_records(domain) # Retry the call
            else:
                self.logger.error(f"Network/API error fetching all DNS records for {domain}: {e}. Returning empty list.", exc_info=True)
                return []
        except Exception as e:
            self.logger.error(f"Error fetching all DNS records for {domain}: {e}. Returning empty list.", exc_info=True)
            return []

