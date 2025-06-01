"""
Domain Service - Provides domain-related information using various API clients.
File: Link_Profiler/services/domain_service.py
"""

import asyncio
import logging
import os
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse
from datetime import datetime, timedelta
import random
import aiohttp
import json
import redis.asyncio as redis

from Link_Profiler.core.models import Domain, DomainHistory
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.monitoring.prometheus_metrics import (
    API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL
)
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.database.database import Database

# New: Import WHOISClient and DNSClient
from Link_Profiler.clients.whois_client import WHOISClient
from Link_Profiler.clients.dns_client import DNSClient

logger = logging.getLogger(__name__)

class BaseDomainAPIClient:
    """
    Base class for a domain information API client.
    Real implementations would connect to external services.
    """
    async def get_domain_availability(self, domain_name: str) -> bool:
        raise NotImplementedError

    async def get_whois_data(self, domain_name: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def __aenter__(self):
        """Async context manager entry for client session."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        pass # No-op for base class

class SimulatedDomainAPIClient(BaseDomainAPIClient):
    """
    A purely simulated client for domain information APIs.
    Generates dummy domain data without making external network calls.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SimulatedDomainAPIClient")

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedDomainAPIClient context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedDomainAPIClient context.")
        pass

    async def get_domain_availability(self, domain_name: str) -> bool:
        """
        Simulates checking domain availability.
        """
        self.logger.info(f"Purely simulating domain availability for: {domain_name}")
        # Simulate availability based on domain name
        return "example" not in domain_name and "test" not in domain_name

    async def get_whois_data(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Simulates fetching WHOIS data.
        """
        self.logger.info(f"Purely simulating WHOIS data for: {domain_name}")
        # Generate dummy WHOIS data
        if "example.com" in domain_name:
            return {
                "domain_name": domain_name,
                "registrar": "Example Registrar",
                "creation_date": "2000-01-01",
                "expiration_date": "2025-01-01",
                "name_servers": ["ns1.example.com", "ns2.example.com"],
                "status": "clientTransferProhibited",
                "emails": ["abuse@example.com"],
                "organization": "Example LLC",
                "country": "US"
            }
        elif "test.com" in domain_name:
            return None # Simulate not found
        else:
            return {
                "domain_name": domain_name,
                "registrar": f"Registrar {random.randint(1, 10)}",
                "creation_date": (datetime.now() - timedelta(days=random.randint(365, 365*10))).strftime("%Y-%m-%d"),
                "expiration_date": (datetime.now() + timedelta(days=random.randint(30, 365*5))).strftime("%Y-%m-%d"),
                "name_servers": [f"ns1.{domain_name}", f"ns2.{domain_name}"],
                "status": "ok",
                "emails": [f"admin@{domain_name}"],
                "organization": f"Org {random.randint(1, 100)}",
                "country": random.choice(["US", "CA", "GB", "DE", "AU"])
            }

class RealDomainAPIClient(BaseDomainAPIClient):
    """
    A client for real domain information APIs.
    This implementation demonstrates where actual API calls would go.
    """
    def __init__(self, api_key: str, base_url: str):
        self.logger = logging.getLogger(__name__ + ".RealDomainAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealDomainAPIClient context.")
        if self._session is None or self._session.closed:
            headers = {"X-API-Key": self.api_key} # Common header for API keys
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealDomainAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @api_rate_limited(service="domain_api", api_client_type="real_api", endpoint="availability")
    async def get_domain_availability(self, domain_name: str) -> bool:
        """
        Fetches domain availability from a real API.
        Replace with actual API call logic for your chosen provider.
        """
        endpoint = f"{self.base_url}/v1/availability" # Hypothetical endpoint
        params = {"domain": domain_name, "apiKey": self.api_key} # Some APIs use query param for key
        self.logger.info(f"Attempting real API call for domain availability: {endpoint}?domain={domain_name}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            
            headers = {"X-API-Key": self.api_key}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data = await response.json()
                # --- Replace with actual parsing logic for your chosen API ---
                # Example: return data.get("available", False)
                self.logger.warning("RealDomainAPIClient: Returning simulated availability. Replace with actual API response parsing.")
                return "example" not in domain_name and "test" not in domain_name # Fallback to simulation
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real domain availability for {domain_name}: {e}. Returning False.")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error in real domain availability fetch for {domain_name}: {e}. Returning False.")
            return False
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

    @api_rate_limited(service="domain_api", api_client_type="real_api", endpoint="whois")
    async def get_whois_data(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetches WHOIS data from a real API.
        Replace with actual API call logic for your chosen provider.
        """
        endpoint = f"{self.base_url}/v1/whois" # Hypothetical endpoint
        params = {"domain": domain_name, "apiKey": self.api_key}
        self.logger.info(f"Attempting real API call for WHOIS data: {endpoint}?domain={domain_name}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            
            headers = {"X-API-Key": self.api_key}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                # --- Replace with actual parsing logic for your chosen API ---
                # Example:
                # return {
                #     "domain_name": data.get("domainName"),
                #     "registrar": data.get("registrarName"),
                #     "creation_date": data.get("createdDate"),
                #     "expiration_date": data.get("expiresDate"),
                #     "name_servers": data.get("nameServers", []),
                #     "status": data.get("status"),
                #     "emails": data.get("contactEmails", []),
                #     "organization": data.get("registrantOrganization"),
                #     "country": data.get("registrantCountry")
                # }
                self.logger.warning("RealDomainAPIClient: Returning simulated WHOIS data. Replace with actual API response parsing.")
                return await SimulatedDomainAPIClient().get_whois_data(domain_name) # Fallback to simulation
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real WHOIS data for {domain_name}: {e}. Returning None.")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in real WHOIS data fetch for {domain_name}: {e}. Returning None.")
            return None
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

class AbstractDomainAPIClient(BaseDomainAPIClient):
    """
    A client for AbstractAPI's Domain API (or similar low-cost/free-tier service).
    Requires an API key.
    """
    def __init__(self, api_key: str, base_url: str, whois_base_url: str):
        self.logger = logging.getLogger(__name__ + ".AbstractDomainAPIClient")
        self.api_key = api_key
        self.base_url = base_url # For domain validation
        self.whois_base_url = whois_base_url # For WHOIS
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.logger.info("Entering AbstractDomainAPIClient context.")
        if self._session is None or self._session.closed:
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("Exiting AbstractDomainAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @api_rate_limited(service="domain_api", api_client_type="abstract_api", endpoint="availability")
    async def get_domain_availability(self, domain_name: str) -> bool:
        """
        Fetches domain availability using AbstractAPI's Domain Validation API.
        """
        endpoint = self.base_url
        params = {"api_key": self.api_key, "domain": domain_name}
        self.logger.info(f"Attempting AbstractAPI Domain API call for availability: {endpoint}?domain={domain_name}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("AbstractDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                # Example parsing for AbstractAPI Domain API
                return data.get("is_available", False)
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching AbstractAPI domain availability for {domain_name}: {e}. Returning False.")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error in AbstractAPI domain availability fetch for {domain_name}: {e}. Returning False.")
            return False
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

    @api_rate_limited(service="domain_api", api_client_type="abstract_api", endpoint="whois")
    async def get_whois_data(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetches WHOIS data using AbstractAPI's WHOIS API.
        """
        endpoint = self.whois_base_url
        params = {"api_key": self.api_key, "domain": domain_name}
        self.logger.info(f"Attempting AbstractAPI WHOIS API call for {domain_name}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("AbstractDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                # Example parsing for AbstractAPI WHOIS API
                return {
                    "domain_name": data.get("domain_name"),
                    "registrar": data.get("registrar_name"),
                    "creation_date": data.get("creation_date"),
                    "expiration_date": data.get("expiration_date"),
                    "name_servers": data.get("name_servers", {}).get("hostnames", []),
                    "status": data.get("status"),
                    "emails": data.get("contact", {}).get("email", []),
                    "organization": data.get("registrant_organization"),
                    "country": data.get("registrant_country")
                }
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching AbstractAPI WHOIS data for {domain_name}: {e}. Returning None.")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in AbstractAPI WHOIS data fetch for {domain_name}: {e}. Returning None.")
            return None
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()


class DomainService:
    """
    Service for querying domain-related information, such as availability and WHOIS data.
    Uses various API clients to perform actual lookups.
    """
    def __init__(self, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600, database: Optional[Database] = None,
                 whois_client: Optional[WHOISClient] = None, dns_client: Optional[DNSClient] = None): # New: Accept WHOISClient and DNSClient
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.api_cache_enabled = config_loader.get("api_cache.enabled", False)
        self.db = database # Store the database instance

        self.whois_client = whois_client
        self.dns_client = dns_client

        # Determine which DomainAPIClient to use for availability based on priority: AbstractAPI > Real (paid) > Simulated
        if config_loader.get("domain_api.abstract_api.enabled"):
            abstract_api_key = config_loader.get("domain_api.abstract_api.api_key")
            abstract_base_url = config_loader.get("domain_api.abstract_api.base_url")
            abstract_whois_base_url = config_loader.get("domain_api.abstract_api.whois_base_url")
            if not abstract_api_key or not abstract_base_url or not abstract_whois_base_url:
                self.logger.warning("AbstractAPI enabled but API key or base_urls not found in config. Falling back to simulated Domain API.")
                self.api_client = SimulatedDomainAPIClient()
            else:
                self.api_client = AbstractDomainAPIClient(api_key=abstract_api_key, base_url=abstract_base_url, whois_base_url=abstract_whois_base_url)
        elif config_loader.get("domain_api.real_api.enabled"):
            real_api_key = config_loader.get("domain_api.real_api.api_key")
            real_api_base_url = config_loader.get("domain_api.real_api.base_url")
            if not real_api_key or not real_api_base_url:
                self.logger.warning("Real Domain API enabled but API key or base_url not found in config. Falling back to simulated Domain API.")
                self.api_client = SimulatedDomainAPIClient()
            else:
                self.api_client = RealDomainAPIClient(api_key=real_api_key, base_url=real_api_base_url)
        else:
            self.logger.info("No specific Domain API enabled. Using SimulatedDomainAPIClient for availability checks.")
            self.api_client = SimulatedDomainAPIClient()

    async def __aenter__(self):
        """Async context manager entry for DomainService."""
        self.logger.debug("Entering DomainService context.")
        await self.api_client.__aenter__() # Enter the primary API client's context
        if self.whois_client:
            await self.whois_client.__aenter__()
        if self.dns_client:
            await self.dns_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for DomainService."""
        self.logger.debug("Exiting DomainService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb) # Exit the primary API client's context
        if self.whois_client:
            await self.whois_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.dns_client:
            await self.dns_client.__aexit__(exc_type, exc_val, exc_tb)

    async def _get_cached_response(self, cache_key: str, service_name: str, endpoint_name: str) -> Optional[Any]:
        if self.api_cache_enabled and self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    API_CACHE_HITS_TOTAL.labels(service=service_name, endpoint=endpoint_name).inc()
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
                else:
                    API_CACHE_MISSES_TOTAL.labels(service=service_name, endpoint=endpoint_name).inc()
            except Exception as e:
                API_CACHE_ERRORS_TOTAL.labels(service=service_name, endpoint=endpoint_name, error_type=type(e).__name__).inc()
                self.logger.error(f"Error retrieving from cache for {cache_key}: {e}", exc_info=True)
        return None

    async def _set_cached_response(self, cache_key: str, data: Any, service_name: str, endpoint_name: str):
        if self.api_cache_enabled and self.redis_client:
            try:
                await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
                API_CACHE_SET_TOTAL.labels(service=service_name, endpoint=endpoint_name).inc()
                self.logger.debug(f"Cached {cache_key} with TTL {self.cache_ttl}")
            except Exception as e:
                API_CACHE_ERRORS_TOTAL.labels(service=service_name, endpoint=endpoint_name, error_type=type(e).__name__).inc()
                self.logger.error(f"Error setting cache for {cache_key}: {e}", exc_info=True)

    async def check_domain_availability(self, domain_name: str) -> bool:
        """
        Checks if a domain name is available for registration.
        Uses caching.
        """
        cache_key = f"domain_availability:{domain_name}"
        cached_result = await self._get_cached_response(cache_key, "domain_api", "availability")
        if cached_result is not None:
            return cached_result

        is_available = await self.api_client.get_domain_availability(domain_name)
        await self._set_cached_response(cache_key, is_available, "domain_api", "availability")
        return is_available

    async def get_whois_info(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves WHOIS information for a given domain name.
        Prioritizes WHOISClient if enabled, otherwise uses primary domain API client.
        Uses caching.
        """
        cache_key = f"whois_info:{domain_name}"
        cached_result = await self._get_cached_response(cache_key, "domain_api", "whois")
        if cached_result is not None:
            return cached_result

        whois_data = None
        if self.whois_client and config_loader.get("domain_api.whois_json_api.enabled"):
            self.logger.info(f"Using WHOISClient to fetch WHOIS data for {domain_name}.")
            whois_data = await self.whois_client.get_domain_info(domain_name)
        else:
            self.logger.info(f"Using primary Domain API client to fetch WHOIS data for {domain_name}.")
            whois_data = await self.api_client.get_whois_data(domain_name)

        if whois_data: # Only cache if data is actually returned
            await self._set_cached_response(cache_key, whois_data, "domain_api", "whois")
        return whois_data

    async def get_dns_records(self, domain_name: str, record_type: str = 'A') -> Optional[Dict[str, Any]]:
        """
        Retrieves DNS records for a given domain name.
        Uses DNSClient if enabled.
        Uses caching.
        """
        cache_key = f"dns_records:{domain_name}:{record_type}"
        cached_result = await self._get_cached_response(cache_key, "domain_api", "dns_records")
        if cached_result is not None:
            return cached_result

        dns_data = None
        if self.dns_client and config_loader.get("domain_api.dns_over_https_api.enabled"):
            self.logger.info(f"Using DNSClient to fetch {record_type} records for {domain_name}.")
            # Default to Cloudflare, can be made configurable
            dns_data = await self.dns_client.get_dns_records(domain_name, record_type, use_cloudflare=True)
        else:
            self.logger.warning(f"DNSClient is not enabled. Cannot fetch DNS records for {domain_name}. Simulating.")
            # Fallback to a simple simulation if DNSClient is not enabled
            dns_data = {
                "Status": 0,
                "Question": [{"name": domain_name, "type": 1}], # Type A
                "Answer": [{"name": domain_name, "type": 1, "TTL": 300, "data": "192.0.2.1"}] # Dummy IP
            }

        if dns_data:
            await self._set_cached_response(cache_key, dns_data, "domain_api", "dns_records")
        return dns_data

    async def get_domain_info(self, domain_name: str) -> Optional[Domain]:
        """
        Combines WHOIS info, availability check, and DNS records into a Domain model.
        Assigns consistent simulated scores if no real API is used.
        Uses caching for underlying API calls.
        Also saves a historical snapshot of the domain's metrics.
        """
        # First, try to load from DB
        domain_obj = self.db.get_domain(domain_name) if self.db else None
        if domain_obj and (datetime.now() - (domain_obj.last_crawled or datetime.min)).days < 7: # Cache for 7 days in DB
            self.logger.info(f"Domain info for {domain_name} found in DB and is recent.")
            self._save_domain_snapshot(domain_obj) # Save a historical snapshot even if from cache, to track progression
            return domain_obj

        self.logger.info(f"Fetching fresh domain info for {domain_name}.")
        
        # Fetch data concurrently
        is_available, whois_data, dns_a_records = await asyncio.gather(
            self.check_domain_availability(domain_name),
            self.get_whois_info(domain_name),
            self.get_dns_records(domain_name, 'A')
        )

        if not whois_data and not is_available:
            self.logger.warning(f"Could not retrieve any info for domain {domain_name}. It might not exist or APIs failed.")
            return None

        # Parse WHOIS data
        creation_date_str = whois_data.get("creation_date") if whois_data else None
        age_days = None
        if creation_date_str:
            try:
                creation_date = self.parse_date_robustly(creation_date_str)
                if creation_date:
                    age_days = (datetime.now() - creation_date).days
            except Exception as e:
                self.logger.warning(f"Could not parse creation_date '{creation_date_str}' for {domain_name}: {e}")

        # Extract IP address from DNS A records
        ip_address = None
        if dns_a_records and dns_a_records.get("Answer"):
            for answer in dns_a_records["Answer"]:
                if answer.get("type") == 1 and "data" in answer: # Type 1 is A record
                    ip_address = answer["data"]
                    break

        # Simulate scores if not from a real source or if they are missing
        # These scores would ideally come from a dedicated domain metrics API (e.g., Moz, Ahrefs)
        # For now, generate consistent dummy scores based on domain name hash
        domain_hash = sum(ord(c) for c in domain_name.lower())
        authority_score = (domain_hash % 90) + 10 # 10-99
        trust_score = round(random.uniform(0.1, 0.9), 2)
        spam_score = round(random.uniform(0.05, 0.5), 2)

        # If domain_obj exists, update its fields; otherwise, create new
        if domain_obj:
            domain_obj.authority_score = authority_score
            domain_obj.trust_score = trust_score
            domain_obj.spam_score = spam_score
            domain_obj.age_days = age_days
            domain_obj.country = whois_data.get("country") if whois_data else None
            domain_obj.ip_address = ip_address # Use fetched IP
            domain_obj.whois_data = whois_data if whois_data else {}
            domain_obj.last_crawled = datetime.now()
        else:
            domain_obj = Domain(
                name=domain_name,
                authority_score=authority_score,
                trust_score=trust_score,
                spam_score=spam_score,
                age_days=age_days,
                country=whois_data.get("country") if whois_data else None,
                ip_address=ip_address, # Use fetched IP
                whois_data=whois_data if whois_data else {},
                first_seen=creation_date,
                last_crawled=datetime.now()
            )
        
        if self.db:
            self.db.save_domain(domain_obj)
            self._save_domain_snapshot(domain_obj) # Save historical snapshot
            self.logger.info(f"Domain info for {domain_name} saved/updated in DB and snapshot taken.")

        return domain_obj

    def parse_date_robustly(self, date_str: str) -> Optional[datetime]:
        """Attempts to parse a date string using common formats."""
        formats = [
            "%Y-%m-%d", "%Y/%m/%d", "%m-%d-%Y", "%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", # ISO format and common datetime
            "%d-%b-%Y", "%d %b %Y" # e.g., 01-Jan-2000
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        self.logger.warning(f"Could not parse date string: {date_str}")
        return None

    def _save_domain_snapshot(self, domain: Domain):
        """Creates and saves a historical snapshot of a domain's current metrics."""
        if not self.db:
            self.logger.warning("Database instance not available. Skipping domain history snapshot.")
            return
        
        snapshot = DomainHistory(
            domain_name=domain.name,
            snapshot_date=datetime.now(),
            authority_score=domain.authority_score,
            trust_score=domain.trust_score,
            spam_score=domain.spam_score,
            total_backlinks=domain.total_backlinks,
            referring_domains=domain.referring_domains
        )
        try:
            self.db.save_domain_history(snapshot)
            self.logger.debug(f"Saved historical snapshot for domain {domain.name}.")
        except Exception as e:
            self.logger.error(f"Error saving historical domain snapshot for {domain.name}: {e}", exc_info=True)

    async def get_domain_authority_progression(self, domain_name: str, num_snapshots: int = 12) -> List[DomainHistory]:
        """
        Retrieves the historical progression of a domain's authority metrics.

        Args:
            domain_name: The domain for which to retrieve historical data.
            num_snapshots: The maximum number of recent historical snapshots to retrieve.

        Returns:
            A list of DomainHistory objects, sorted by snapshot_date (most recent first).
        """
        if not self.db:
            self.logger.error("Database instance not available. Cannot retrieve domain authority progression.")
            return []
        
        self.logger.info(f"Retrieving {num_snapshots} historical snapshots for domain {domain_name}.")
        history = self.db.get_domain_history(domain_name, num_snapshots)
        return history
