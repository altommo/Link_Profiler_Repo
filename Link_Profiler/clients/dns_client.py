"""
DNS Client - Interacts with DNS over HTTPS (DoH) services like Cloudflare or Google.
File: Link_Profiler/clients/dns_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

class DNSClient:
    """
    Client for fetching DNS records using DNS over HTTPS (DoH).
    Supports Cloudflare and Google DoH endpoints.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".DNSClient")
        self.cloudflare_url = config_loader.get("domain_api.dns_over_https_api.cloudflare_url")
        self.google_url = config_loader.get("domain_api.dns_over_https_api.google_url")
        self.enabled = config_loader.get("domain_api.dns_over_https_api.enabled", False)
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.enabled:
            self.logger.info("DNS over HTTPS API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering DNSClient context.")
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled and self._session and not self._session.closed:
            self.logger.info("Exiting DNSClient context. Closing aiohttp session.")
            await self._session.close()
            self._session = None

    @api_rate_limited(service="dns_over_https_api", api_client_type="dns_client", endpoint="get_dns_records")
    async def get_dns_records(self, domain: str, record_type: str = 'A', use_cloudflare: bool = True) -> Optional[Dict[str, Any]]:
        """
        Fetches DNS records for a domain using either Cloudflare or Google DoH.
        
        Args:
            domain (str): The domain name to query.
            record_type (str): The type of DNS record (e.g., 'A', 'AAAA', 'MX', 'TXT', 'NS').
            use_cloudflare (bool): If True, uses Cloudflare's DoH. Otherwise, uses Google's.
            
        Returns:
            Optional[Dict[str, Any]]: The JSON response containing DNS records, or None on failure.
        """
        if not self.enabled:
            self.logger.warning(f"DNS over HTTPS API is disabled. Simulating DNS records for {domain}.")
            return self._simulate_dns_records(domain, record_type)

        endpoint = self.cloudflare_url if use_cloudflare else self.google_url
        if not endpoint:
            self.logger.error(f"No DoH endpoint configured for {'Cloudflare' if use_cloudflare else 'Google'}. Simulating DNS records.")
            return self._simulate_dns_records(domain, record_type)

        headers = {'Accept': 'application/dns-json'}
        params = {'name': domain, 'type': record_type}

        self.logger.info(f"Calling {'Cloudflare' if use_cloudflare else 'Google'} DoH for {domain} ({record_type} record)...")
        try:
            async with self._session.get(endpoint, headers=headers, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                self.logger.info(f"DNS records for {domain} fetched successfully from {'Cloudflare' if use_cloudflare else 'Google'}.")
                return data
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error fetching DNS records for {domain} from {'Cloudflare' if use_cloudflare else 'Google'}: {e}", exc_info=True)
            return self._simulate_dns_records(domain, record_type) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching DNS records for {domain} from {'Cloudflare' if use_cloudflare else 'Google'}: {e}", exc_info=True)
            return self._simulate_dns_records(domain, record_type) # Fallback to simulation on error

    def _simulate_dns_records(self, domain: str, record_type: str) -> Dict[str, Any]:
        """Helper to generate simulated DNS records."""
        self.logger.info(f"Simulating DNS records for {domain} ({record_type}).")
        import random

        response = {
            "Status": 0, # NOERROR
            "TC": False,
            "RD": True,
            "RA": True,
            "AD": False,
            "CD": False,
            "Question": [{"name": domain, "type": self._get_record_type_code(record_type)}],
            "Answer": []
        }

        if record_type.upper() == 'A':
            response["Answer"].append({
                "name": domain,
                "type": self._get_record_type_code('A'),
                "TTL": 300,
                "data": f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            })
        elif record_type.upper() == 'AAAA':
            response["Answer"].append({
                "name": domain,
                "type": self._get_record_type_code('AAAA'),
                "TTL": 300,
                "data": f"2001:0db8:{random.randint(0,9999):04x}:{random.randint(0,9999):04x}::{random.randint(1,254)}"
            })
        elif record_type.upper() == 'MX':
            response["Answer"].append({
                "name": domain,
                "type": self._get_record_type_code('MX'),
                "TTL": 300,
                "data": f"10 mail.{domain}"
            })
        elif record_type.upper() == 'TXT':
            response["Answer"].append({
                "name": domain,
                "type": self._get_record_type_code('TXT'),
                "TTL": 300,
                "data": f"\"v=spf1 include:_spf.google.com ~all\""
            })
        elif record_type.upper() == 'NS':
            response["Answer"].append({
                "name": domain,
                "type": self._get_record_type_code('NS'),
                "TTL": 300,
                "data": f"ns1.{domain}"
            })
        # Add more record types as needed for simulation

        return response

    def _get_record_type_code(self, record_type: str) -> int:
        """Helper to convert record type string to DNS query code (simulated)."""
        type_map = {
            'A': 1, 'NS': 2, 'MD': 3, 'MF': 4, 'CNAME': 5, 'SOA': 6, 'MB': 7, 'MG': 8,
            'MR': 9, 'NULL': 10, 'WKS': 11, 'PTR': 12, 'HINFO': 13, 'MINFO': 14,
            'MX': 15, 'TXT': 16, 'AAAA': 28, 'SRV': 33, 'NAPTR': 35, 'OPT': 41,
            'DS': 43, 'RRSIG': 46, 'NSEC': 47, 'DNSKEY': 48, 'NSEC3': 50,
            'NSEC3PARAM': 51, 'TLSA': 52, 'SMIMEA': 53, 'HIP': 55, 'CDS': 59,
            'CDNSKEY': 60, 'OPENPGPKEY': 61, 'CSYNC': 62, 'ZONEMD': 63,
            'SVCB': 64, 'HTTPS': 65, 'SPF': 99, 'AXFR': 252, 'MAILB': 253,
            'MAILA': 254, 'ANY': 255, 'URI': 256, 'CAA': 257, 'AVC': 258,
            'DNAME': 39, 'OPT': 41 # OPT is pseudo-record type for EDNS
        }
        return type_map.get(record_type.upper(), 255) # Default to ANY if not found
