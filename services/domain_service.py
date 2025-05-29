"""
Domain Service - Provides functionalities related to domain information.
File: services/domain_service.py
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import random
from datetime import datetime # Import datetime for parsing WHOIS dates
import aiohttp # Import aiohttp

from ..core.models import Domain

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
    Uses aiohttp to simulate network requests.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SimulatedDomainAPIClient")
        self._session: Optional[aiohttp.ClientSession] = None

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
        if self._session is None or self._session.closed:
            self.logger.warning("aiohttp session not active. Call client within async with block.")
            # Fallback to simple sleep if session not managed by context manager
            await asyncio.sleep(0.5)
        else:
            try:
                # Simulate an actual HTTP request, even if it's to a dummy URL
                # This helps test aiohttp session management
                async with self._session.get(f"http://localhost:8080/simulate_availability/{domain_name}") as response:
                    # We don't care about the actual response, just that the request was made
                    pass
            except aiohttp.ClientConnectorError:
                # This is expected if localhost:8080 is not running, simulating network activity
                pass
            except Exception as e:
                self.logger.warning(f"Unexpected error during simulated availability check: {e}")

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
        if self._session is None or self._session.closed:
            self.logger.warning("aiohttp session not active. Call client within async with block.")
            # Fallback to simple sleep if session not managed by context manager
            await asyncio.sleep(1.0)
        else:
            try:
                # Simulate an actual HTTP request
                async with self._session.get(f"http://localhost:8080/simulate_whois/{domain_name}") as response:
                    pass
            except aiohttp.ClientConnectorError:
                pass
            except Exception as e:
                self.logger.warning(f"Unexpected error during simulated WHOIS check: {e}")

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


class DomainService:
    """
    Service for querying domain-related information, such as availability and WHOIS data.
    Uses a DomainAPIClient to perform actual lookups.
    """
    def __init__(self, api_client: Optional[BaseDomainAPIClient] = None):
        self.logger = logging.getLogger(__name__)
        self.api_client = api_client if api_client else SimulatedDomainAPIClient()

    async def __aenter__(self):
        """Async context manager entry for DomainService."""
        self.logger.debug("Entering DomainService context.")
        await self.api_client.__aenter__() # Enter the client's context
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for DomainService."""
        self.logger.debug("Exiting DomainService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb) # Exit the client's context

    async def check_domain_availability(self, domain_name: str) -> bool:
        """
        Checks if a domain name is available for registration using the API client.
        """
        return await self.api_client.get_domain_availability(domain_name)

    async def get_whois_info(self, domain_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetches WHOIS information for a domain using the API client.
        """
        return await self.api_client.get_whois_data(domain_name)

    async def get_domain_info(self, domain_name: str) -> Optional[Domain]:
        """
        Combines WHOIS info and availability check into a Domain model.
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

        try:
            if creation_date_str:
                creation_date = datetime.strptime(creation_date_str, "%Y-%m-%d")
            if expiration_date_str:
                expiration_date = datetime.strptime(expiration_date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            self.logger.warning(f"Could not parse date from WHOIS data for {domain_name}. Data: {creation_date_str}, {expiration_date_str}")

        # Calculate age if creation date is available
        age_days = None
        if creation_date:
            age_days = (datetime.now() - creation_date).days

        # Create a Domain object (authority_score, trust_score, spam_score are placeholders for now)
        domain_obj = Domain(
            name=domain_name,
            authority_score=random.uniform(0, 100), # Placeholder
            trust_score=random.uniform(0, 100),     # Placeholder
            spam_score=random.uniform(0, 100),      # Placeholder
            age_days=age_days,
            whois_data=whois_data,
            first_seen=creation_date,
            # For simplicity, last_crawled is not set here, but could be from a separate crawl
        )
        return domain_obj

