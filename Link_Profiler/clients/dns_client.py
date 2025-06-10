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

# Import dnspython for direct DNS queries
try:
    import dns.resolver
    import dns.exception
except ImportError:
    dns = None
    logging.getLogger(__name__).warning("dnspython library not found. Direct DNS lookups will be disabled.")


from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient # Import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class DNSClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Client for performing DNS lookups using dnspython.
    This version performs direct DNS queries, bypassing DNS-over-HTTPS providers.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None): # New: Accept APIQuotaManager
        # Note: This client now performs direct DNS lookups using dnspython,
        # so session_manager, resilience_manager, and api_quota_manager are less directly
        # applicable for the actual DNS query, but are kept for BaseAPIClient compatibility
        # and potential future use.
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".DNSClient")
        
        # Check if dnspython is available
        self.enabled = bool(dns) and config_loader.get("domain_api.dns_over_https_api.enabled", False) # Re-using config flag
        
        if not self.enabled:
            self.logger.info("Direct DNS lookups are disabled (dnspython not found or configuration disabled).")

    async def __aenter__(self):
        """Async context manager entry for client session (if still needed by BaseAPIClient)."""
        await super().__aenter__() # Call BaseAPIClient's __aenter__
        if self.enabled:
            self.logger.info("Entering DNSClient context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session (if still needed by BaseAPIClient)."""
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

        self.logger.info(f"Resolving DNS for {domain} ({record_type} record) using dnspython...")
        
        # Enforce 0.2s throttle
        await asyncio.sleep(0.2)

        try:
            # dnspython is synchronous, run in a thread pool executor
            answers = await asyncio.to_thread(dns.resolver.resolve, domain, record_type)
            
            for rdata in answers:
                if record_type == "A" or record_type == "AAAA":
                    return str(rdata) # Return IP address
                else:
                    return str(rdata) # Return string representation for other types (e.g., NS, MX, TXT)
            return None
        except dns.exception.DNSException as e:
            self.logger.error(f"DNSException resolving {record_type} record for {domain}: {e}. Returning None.", exc_info=True)
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

        self.logger.info(f"Fetching all DNS records for {domain} using dnspython...")
        
        # Enforce 0.2s throttle
        await asyncio.sleep(0.2)

        record_types = ["A", "AAAA", "NS", "MX", "TXT", "CNAME", "SOA", "SRV"] # Common record types
        all_records = []
        now_iso = datetime.utcnow().isoformat()

        for rtype in record_types:
            try:
                # dnspython is synchronous, run in a thread pool executor
                answers = await asyncio.to_thread(dns.resolver.resolve, domain, rtype)
                for rdata in answers:
                    all_records.append({
                        "name": domain,
                        "type": rtype,
                        "data": str(rdata),
                        "TTL": rdata.ttl if hasattr(rdata, 'ttl') else None, # TTL might not be present for all record types
                        "last_fetched_at": now_iso
                    })
            except dns.exception.DNSException as e:
                self.logger.debug(f"No {rtype} record found or error for {domain}: {e}")
                continue # Continue to next record type
            except Exception as e:
                self.logger.error(f"Error fetching {rtype} records for {domain}: {e}", exc_info=True)
                continue

        if not all_records:
            self.logger.info(f"No DNS records found for {domain}.")
        return all_records

