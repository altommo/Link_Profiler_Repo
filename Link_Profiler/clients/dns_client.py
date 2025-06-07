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
from Link_Profiler.clients.base_client import BaseAPIClient # Import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class DNSClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Client for performing DNS lookups using DNS-over-HTTPS (DoH) providers.
    Supports Cloudflare and Google DoH endpoints.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None): # New: Accept APIQuotaManager
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".DNSClient")
        self.cloudflare_url = config_loader.get("domain_api.dns_over_https_api.cloudflare_url")
        self.google_url = config_loader.get("domain_api.dns_over_https_api.google_url")
        self.enabled = config_loader.get("domain_api.dns_over_https_api.enabled", False)
        
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
        await super().__aenter__() # Call BaseAPIClient's __aenter__
        if self.enabled:
            self.logger.info("Entering DNSClient context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        await super().__aexit__(exc_type, exc_val, exc_tb) # Call BaseAPIClient's __aexit__
        if self.enabled:
            self.logger.info("Exiting DNSClient context.")

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
            # Use _make_request which handles throttling, resilience, and performance recording
            data = await self._make_request("GET", provider_url, params=params, headers=headers)
            
            if data and data.get("Answer"):
                for answer in data["Answer"]:
                    if answer["type"] == 1 and record_type == "A": # A record
                        return answer["data"]
                    if answer["type"] == 28 and record_type == "AAAA": # AAAA record
                        return answer["data"]
                self.logger.info(f"No {record_type} record found for {domain}.")
                return None
            return None # No data or no answer section
        except aiohttp.ClientResponseError as e:
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

        provider_url = random.choice(self.providers)
        params = {"name": domain, "type": "ANY"} # Request all record types
        headers = {"Accept": "application/dns-json"}

        self.logger.info(f"Fetching all DNS records for {domain} using {provider_url}...")

        try:
            # Use _make_request which handles throttling, resilience, and performance recording
            data = await self._make_request("GET", provider_url, params=params, headers=headers)
            
            if data and data.get("Answer"):
                # last_fetched_at is already added by _make_request to the top-level dict
                normalized_records = []
                for answer in data["Answer"]:
                    normalized_records.append({
                        "name": answer.get("name"),
                        "type": answer.get("type"), # Numeric type
                        "type_str": {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 15: "MX", 16: "TXT", 28: "AAAA", 33: "SRV", 65: "HTTPS"}.get(answer.get("type"), "UNKNOWN"), # Map numeric type to string
                        "TTL": answer.get("TTL"),
                        "data": answer.get("data"),
                        "last_fetched_at": data.get('last_fetched_at') # Get from _make_request
                    })
                return normalized_records
            else:
                self.logger.info(f"No DNS records found for {domain}.")
                return []
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Network/API error fetching all DNS records for {domain}: {e}. Returning empty list.", exc_info=True)
            return []
        except Exception as e:
            self.logger.error(f"Error fetching all DNS records for {domain}: {e}. Returning empty list.", exc_info=True)
            return []

