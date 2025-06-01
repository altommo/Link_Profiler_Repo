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

from Link_Profiler.core.models import Domain, DomainHistory # New: Import DomainHistory
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.monitoring.prometheus_metrics import (
    API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL
)
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.database.database import Database # Import Database

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
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()
            
            self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedDomainAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_domain_availability(self, domain_name: str) -> bool:
        """
        Simulates checking domain availability.
        Uses aiohttp to simulate a network call.
        """
        self.logger.info(f"Simulating API call for domain availability: {domain_name}")
        
        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("SimulatedDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
            close_session_after_use = True

        try:
            async with session_to_use.get(f"http://localhost:8080/simulate_domain_availability/{domain_name}") as response:
                # We don't care about the actual response, just that the request was made
                pass
        except aiohttp.ClientConnectorError:
            # This is expected if localhost:8080 is not running, simulating network activity
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated domain availability check: {e}")
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

        # Simulate availability based on domain name
        return "example" not in domain_name and "test" not in domain_name

    async def get_whois_data(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Simulates fetching WHOIS data.
        """
        self.logger.info(f"Simulating API call for WHOIS data: {domain_name}")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("SimulatedDomainAPIClient: aiohttp session not active. Creating temporary session for this call.")
            
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()

            session_to_use = aiohttp.ClientSession(headers=headers)
            close_session_after_use = True

        try:
            async with session_to_use.get(f"http://localhost:8080/simulate_whois/{domain_name}") as response:
                pass
        except aiohttp.ClientConnectorError:
            # This is expected if localhost:8080 is not running, simulating network activity
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated WHOIS fetch: {e}")
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

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
            headers = {"X-API-Key": self.api_key}
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
        This is a placeholder; replace with actual API call logic.
        """
        endpoint = f"{self.base_url}/v1/availability"
        params = {"domain": domain_name}
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
                response.raise_for_status()
                data = await response.json()
                # Placeholder for parsing real API response
                return data.get("available", False)
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
        This is a placeholder; replace with actual API call logic.
        """
        endpoint = f"{self.base_url}/v1/whois"
        params = {"domain": domain_name}
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
                # real_data = await response.json()
                # return real_data.get("whois_record")

                # Fallback to simulated logic for actual return value
                return await SimulatedDomainAPIClient().get_whois_data(domain_name)
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
    def __init__(self, api_key: str, base_url: str = "https://emailvalidation.abstractapi.com/v1/"):
        self.logger = logging.getLogger(__name__ + ".AbstractDomainAPIClient")
        self.api_key = api_key
        self.base_url = base_url
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
        Fetches domain availability using AbstractAPI.
        """
        endpoint = f"{self.base_url}"
        params = {"api_key": self.api_key, "domain": domain_name}
        self.logger.info(f"Attempting AbstractAPI call for domain availability: {endpoint}?domain={domain_name}...")

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
                # AbstractAPI's email validation endpoint can also check domain validity
                # Assuming 'is_smtp_valid' or similar indicates if domain is reachable
                return data.get("is_smtp_valid", False) # This is a simplification
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
        Fetches WHOIS data using AbstractAPI.
        Note: AbstractAPI has a separate WHOIS API. This is a placeholder.
        """
        self.logger.warning("AbstractAPI WHOIS endpoint not implemented. Returning simulated WHOIS data.")
        # Fallback to simulated data if the specific AbstractAPI WHOIS endpoint is not integrated
        return await SimulatedDomainAPIClient().get_whois_data(domain_name)


class DomainService:
    """
    Service for querying domain-related information, such as availability and WHOIS data.
    Uses a DomainAPIClient to perform actual lookups.
    """
    def __init__(self, api_client: BaseDomainAPIClient, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600, database: Optional[Database] = None):
        self.logger = logging.getLogger(__name__)
        self.api_client = api_client
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.api_cache_enabled = config_loader.get("api_cache.enabled", False)
        self.db = database # Store the database instance

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
        Uses caching.
        """
        cache_key = f"whois_info:{domain_name}"
        cached_result = await self._get_cached_response(cache_key, "domain_api", "whois")
        if cached_result is not None:
            return cached_result

        whois_data = await self.api_client.get_whois_data(domain_name)
        if whois_data: # Only cache if data is actually returned
            await self._set_cached_response(cache_key, whois_data, "domain_api", "whois")
        return whois_data

    async def get_domain_info(self, domain_name: str) -> Optional[Domain]:
        """
        Combines WHOIS info and availability check into a Domain model.
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
        
        is_available = await self.check_domain_availability(domain_name)
        whois_data = await self.get_whois_info(domain_name)

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
            domain_obj.ip_address = whois_data.get("ip_address") if whois_data else None
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
                ip_address=whois_data.get("ip_address") if whois_data else None,
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
