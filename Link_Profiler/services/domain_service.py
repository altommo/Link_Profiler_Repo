import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp
import json # Import json for caching
import redis.asyncio as redis # Import redis for type hinting

from Link_Profiler.core.models import Domain, DomainHistory # Absolute import
from Link_Profiler.config.config_loader import config_loader # New import
from Link_Profiler.utils.api_rate_limiter import api_rate_limited # Import the rate limiter
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager
from Link_Profiler.clients.whois_client import WHOISClient # New: Import WHOISClient
from Link_Profiler.clients.dns_client import DNSClient # New: Import DNSClient
from Link_Profiler.monitoring.prometheus_metrics import API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL # Import Prometheus metrics
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.database.database import Database # Import Database

logger = logging.getLogger(__name__)

class BaseDomainAPIClient:
    """
    Base class for a domain information API client.
    Real implementations would connect to external services.
    """
    async def get_domain_info(self, domain: str) -> Optional[Dict[str, Any]]:
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
    def __init__(self, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__ + ".SimulatedDomainAPIClient")
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to SimulatedDomainAPIClient. Falling back to local SessionManager.")

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedDomainAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedDomainAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def get_domain_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Simulates fetching domain information.
        """
        self.logger.info(f"Simulating API call for domain info: {domain}")
        
        try:
            async with await self.session_manager.get(f"http://localhost:8080/simulate_domain/{domain}") as response:
                # We don't care about the actual response, just that the request was made
                pass
        except aiohttp.ClientConnectorError:
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated domain fetch: {e}")

        # Generate dummy data
        is_available = random.choice([True, False])
        if is_available:
            return {
                "domain_name": domain,
                "is_available": True,
                "creation_date": (datetime.now() - timedelta(days=random.randint(365, 365*10))).isoformat(),
                "expiration_date": (datetime.now() + timedelta(days=random.randint(30, 365*5))).isoformat(),
                "registrant_country": random.choice(["US", "CA", "GB", "DE", "AU"]),
                "registrar": f"SimulatedRegistrar{random.randint(1,5)}",
                "name_servers": [f"ns1.simulated.com", f"ns2.simulated.com"],
                "whois_data": {"raw": "Simulated WHOIS data..."},
                "ip_address": f"192.168.1.{random.randint(1,254)}",
                "status": "active"
            }
        else:
            return {
                "domain_name": domain,
                "is_available": False,
                "status": "unavailable"
            }

class RealDomainAPIClient(BaseDomainAPIClient):
    """
    A client for real domain information APIs.
    This implementation demonstrates where actual API calls would go.
    """
    def __init__(self, api_key: str, base_url: str, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__ + ".RealDomainAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to RealDomainAPIClient. Falling back to local SessionManager.")

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealDomainAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealDomainAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="domain_api", api_client_type="real_api", endpoint="get_domain_info")
    async def get_domain_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Fetches domain information from a real API.
        Replace with actual API call logic for your chosen provider.
        """
        endpoint = f"{self.base_url}/v1/domain/{domain}/info" # Hypothetical endpoint
        headers = {"Authorization": f"Bearer {self.api_key}"} # Example for API key in header
        self.logger.info(f"Attempting real API call for domain info: {endpoint}...")

        try:
            async with await self.session_manager.get(endpoint, headers=headers) as response:
                response.raise_for_status() # Raise an exception for HTTP errors
                data = await response.json()
                
                # --- Replace with actual parsing logic for your chosen API ---
                # Example: assuming data contains keys like 'domain_name', 'created_date', etc.
                # return {
                #     "domain_name": data.get("domain_name"),
                #     "is_available": data.get("status") == "available",
                #     "creation_date": data.get("created_date"),
                #     "expiration_date": data.get("expiration_date"),
                #     "registrant_country": data.get("registrant", {}).get("country"),
                #     "registrar": data.get("registrar"),
                #     "name_servers": data.get("name_servers", []),
                #     "whois_data": data.get("whois_raw"),
                #     "ip_address": data.get("ip_address"),
                #     "status": data.get("status")
                # }
                self.logger.warning("RealDomainAPIClient: Returning simulated data. Replace with actual API response parsing.")
                return SimulatedDomainAPIClient(session_manager=self.session_manager).get_domain_info(domain) # Fallback to simulation

        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real domain info for {domain}: {e}. Returning None.")
            return None # Return None on network/client error
        except Exception as e:
            self.logger.error(f"Unexpected error in real domain fetch for {domain}: {e}. Returning None.")
            return None

class AbstractDomainAPIClient(BaseDomainAPIClient):
    """
    A client for AbstractAPI's Domain API (or similar low-cost/free-tier service).
    Requires an API key.
    """
    def __init__(self, api_key: str, base_url: str, whois_base_url: str, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__ + ".AbstractDomainAPIClient")
        self.api_key = api_key
        self.base_url = base_url # For domain validation
        self.whois_base_url = whois_base_url # For WHOIS data
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to AbstractDomainAPIClient. Falling back to local SessionManager.")

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering AbstractDomainAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting AbstractDomainAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="domain_api", api_client_type="abstract_api", endpoint="get_domain_info")
    async def get_domain_info(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Fetches domain information using AbstractAPI.
        Combines domain validation and WHOIS data.
        """
        if not self.api_key:
            self.logger.error("AbstractAPI key is not configured. Cannot fetch domain info.")
            return None

        domain_validation_url = f"{self.base_url}?api_key={self.api_key}&domain={domain}"
        whois_url = f"{self.whois_base_url}?api_key={self.api_key}&domain={domain}"
        
        domain_data = {}
        whois_data = {}

        try:
            # Fetch domain validation data
            async with await self.session_manager.get(domain_validation_url) as response:
                response.raise_for_status()
                domain_data = await response.json()
                self.logger.debug(f"AbstractAPI Domain Validation for {domain}: {domain_data}")

            # Fetch WHOIS data
            async with await self.session_manager.get(whois_url) as response:
                response.raise_for_status()
                whois_data = await response.json()
                self.logger.debug(f"AbstractAPI WHOIS for {domain}: {whois_data}")

            # Combine and format data
            return {
                "domain_name": domain_data.get("domain"),
                "is_available": domain_data.get("is_available"),
                "creation_date": whois_data.get("created"),
                "expiration_date": whois_data.get("expires"),
                "registrant_country": whois_data.get("country"),
                "registrar": whois_data.get("registrar"),
                "name_servers": whois_data.get("nameservers"),
                "whois_data": whois_data, # Store full WHOIS response
                "ip_address": domain_data.get("ip_address"),
                "status": "active" if not domain_data.get("is_available") else "available"
            }

        except aiohttp.ClientError as e:
            self.logger.error(f"AbstractAPI network/client error for {domain}: {e}. Returning None.")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error with AbstractAPI for {domain}: {e}. Returning None.", exc_info=True)
            return None


class DomainService:
    """
    Service for querying domain-related information, such as availability and WHOIS data.
    Uses various API clients to perform actual lookups.
    """
    def __init__(self, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600, database: Optional[Database] = None, whois_client: Optional[WHOISClient] = None, dns_client: Optional[DNSClient] = None, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.db = database
        self.api_cache_enabled = config_loader.get("api_cache.enabled", False)
        self.whois_client = whois_client # New: Store WHOISClient instance
        self.dns_client = dns_client # New: Store DNSClient instance
        self.session_manager = session_manager # Store the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to DomainService. Falling back to local SessionManager.")

        # Determine which DomainAPIClient to use based on config_loader priority
        if config_loader.get("domain_api.abstract_api.enabled"):
            abstract_api_key = config_loader.get("domain_api.abstract_api.api_key")
            abstract_base_url = config_loader.get("domain_api.abstract_api.base_url")
            abstract_whois_base_url = config_loader.get("domain_api.abstract_api.whois_base_url")
            if not abstract_api_key or not abstract_base_url or not abstract_whois_base_url:
                self.logger.warning("AbstractAPI enabled but key/URL not found. Falling back to simulated Domain API.")
                self.api_client = SimulatedDomainAPIClient(session_manager=self.session_manager)
            else:
                self.logger.info("Using AbstractDomainAPIClient for domain lookups.")
                self.api_client = AbstractDomainAPIClient(api_key=abstract_api_key, base_url=abstract_base_url, whois_base_url=abstract_whois_base_url, session_manager=self.session_manager)
        elif config_loader.get("domain_api.real_api.enabled"):
            real_api_key = config_loader.get("domain_api.real_api.api_key")
            real_base_url = config_loader.get("domain_api.real_api.base_url")
            if not real_api_key or not real_base_url:
                self.logger.warning("Real Domain API enabled but key/URL not found. Falling back to simulated Domain API.")
                self.api_client = SimulatedDomainAPIClient(session_manager=self.session_manager)
            else:
                self.logger.info("Using RealDomainAPIClient for domain lookups.")
                self.api_client = RealDomainAPIClient(api_key=real_api_key, base_url=real_base_url, session_manager=self.session_manager)
        elif config_loader.get("domain_api.whois_json_api.enabled") and self.whois_client and self.whois_client.enabled:
            self.logger.info("Using WHOISClient for domain lookups.")
            self.api_client = self.whois_client # WHOISClient is already a BaseDomainAPIClient
        else:
            self.logger.info("No specific Domain API enabled. Using SimulatedDomainAPIClient for availability checks.")
            self.api_client = SimulatedDomainAPIClient(session_manager=self.session_manager)

    async def __aenter__(self):
        """Async context manager entry for DomainService."""
        self.logger.debug("Entering DomainService context.")
        await self.api_client.__aenter__() # Enter the client's context
        if self.whois_client: # New: Enter WHOISClient's context
            await self.whois_client.__aenter__()
        if self.dns_client: # New: Enter DNSClient's context
            await self.dns_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for DomainService."""
        self.logger.debug("Exiting DomainService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb) # Exit the client's context
        if self.whois_client: # New: Exit WHOISClient's context
            await self.whois_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.dns_client: # New: Exit DNSClient's context
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

    async def get_domain_info(self, domain_name: str) -> Optional[Domain]:
        """
        Retrieves comprehensive information about a domain.
        Prioritizes database cache, then API, then fetches new data.
        """
        # 1. Check database cache first
        if self.db:
            domain_from_db = self.db.get_domain(domain_name)
            if domain_from_db and (datetime.now() - (domain_from_db.last_crawled or datetime.min)).total_seconds() < self.cache_ttl:
                self.logger.info(f"Domain info for {domain_name} found in DB cache.")
                return domain_from_db

        # 2. Check Redis API cache
        cache_key = f"domain_info:{domain_name}"
        cached_data = await self._get_cached_response(cache_key, "domain_api", "get_domain_info")
        if cached_data:
            domain_obj = Domain.from_dict(cached_data)
            if self.db:
                self.db.save_domain(domain_obj) # Save to DB for persistence
            return domain_obj

        # 3. Fetch from API
        self.logger.info(f"Fetching domain info for {domain_name} from API.")
        domain_data = await self.api_client.get_domain_info(domain_name)

        if domain_data:
            # If WHOISClient is enabled and used as primary, it might not return IP.
            # Try to get IP from DNSClient if available and IP is missing.
            if not domain_data.get("ip_address") and self.dns_client and self.dns_client.enabled:
                self.logger.info(f"Attempting to get IP for {domain_name} via DNSClient.")
                ip_address = await self.dns_client.resolve_domain(domain_name)
                if ip_address:
                    domain_data["ip_address"] = ip_address
            
            # Calculate age if creation_date is available
            creation_date_str = domain_data.get("creation_date")
            if creation_date_str:
                try:
                    creation_dt = self.parse_date_robustly(creation_date_str)
                    if creation_dt:
                        domain_data["age_days"] = (datetime.now() - creation_dt).days
                except Exception as e:
                    self.logger.warning(f"Could not parse creation_date: {creation_date_str} for {domain_name}: {e}")
            else:
                domain_data["age_days"] = None

            domain_obj = Domain(
                name=domain_name,
                authority_score=random.uniform(0, 100), # Placeholder, would come from external source
                trust_score=random.uniform(0, 1), # Placeholder
                spam_score=random.uniform(0, 1), # Placeholder
                age_days=domain_data.get("age_days"),
                country=domain_data.get("registrant_country"),
                ip_address=domain_data.get("ip_address"),
                whois_data=domain_data.get("whois_data", {}),
                total_pages=random.randint(10, 10000), # Placeholder
                total_backlinks=random.randint(100, 100000), # Placeholder
                referring_domains=random.randint(10, 5000), # Placeholder
                first_seen=creation_dt if 'creation_dt' in locals() else None,
                last_crawled=datetime.now()
            )
            
            if self.db:
                self.db.save_domain(domain_obj) # Save to DB
            await self._set_cached_response(cache_key, domain_obj.to_dict(), "domain_api", "get_domain_info") # Cache in Redis
            return domain_obj
        
        self.logger.warning(f"Could not retrieve domain info for {domain_name}.")
        return None

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
