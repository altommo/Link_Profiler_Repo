"""
Domain Service - Provides functionalities related to domain information.
File: Link_Profiler/services/domain_service.py
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import random
from datetime import datetime # Import datetime for parsing WHOIS dates
import aiohttp # Import aiohttp
import os # Import os to read environment variables
import json # Import json for caching
import redis.asyncio as redis # Import redis for type hinting

from Link_Profiler.core.models import Domain # Changed to absolute import
from Link_Profiler.config.config_loader import config_loader # Import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited # Import the rate limiter
from Link_Profiler.monitoring.prometheus_metrics import ( # Import Prometheus metrics
    API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL
)

logger = logging.getLogger(__name__)

# --- Placeholder for a future Domain API Client ---
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


# --- Simulated Domain API Client ---
class SimulatedDomainAPIClient(BaseDomainAPIClient):
    """
    A simulated client for domain information APIs.
    Generates dummy domain data with consistent scores for testing.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SimulatedDomainAPIClient")
        self._session: Optional[aiohttp.ClientSession] = None # For simulating network calls

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedDomainAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedDomainAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_domain_availability(self, domain_name: str) -> bool:
        """
        Simulates checking if a domain name is available for registration.
        Uses aiohttp to simulate a network call.
        """
        self.logger.debug(f"Simulating API call for availability of: {domain_name}")
        
        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("SimulatedDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession()
            close_session_after_use = True

        try:
            async with session_to_use.get(f"http://localhost:8080/simulate_availability/{domain_name}") as response:
                # We don't care about the actual response, just that the request was made
                pass
        except aiohttp.ClientConnectorError:
            # This is expected if localhost:8080 is not running, simulating network activity
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated availability check: {e}")
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

        # Actual simulated logic
        if domain_name.lower() in ["example.com", "testdomain.org", "available.net"]:
            return True
        elif domain_name.lower() in ["google.com", "microsoft.com", "apple.com"]:
            return False
        else:
            return random.choice([True, False])

    async def get_whois_data(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Simulates fetching WHOIS information for a domain.
        Uses aiohttp to simulate a network call.
        """
        self.logger.debug(f"Simulating API call for WHOIS info of: {domain_name}")
        
        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("SimulatedDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession()
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(f"http://localhost:8080/simulate_whois/{domain_name}") as response:
                pass
        except aiohttp.ClientConnectorError:
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated WHOIS check: {e}")
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

        # Actual simulated logic
        if domain_name.lower() == "example.com":
            return {
                "domain_name": "EXAMPLE.COM",
                "registrar": "IANA",
                "creation_date": "1995-08-14",
                "expiration_date": "2025-08-13",
                "name_servers": ["A.IANA-SERVERS.NET", "B.IANA-SERVERS.NET"],
                "status": "clientDeleteProhibited https://icann.org/epp#clientDeleteProhibited",
                "emails": ["abuse@iana.org"],
                "updated_date": "2023-08-14"
            }
        elif domain_name.lower() == "google.com":
            return {
                "domain_name": "GOOGLE.COM",
                "registrar": "MarkMonitor Inc.",
                "creation_date": "1997-09-15",
                "expiration_date": "2028-09-14",
                "name_servers": ["NS1.GOOGLE.COM", "NS2.GOOGLE.COM"],
                "status": "clientDeleteProhibited https://icann.org/epp#clientDeleteProhibited",
                "emails": ["abuse-contact@markmonitor.com"],
                "updated_date": "2023-09-15"
            }
        else:
            return {
                "domain_name": domain_name.upper(),
                "registrar": "Simulated Registrar",
                "creation_date": "2020-01-01",
                "expiration_date": "2025-01-01",
                "name_servers": ["NS1.SIMULATED.COM", "NS2.SIMULATED.COM"],
                "status": "ok",
                "emails": [f"admin@{domain_name}"],
                "updated_date": "2023-01-01"
            }

# --- Real Domain API Client (Placeholder for actual integration) ---
class RealDomainAPIClient(BaseDomainAPIClient):
    """
    A client for real domain information APIs.
    You would replace the placeholder logic with actual API calls.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.real-domain-provider.com"):
        self.logger = logging.getLogger(__name__ + ".RealDomainAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealDomainAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}"})
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
        Simulates checking domain availability via a real API.
        Replace this with actual API call logic.
        """
        endpoint = f"{self.base_url}/v1/domain/availability"
        params = {"domain": domain_name}
        self.logger.info(f"Making real API call for availability: {endpoint}?domain={domain_name}")
        
        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}"})
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status() # Raise an exception for HTTP errors
                
                # Fallback to simulated logic for actual return value
                return SimulatedDomainAPIClient().get_domain_availability(domain_name)
        except aiohttp.ClientError as e:
            self.logger.error(f"Error checking real domain availability for {domain_name}: {e}")
            return False # Assume not available on error
        except Exception as e:
            self.logger.error(f"Unexpected error in real domain availability check for {domain_name}: {e}")
            return False
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

    @api_rate_limited(service="domain_api", api_client_type="real_api", endpoint="whois")
    async def get_whois_data(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Simulates fetching WHOIS data via a real API.
        Replace this with actual API call logic.
        """
        endpoint = f"{self.base_url}/v1/domain/whois"
        params = {"domain": domain_name}
        self.logger.info(f"Making real API call for WHOIS data: {endpoint}?domain={domain_name}")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}"})
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status()
                # real_data = await response.json()
                # return real_data.get("whois_record")

                # Fallback to simulated logic for actual return value
                return SimulatedDomainAPIClient().get_whois_data(domain_name)
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real WHOIS data for {domain_name}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in real WHOIS data fetch for {domain_name}: {e}")
            return None
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

class AbstractDomainAPIClient(BaseDomainAPIClient):
    """
    A client for AbstractAPI's Domain API (or similar low-cost/free-tier service).
    Requires an API key.
    """
    def __init__(self, api_key: str, base_url: str = "https://companyenrichment.abstractapi.com/v1/"):
        self.logger = logging.getLogger(__name__ + ".AbstractDomainAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering AbstractDomainAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting AbstractDomainAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @api_rate_limited(service="domain_api", api_client_type="abstract_api", endpoint="availability")
    async def get_domain_availability(self, domain_name: str) -> bool:
        """
        Checks domain availability using AbstractAPI.
        """
        endpoint = f"{self.base_url}"
        params = {"api_key": self.api_key, "domain": domain_name, "field": "is_dead"} # AbstractAPI uses 'is_dead' for availability
        self.logger.info(f"Making AbstractAPI call for availability: {endpoint}?domain={domain_name}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("AbstractDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession()
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                # AbstractAPI returns is_dead: true if domain is dead/available, false if active/registered
                return data.get("is_dead", False) # is_dead=True means available
        except aiohttp.ClientError as e:
            self.logger.error(f"Error checking AbstractAPI domain availability for {domain_name}: {e}")
            return False # Assume not available on error
        except Exception as e:
            self.logger.error(f"Unexpected error in AbstractAPI domain availability check for {domain_name}: {e}")
            return False
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

    @api_rate_limited(service="domain_api", api_client_type="abstract_api", endpoint="whois")
    async def get_whois_data(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetches WHOIS data using AbstractAPI.
        """
        endpoint = f"{self.base_url}"
        params = {"api_key": self.api_key, "domain": domain_name}
        self.logger.info(f"Making AbstractAPI call for WHOIS data: {endpoint}?domain={domain_name}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("AbstractDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession()
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Map AbstractAPI response to a more generic WHOIS format
                whois_info = {
                    "domain_name": data.get("domain", {}).get("domain", domain_name).upper(),
                    "registrar": data.get("registrar", {}).get("registrar_name"),
                    "creation_date": data.get("registered", ""), # AbstractAPI provides 'registered'
                    "expiration_date": data.get("expires_at", ""), # AbstractAPI provides 'expires_at'
                    "name_servers": data.get("dns_records", {}).get("NS", []),
                    "status": data.get("domain", {}).get("status"),
                    "emails": [data.get("contact", {}).get("email")] if data.get("contact", {}).get("email") else [],
                    "updated_date": data.get("last_changed_date", "")
                }
                return {k: v for k, v in whois_info.items() if v is not None and v != ""} # Filter out empty values
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching AbstractAPI WHOIS data for {domain_name}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in AbstractAPI WHOIS data fetch for {domain_name}: {e}")
            return None
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()


class DomainService:
    """
    Service for querying domain-related information, such as availability and WHOIS data.
    Uses a DomainAPIClient to perform actual lookups.
    """
    def __init__(self, api_client: Optional[BaseDomainAPIClient] = None, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600):
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.api_cache_enabled = config_loader.get("api_cache.enabled", False)
        
        # Determine which API client to use based on config_loader priority
        if config_loader.get("domain_api.abstract_api.enabled"):
            abstract_api_key = config_loader.get("domain_api.abstract_api.api_key")
            if not abstract_api_key:
                self.logger.error("AbstractAPI enabled but API key not found in config. Falling back to simulated Domain API.")
                self.api_client = SimulatedDomainAPIClient()
            else:
                self.logger.info("Using AbstractDomainAPIClient for domain lookups.")
                self.api_client = AbstractDomainAPIClient(api_key=abstract_api_key)
        elif config_loader.get("domain_api.real_api.enabled"):
            real_api_key = config_loader.get("domain_api.real_api.api_key")
            if not real_api_key:
                self.logger.error("Real Domain API enabled but API key not found in config. Falling back to simulated Domain API.")
                self.api_client = SimulatedDomainAPIClient()
            else:
                self.logger.info("Using RealDomainAPIClient for domain lookups.")
                self.api_client = RealDomainAPIClient(api_key=real_api_key)
        else:
            self.logger.info("Using SimulatedDomainAPIClient for domain lookups.")
            self.api_client = SimulatedDomainAPIClient()

    async def __aenter__(self):
        """Async context manager entry for DomainService."""
        self.logger.debug("Entering DomainService context.")
        await self.api_client.__aenter__() # Enter the client's context
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for DomainService."""
        self.logger.debug("Exiting DomainService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb) # Exit the client's context

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
        Checks if a domain name is available for registration using the API client.
        Uses caching.
        """
        cache_key = f"domain_availability:{domain_name}"
        cached_result = await self._get_cached_response(cache_key, "domain_api", "availability")
        if cached_result is not None:
            return cached_result

        result = await self.api_client.get_domain_availability(domain_name)
        await self._set_cached_response(cache_key, result, "domain_api", "availability")
        return result

    async def get_whois_info(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetches WHOIS information for a domain using the API client.
        Uses caching.
        """
        cache_key = f"domain_whois:{domain_name}"
        cached_result = await self._get_cached_response(cache_key, "domain_api", "whois")
        if cached_result is not None:
            return cached_result

        result = await self.api_client.get_whois_data(domain_name)
        if result: # Only cache if result is not None
            await self._set_cached_response(cache_key, result, "domain_api", "whois")
        return result

    async def get_domain_info(self, domain_name: str) -> Optional[Domain]:
        """
        Combines WHOIS info and availability check into a Domain model.
        Assigns consistent simulated scores if no real API is used.
        Uses caching for underlying API calls.
        """
        whois_data = await self.get_whois_info(domain_name)
        if not whois_data:
            self.logger.warning(f"No WHOIS data found for {domain_name}.")
            return None

        is_available = await self.check_domain_availability(domain_name)

        # Parse dates from WHOIS data
        creation_date_str = whois_data.get("creation_date")
        expiration_date_str = whois_data.get("expiration_date")
        
        creation_date = None
        expiration_date = None

        # Define common date formats to try
        date_formats = [
            "%Y-%m-%d",         # e.g., 2023-01-01
            "%Y-%m-%dT%H:%M:%S", # e.g., 2023-01-01T12:30:00
            "%Y-%m-%d %H:%M:%S", # e.g., 2023-01-01 12:30:00
            "%Y-%m-%d %H:%M:%S.%f", # e.g., 2023-01-01 12:30:00.123456
            "%b %d %Y",         # e.g., Jan 01 2023
            "%d-%b-%Y",         # e.g., 01-Jan-2023
            "%d-%m-%Y",         # e.g., 01-01-2023
            "%Y.%m.%d"          # e.g., 2023.01.01
        ]

        def parse_date_robustly(date_str: str) -> Optional[datetime]:
            if not date_str:
                return None
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            self.logger.warning(f"Could not parse date string: '{date_str}'")
            return None

        creation_date = parse_date_robustly(creation_date_str)
        expiration_date = parse_date_robustly(expiration_date_str)
        
        # Calculate age if creation date is available
        age_days = None
        if creation_date:
            age_days = (datetime.now() - creation_date).days

        # --- Simulated Authority, Trust, Spam Scores (more consistent for testing) ---
        # These scores would ideally come from a real SEO metrics API.
        # For simulation, we make them somewhat deterministic based on domain name.
        # This allows DomainAnalyzerService to have consistent inputs for its rules.
        
        # Simple hash-based simulation for consistent scores
        # This is NOT a real scoring model, just for predictable testing
        domain_hash = sum(ord(c) for c in domain_name.lower())
        
        simulated_authority_score = (domain_hash % 100) + 1 # 1-100
        simulated_trust_score = (domain_hash % 80) + 20 # 20-100
        simulated_spam_score = (domain_hash % 50) + 1 # 1-50

        # Example: make "google.com" always high authority, low spam
        if domain_name.lower() == "google.com":
            simulated_authority_score = 95.0
            simulated_trust_score = 99.0
            simulated_spam_score = 5.0
        elif domain_name.lower() == "example.com":
            simulated_authority_score = 70.0
            simulated_trust_score = 80.0
            simulated_spam_score = 15.0
        elif domain_name.lower() == "nonexistent.xyz":
            simulated_authority_score = 10.0
            simulated_trust_score = 20.0
            simulated_spam_score = 40.0
        
        domain_obj = Domain(
            name=domain_name,
            authority_score=simulated_authority_score,
            trust_score=simulated_trust_score,
            spam_score=simulated_spam_score,
            age_days=age_days,
            whois_data=whois_data,
            first_seen=creation_date,
            # For simplicity, last_crawled is not set here, but could be from a separate crawl
        )
        return domain_obj
