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

        provider_url = random.choice(self.providers) # Randomly choose a provider
        params = {"name": domain, "type": record_type}
        headers = {"Accept": "application/dns-json"} # Standard for DoH JSON

        self.logger.info(f"Resolving DNS for {domain} ({record_type} record) using {provider_url}...")

        try:
            # Use resilience manager for the actual HTTP request
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

        provider_url = random.choice(self.providers)
        params = {"name": domain, "type": "ANY"} # Request all record types
        headers = {"Accept": "application/dns-json"}

        self.logger.info(f"Fetching all DNS records for {domain} using {provider_url}...")

        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(provider_url, params=params, headers=headers, timeout=15),
                url=provider_url # Pass the URL for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            
            if data and data.get("Answer"):
                return data["Answer"]
            self.logger.info(f"No DNS records found for {domain}.")
            return []

        except Exception as e:
            self.logger.error(f"Error fetching all DNS records for {domain}: {e}. Returning empty list.", exc_info=True)
            return []

