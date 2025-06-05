"""
Domain Service - Manages fetching and processing domain information.
File: Link_Profiler/services/domain_service.py
"""

import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import asyncio
from datetime import datetime
import json # Import json for serializing/deserializing WHOIS data
import random # Import random for simulation functions

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.api_cache import cached_api_call
from Link_Profiler.core.models import Domain, SEOMetrics # Assuming SEOMetrics is defined in models.py
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager

logger = logging.getLogger(__name__)

class AbstractDomainAPIClient(BaseAPIClient):
    """Client for AbstractAPI Domain Validation and WHOIS."""
    def __init__(self, session_manager: Optional[SessionManager] = None):
        super().__init__(session_manager)
        self.enabled = config_loader.get("domain_api.abstract_api.enabled", False)
        self.api_key = config_loader.get("domain_api.abstract_api.api_key")
        self.base_url = config_loader.get("domain_api.abstract_api.base_url", "https://domain-validation.abstractapi.com/v1/")
        self.whois_base_url = config_loader.get("domain_api.abstract_api.whois_base_url", "https://whois.abstractapi.com/v1/")
        
        if not self.enabled:
            self.logger.info("AbstractAPI Domain Validation is disabled.")
        elif not self.api_key:
            self.logger.warning("AbstractAPI key is missing. AbstractAPI Domain Validation will be disabled.")
            self.enabled = False

    @api_rate_limited(service="domain_api", api_client_type="abstract_api", endpoint="validate_domain")
    @cached_api_call(service="domain_api", endpoint="validate_domain", ttl=86400) # Cache for 24 hours
    async def validate_domain(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """Validates a domain using AbstractAPI."""
        if not self.enabled:
            return None
        
        params = {"api_key": self.api_key, "domain": domain_name}
        try:
            response = await self._make_request("GET", self.base_url, params=params)
            return await response.json()
        except Exception as e:
            self.logger.error(f"Error validating domain {domain_name} with AbstractAPI: {e}")
            return None

    @api_rate_limited(service="domain_api", api_client_type="abstract_api", endpoint="whois_lookup")
    @cached_api_call(service="domain_api", endpoint="whois_lookup", ttl=86400 * 7) # Cache WHOIS for 7 days
    async def whois_lookup(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """Performs a WHOIS lookup using AbstractAPI."""
        if not self.enabled:
            return None
        
        params = {"api_key": self.api_key, "domain": domain_name}
        try:
            response = await self._make_request("GET", self.whois_base_url, params=params)
            return await response.json()
        except Exception as e:
            self.logger.error(f"Error performing WHOIS lookup for {domain_name} with AbstractAPI: {e}")
            return None

class WhoisJsonAPIClient(BaseAPIClient):
    """Client for WHOIS-JSON.com API."""
    def __init__(self, session_manager: Optional[SessionManager] = None):
        super().__init__(session_manager)
        self.enabled = config_loader.get("domain_api.whois_json_api.enabled", False)
        self.api_key = config_loader.get("domain_api.whois_json_api.api_key") # Optional for this API
        self.base_url = config_loader.get("domain_api.whois_json_api.base_url", "https://www.whois-json.com/api/v1/whois")
        
        if not self.enabled:
            self.logger.info("WHOIS-JSON.com API is disabled.")

    @api_rate_limited(service="domain_api", api_client_type="whois_json_api", endpoint="whois_lookup")
    @cached_api_call(service="domain_api", endpoint="whois_json_lookup", ttl=86400 * 7) # Cache WHOIS for 7 days
    async def whois_lookup(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """Performs a WHOIS lookup using WHOIS-JSON.com."""
        if not self.enabled:
            return None
        
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Token {self.api_key}" # Example for token auth
        
        try:
            # WHOIS-JSON.com uses path parameter for domain
            url = f"{self.base_url}/{domain_name}"
            response = await self._make_request("GET", url, headers=headers)
            return await response.json()
        except Exception as e:
            self.logger.error(f"Error performing WHOIS lookup for {domain_name} with WHOIS-JSON.com: {e}")
            return None

class DomainService:
    """
    Service for fetching and processing comprehensive domain information.
    Aggregates data from various sources (WHOIS, DNS, SEO metrics).
    """
    _instance = None

    def __new__(cls, session_manager: Optional[SessionManager] = None):
        if cls._instance is None:
            cls._instance = super(DomainService, cls).__new__(cls)
            cls._instance._initialized = False
            cls._instance.session_manager = session_manager # Store session_manager for clients
        return cls._instance

    def __init__(self, session_manager: Optional[SessionManager] = None):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".DomainService")
        self.session_manager = session_manager # Ensure it's set for this instance

        # Initialize API clients
        self.abstract_api_client = AbstractDomainAPIClient(session_manager=self.session_manager)
        self.whois_json_api_client = WhoisJsonAPIClient(session_manager=self.session_manager)
        
        # Placeholder for other potential clients (e.g., DNS over HTTPS, SEO metrics API)
        # self.dns_client = DNSOverHttpsClient(session_manager=self.session_manager)
        # self.seo_metrics_client = SEOMetricsAPIClient(session_manager=self.session_manager)

    async def __aenter__(self):
        """Enter context for all underlying API clients."""
        await self.abstract_api_client.__aenter__()
        await self.whois_json_api_client.__aenter__()
        # await self.dns_client.__aenter__()
        # await self.seo_metrics_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context for all underlying API clients."""
        await self.abstract_api_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.whois_json_api_client.__aexit__(exc_type, exc_val, exc_tb)
        # await self.dns_client.__aexit__(exc_type, exc_val, exc_tb)
        # await self.seo_metrics_client.__aexit__(exc_type, exc_val, exc_tb)

    async def get_domain_info(self, domain_name: str) -> Optional[Domain]:
        """
        Fetches comprehensive information for a given domain.
        Aggregates data from various sources.
        """
        if not domain_name:
            self.logger.warning("Attempted to get domain info for empty domain_name.")
            return None

        parsed_domain = urlparse(domain_name).netloc or domain_name
        if not parsed_domain:
            self.logger.warning(f"Could not parse domain from '{domain_name}'.")
            return None

        self.logger.info(f"Fetching comprehensive info for domain: {parsed_domain}")

        domain_data: Dict[str, Any] = {"name": parsed_domain}
        
        # --- WHOIS Lookup ---
        whois_data = None
        if self.abstract_api_client.enabled:
            whois_data = await self.abstract_api_client.whois_lookup(parsed_domain)
            if whois_data:
                domain_data["whois_data"] = whois_data
                self.logger.debug(f"AbstractAPI WHOIS data for {parsed_domain} fetched.")
        
        if not whois_data and self.whois_json_api_client.enabled:
            whois_data = await self.whois_json_api_client.whois_lookup(parsed_domain)
            if whois_data:
                domain_data["whois_data"] = whois_data
                self.logger.debug(f"WHOIS-JSON.com WHOIS data for {parsed_domain} fetched.")

        # --- Domain Validation (e.g., check if domain exists, is parked, etc.) ---
        validation_data = None
        if self.abstract_api_client.enabled:
            validation_data = await self.abstract_api_client.validate_domain(parsed_domain)
            if validation_data:
                domain_data["validation_data"] = validation_data
                self.logger.debug(f"AbstractAPI validation data for {parsed_domain} fetched.")
                # Extract basic status from validation data
                domain_data["is_registered"] = validation_data.get("is_registered", False)
                domain_data["is_parked"] = validation_data.get("is_parked", False)
                domain_data["is_dead"] = validation_data.get("is_dead", False)
                domain_data["is_free"] = validation_data.get("is_free", False)
                domain_data["is_spam"] = validation_data.get("is_spam", False) # AbstractAPI provides this

        # --- DNS Records (A, CNAME, MX, NS, TXT) ---
        # This would typically involve a dedicated DNS client or direct dns.resolver calls
        # For now, we'll simulate or leave as placeholder if no client is integrated
        domain_data["dns_records"] = self._simulate_dns_records(parsed_domain)
        
        # --- SEO Metrics (e.g., Domain Authority, Page Authority, Trust Flow, Citation Flow) ---
        # This would involve integration with Moz, Ahrefs, SEMrush APIs
        # For now, simulate
        domain_data["seo_metrics"] = self._simulate_seo_metrics(parsed_domain)

        # --- IP Information ---
        # This would involve IP lookup services
        domain_data["ip_info"] = self._simulate_ip_info(parsed_domain)

        # Construct Domain object
        domain_obj = Domain(
            name=parsed_domain,
            authority_score=domain_data.get('seo_metrics', {}).get('domain_authority', 0),
            trust_score=domain_data.get('seo_metrics', {}).get('trust_flow', 0),
            spam_score=domain_data.get('is_spam', False), # Use is_spam from validation
            registered_date=self._extract_whois_date(whois_data, 'created_date'),
            expiration_date=self._extract_whois_date(whois_data, 'expires_date'),
            registrar=whois_data.get('registrar', '') if whois_data else '',
            is_registered=domain_data.get('is_registered', False),
            is_parked=domain_data.get('is_parked', False),
            is_dead=domain_data.get('is_dead', False),
            # Populate other fields from domain_data
            whois_raw=json.dumps(whois_data) if whois_data else None,
            dns_records=domain_data.get('dns_records', {}),
            ip_address=domain_data.get('ip_info', {}).get('ip_address'),
            country=domain_data.get('ip_info', {}).get('country'),
            seo_metrics=SEOMetrics(**domain_data.get('seo_metrics', {})),
            last_checked=datetime.now()
        )
        
        self.logger.info(f"Successfully compiled info for domain: {parsed_domain}")
        return domain_obj

    def _extract_whois_date(self, whois_data: Optional[Dict[str, Any]], key: str) -> Optional[datetime]:
        """Helper to extract and parse dates from WHOIS data."""
        if whois_data and whois_data.get(key):
            try:
                # AbstractAPI WHOIS dates are often ISO format
                return datetime.fromisoformat(whois_data[key].replace('Z', '+00:00'))
            except ValueError:
                # Fallback for other formats if necessary
                pass
        return None

    def _simulate_dns_records(self, domain_name: str) -> Dict[str, List[str]]:
        """Simulates DNS record lookup."""
        return {
            "A": [f"192.0.2.{random.randint(1, 254)}"],
            "MX": [f"mail.{domain_name}"],
            "NS": [f"ns1.{domain_name}", f"ns2.{domain_name}"],
            "TXT": [f"v=spf1 include:{domain_name} ~all"]
        }

    def _simulate_seo_metrics(self, domain_name: str) -> Dict[str, Any]:
        """Simulates fetching SEO metrics."""
        return {
            "domain_authority": random.randint(10, 90),
            "page_authority": random.randint(10, 90),
            "trust_flow": random.randint(5, 50),
            "citation_flow": random.randint(5, 50),
            "organic_keywords": random.randint(100, 10000),
            "organic_traffic": random.randint(1000, 100000),
            "referring_domains": random.randint(50, 5000)
        }

    def _simulate_ip_info(self, domain_name: str) -> Dict[str, Any]:
        """Simulates IP information lookup."""
        return {
            "ip_address": f"192.0.2.{random.randint(1, 254)}",
            "country": random.choice(["US", "CA", "GB", "DE", "AU"]),
            "city": random.choice(["New York", "Toronto", "London", "Berlin", "Sydney"]),
            "isp": f"ISP-{random.randint(1, 100)}"
        }

# Create a singleton instance
domain_service_instance = DomainService()
