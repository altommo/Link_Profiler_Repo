"""
Domain Service - Manages fetching and processing domain information.
File: Link_Profiler/services/domain_service.py
"""

import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import asyncio
from datetime import datetime
import json  # Import json for serializing/deserializing WHOIS data
import random  # Import random for simulation functions
import dns.asyncresolver  # For real DNS lookups
import aiohttp # Import aiohttp for ClientError

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.api_cache import cached_api_call
from Link_Profiler.core.models import Domain, SEOMetrics # Assuming SEOMetrics is defined in models.py
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class AbstractDomainAPIClient(BaseAPIClient):
    """Client for AbstractAPI Domain Validation and WHOIS."""
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept resilience_manager
        super().__init__(session_manager, resilience_manager) # Pass resilience_manager to BaseAPIClient
        self.enabled = config_loader.get("domain_api.abstract_api.enabled", False)
        self.api_key = config_loader.get("domain_api.abstract_api.api_key")
        self.base_url = config_loader.get("domain_api.abstract_api.base_url", "https://domain-validation.abstractapi.com/v1/")
        self.whois_base_url = config_loader.get("domain_api.abstract_api.whois_base_url", "https://whois.abstractapi.com/v1/")
        
        # Resilience manager check is now handled in BaseAPIClient's __init__
        # if self.enabled and self.resilience_manager is None:
        #     raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

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
            # _make_request now handles resilience
            response_data = await self._make_request("GET", self.base_url, params=params)
            return response_data
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
            # _make_request now handles resilience
            response_data = await self._make_request("GET", self.whois_base_url, params=params)
            return response_data
        except Exception as e:
            self.logger.error(f"Error performing WHOIS lookup for {domain_name} with AbstractAPI: {e}")
            return None

class WhoisJsonAPIClient(BaseAPIClient):
    """Client for WHOIS-JSON.com API."""
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept resilience_manager
        super().__init__(session_manager, resilience_manager) # Pass resilience_manager to BaseAPIClient
        self.enabled = config_loader.get("domain_api.whois_json_api.enabled", False)
        self.api_key = config_loader.get("domain_api.whois_json_api.api_key") # Optional for this API
        self.base_url = config_loader.get("domain_api.whois_json_api.base_url", "https://www.whois-json.com/api/v1/whois")
        
        # Resilience manager check is now handled in BaseAPIClient's __init__
        # if self.enabled and self.resilience_manager is None:
        #     raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

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
            # _make_request now handles resilience
            response_data = await self._make_request("GET", url, headers=headers)
            return response_data
        except Exception as e:
            self.logger.error(f"Error performing WHOIS lookup for {domain_name} with WHOIS-JSON.com: {e}")
            return None

class DomainService:
    """
    Service for fetching and processing comprehensive domain information.
    Aggregates data from various sources (WHOIS, DNS, SEO metrics).
    """
    _instance = None

    def __new__(cls, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept resilience_manager
        if cls._instance is None:
            cls._instance = super(DomainService, cls).__new__(cls)
            cls._instance._initialized = False
            cls._instance.session_manager = session_manager # Store session_manager for clients
            cls._instance.resilience_manager = resilience_manager # New: Store resilience_manager
        return cls._instance

    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept resilience_manager
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".DomainService")
        self.session_manager = session_manager # Ensure it's set for this instance
        self.resilience_manager = resilience_manager # Ensure it's set for this instance
        if self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")


        # Initialize API clients, passing the resilience_manager
        self.abstract_api_client = AbstractDomainAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)
        self.whois_json_api_client = WhoisJsonAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)

        # Configuration for live lookups
        self.allow_live = config_loader.get("domain_api.domain_service.allow_live", False)
        self.dns_over_https_enabled = config_loader.get("domain_api.dns_over_https_api.enabled", False)
        self.cloudflare_doh_url = config_loader.get("domain_api.dns_over_https_api.cloudflare_url")
        self.google_doh_url = config_loader.get("domain_api.dns_over_https_api.google_url")
        self.seo_metrics_enabled = config_loader.get("domain_api.seo_metrics_api.enabled", False)
        self.seo_metrics_base_url = config_loader.get("domain_api.seo_metrics_api.base_url", "https://openpagerank.com/api/v1.0/getPageRank")
        self.seo_metrics_api_key = config_loader.get("domain_api.seo_metrics_api.api_key")
        self.ip_info_enabled = config_loader.get("domain_api.ip_info_api.enabled", False)
        self.ip_info_base_url = config_loader.get("domain_api.ip_info_api.base_url", "http://ip-api.com/json")
        self.ip_info_api_key = config_loader.get("domain_api.ip_info_api.api_key")
        
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

        # --- DNS Records (A, AAAA, MX, NS, TXT) ---
        domain_data["dns_records"] = await self._fetch_dns_records(parsed_domain)
        
        # --- SEO Metrics (e.g., Domain Authority, Page Authority, Trust Flow, Citation Flow) ---
        domain_data["seo_metrics"] = await self._fetch_seo_metrics(parsed_domain)

        # --- IP Information ---
        domain_data["ip_info"] = await self._fetch_ip_info(parsed_domain)

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

    async def _fetch_dns_records(self, domain_name: str) -> Dict[str, List[str]]:
        """Fetch DNS records using DNS over HTTPS or dnspython if enabled."""
        if not self.allow_live:
            self.logger.debug(
                "Live DNS lookups disabled in configuration; using simulated records."
            )
            return self._simulate_dns_records(domain_name)

        if self.dns_over_https_enabled and (self.cloudflare_doh_url or self.google_doh_url):
            doh_url = self.cloudflare_doh_url or self.google_doh_url
            records: Dict[str, List[str]] = {}
            for rtype in ["A", "AAAA", "MX", "NS", "TXT"]:
                try:
                    resp = await self.resilience_manager.execute_with_resilience( # Use resilience_manager
                        lambda: self.session_manager.get(doh_url, params={"name": domain_name, "type": rtype}, headers={"Accept": "application/dns-json"}),
                        url=doh_url # Use doh_url for circuit breaker naming
                    )
                    data = await resp.json()
                    answers = data.get("Answer") or data.get("answer") or []
                    if answers:
                        records[rtype] = [a.get("data") for a in answers if a.get("data")]
                except aiohttp.ClientError as e:
                    self.logger.error(f"DNS over HTTPS client error for {domain_name} {rtype}: {e}")
                except Exception as e:
                    self.logger.error(f"DNS over HTTPS error for {domain_name} {rtype}: {e}")
            if records:
                return records

        # Fallback to local DNS resolver if DOH not configured or failed
        try:
            resolver = dns.asyncresolver.Resolver()
            records: Dict[str, List[str]] = {}
            for rtype in ["A", "AAAA", "MX", "NS", "TXT"]:
                try:
                    # dns.asyncresolver.resolve is already async, no need for execute_with_resilience
                    answers = await resolver.resolve(domain_name, rtype)
                    records[rtype] = [r.to_text() for r in answers]
                except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                    continue
                except Exception as e:
                    self.logger.error(f"DNS lookup error for {domain_name} {rtype}: {e}")
            if records:
                return records
        except Exception as e:
            self.logger.error(f"DNS lookup failed for {domain_name}: {e}")

        self.logger.debug(
            f"Falling back to simulated DNS records for {domain_name}."
        )
        return self._simulate_dns_records(domain_name)

    async def _fetch_seo_metrics(self, domain_name: str) -> Dict[str, Any]:
        """Fetch SEO metrics using external API if enabled."""
        if not self.allow_live or not self.seo_metrics_enabled:
            self.logger.debug(
                "Live SEO metric lookups disabled; returning simulated metrics."
            )
            return self._simulate_seo_metrics(domain_name)

        headers = {}
        if self.seo_metrics_api_key:
            headers["API-OPR"] = self.seo_metrics_api_key

        try:
            params = {"domains[]": domain_name}
            resp = await self.resilience_manager.execute_with_resilience( # Use resilience_manager
                lambda: self.session_manager.get(self.seo_metrics_base_url, params=params, headers=headers),
                url=self.seo_metrics_base_url # Use base_url for circuit breaker naming
            )
            data = await resp.json()
            result = None
            if isinstance(data, dict):
                if "response" in data and isinstance(data["response"], list) and data["response"]:
                    result = data["response"][0]
                elif "results" in data and isinstance(data["results"], list) and data["results"]:
                    result = data["results"][0]
            if result:
                return {
                    "domain_authority": result.get("page_rank_integer"),
                    "page_authority": result.get("page_rank_decimal"),
                    "referring_domains": result.get("rank"),
                    "last_fetched_at": datetime.utcnow().isoformat()
                }
        except aiohttp.ClientError as e:
            self.logger.error(f"SEO metrics client error for {domain_name}: {e}")
        except Exception as e:
            self.logger.error(f"SEO metrics lookup failed for {domain_name}: {e}")

        self.logger.debug(
            f"Falling back to simulated SEO metrics for {domain_name}."
        )
        return self._simulate_seo_metrics(domain_name)

    async def _fetch_ip_info(self, domain_name: str) -> Dict[str, Any]:
        """Fetch IP information using external API if enabled."""
        if not self.allow_live or not self.ip_info_enabled:
            self.logger.debug(
                "Live IP information lookups disabled; using simulated data."
            )
            return self._simulate_ip_info(domain_name)

        params = {}
        if self.ip_info_api_key:
            params["token"] = self.ip_info_api_key

        try:
            url = f"{self.ip_info_base_url.rstrip('/')}/{domain_name}"
            resp = await self.resilience_manager.execute_with_resilience( # Use resilience_manager
                lambda: self.session_manager.get(url, params=params),
                url=url # Use specific URL for circuit breaker naming
            )
            data = await resp.json()
            if data.get("status", "success") == "success":
                return {
                    "ip_address": data.get("query"),
                    "country": data.get("country"),
                    "city": data.get("city"),
                    "isp": data.get("isp"),
                    "last_fetched_at": datetime.utcnow().isoformat()
                }
        except aiohttp.ClientError as e:
            self.logger.error(f"IP info client error for {domain_name}: {e}")
        except Exception as e:
            self.logger.error(f"IP info lookup failed for {domain_name}: {e}")

        self.logger.debug(
            f"Falling back to simulated IP info for {domain_name}."
        )
        return self._simulate_ip_info(domain_name)

    def _simulate_dns_records(self, domain_name: str) -> Dict[str, List[str]]:
        """Simulates DNS record lookup used as a fallback."""
        self.logger.debug(f"Simulating DNS records for {domain_name}.")
        return {
            "A": [f"192.0.2.{random.randint(1, 254)}"],
            "MX": [f"mail.{domain_name}"],
            "NS": [f"ns1.{domain_name}", f"ns2.{domain_name}"],
            "TXT": [f"v=spf1 include:{domain_name} ~all"]
        }

    def _simulate_seo_metrics(self, domain_name: str) -> Dict[str, Any]:
        """Simulates fetching SEO metrics used as a fallback."""
        self.logger.debug(f"Simulating SEO metrics for {domain_name}.")
        return {
            "domain_authority": random.randint(10, 90),
            "page_authority": random.randint(10, 90),
            "trust_flow": random.randint(5, 50),
            "citation_flow": random.randint(5, 50),
            "organic_keywords": random.randint(100, 10000),
            "organic_traffic": random.randint(1000, 100000),
            "referring_domains": random.randint(50, 5000),
            "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
        }

    def _simulate_ip_info(self, domain_name: str) -> Dict[str, Any]:
        """Simulates IP information lookup used as a fallback."""
        self.logger.debug(f"Simulating IP info for {domain_name}.")
        return {
            "ip_address": f"192.0.2.{random.randint(1, 254)}",
            "country": random.choice(["US", "CA", "GB", "DE", "AU"]),
            "city": random.choice(["New York", "Toronto", "London", "Berlin", "Sydney"]),
            "isp": f"ISP-{random.randint(1, 100)}",
            "last_fetched_at": datetime.utcnow().isoformat() # Add last_fetched_at
        }

# Create a singleton instance
# This will be initialized in main.py's lifespan with proper dependencies
# domain_service_instance = DomainService()
