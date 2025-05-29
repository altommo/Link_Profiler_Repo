import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime, timedelta
import random
import aiohttp

from Link_Profiler.core.models import Backlink, LinkType, SpamLevel, Domain # Assuming Domain model might be needed for context

logger = logging.getLogger(__name__)

class BaseBacklinkAPIClient:
    """
    Base class for a backlink information API client.
    Real implementations would connect to external services.
    """
    async def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        raise NotImplementedError

    async def __aenter__(self):
        """Async context manager entry for client session."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        pass # No-op for base class

class SimulatedBacklinkAPIClient(BaseBacklinkAPIClient):
    """
    A simulated client for backlink information APIs.
    Generates dummy backlink data.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SimulatedBacklinkAPIClient")
        self._session: Optional[aiohttp.ClientSession] = None # For simulating network calls

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedBacklinkAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedBacklinkAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """
        Simulates fetching backlinks for a given target URL.
        """
        self.logger.info(f"Simulating API call for backlinks for: {target_url}")
        
        # Simulate network delay
        if self._session is None or self._session.closed:
            await asyncio.sleep(0.5)
        else:
            try:
                # Simulate an actual HTTP request, even if it's to a dummy URL
                async with self._session.get(f"http://localhost:8080/simulate_backlinks/{target_url}") as response:
                    pass
            except aiohttp.ClientConnectorError:
                pass
            except Exception as e:
                self.logger.warning(f"Unexpected error during simulated backlink fetch: {e}")

        # Generate some dummy backlinks
        num_backlinks = random.randint(5, 15)
        backlinks = []
        for i in range(num_backlinks):
            source_domain = f"source{i}.com"
            source_url = f"http://{source_domain}/page{random.randint(1, 5)}"
            link_type = random.choice(list(LinkType))
            spam_level = random.choice(list(SpamLevel))
            
            backlinks.append(
                Backlink(
                    source_url=source_url,
                    target_url=target_url,
                    anchor_text=f"Anchor Text {i}",
                    link_type=link_type,
                    context_text=f"Context around link {i}",
                    is_image_link=random.choice([True, False]),
                    alt_text=f"Alt text {i}" if random.choice([True, False]) else None,
                    discovered_date=datetime.now() - timedelta(days=random.randint(1, 365)),
                    last_seen_date=datetime.now(),
                    authority_passed=random.uniform(0.1, 1.0),
                    spam_level=spam_level
                )
            )
        
        # Add a few specific backlinks for quotes.toscrape.com for consistency with existing tests
        if "quotes.toscrape.com" in target_url:
            backlinks.extend([
                Backlink(
                    source_url="http://example.com/blog/quotes-review",
                    target_url="http://quotes.toscrape.com/",
                    anchor_text="Great Quotes Site",
                    link_type=LinkType.FOLLOW,
                    context_text="Check out this great quotes site.",
                    spam_level=SpamLevel.CLEAN
                ),
                Backlink(
                    source_url="http://anotherblog.net/top-sites",
                    target_url="http://quotes.toscrape.com/login",
                    anchor_text="Login to Quotes",
                    link_type=LinkType.NOFOLLOW,
                    context_text="You can login here.",
                    spam_level=SpamLevel.CLEAN
                )
            ])

        self.logger.info(f"Simulated {len(backlinks)} backlinks for {target_url}.")
        return backlinks

class RealBacklinkAPIClient(BaseBacklinkAPIClient):
    """
    A client for real backlink information APIs (e.g., Ahrefs, Moz, SEMrush).
    This is a placeholder; you would implement actual API calls here.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.real-backlink-provider.com"):
        self.logger = logging.getLogger(__name__ + ".RealBacklinkAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealBacklinkAPIClient context.")
        if self._session is None or self._session.closed:
            # Example: Ahrefs API might use 'X-Ahrefs-Token' header
            # Moz API might use basic auth or query params
            self._session = aiohttp.ClientSession(headers={"X-API-Key": self.api_key})
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealBacklinkAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """
        Fetches backlinks for a given target URL from a real API.
        This is a placeholder; replace with actual API call logic.
        """
        endpoint = f"{self.base_url}/v1/backlinks"
        params = {"target": target_url, "limit": 100} # Example parameters
        self.logger.info(f"Making real API call for backlinks: {endpoint}?target={target_url}...")

        try:
            async with self._session.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                data = await response.json()
                
                # --- Placeholder for parsing real API response into Backlink objects ---
                # This part is highly dependent on the actual API's response structure.
                # For demonstration, we'll simulate data if the real API call was successful
                # but we don't have actual parsing logic.
                
                # Example of how you might parse a real API response:
                # parsed_backlinks = []
                # for item in data.get("backlinks", []):
                #     parsed_backlinks.append(Backlink(
                #         source_url=item.get("source_url"),
                #         target_url=item.get("target_url"),
                #         anchor_text=item.get("anchor_text", ""),
                #         link_type=LinkType(item.get("link_type", "follow").lower()),
                #         # ... map other fields
                #     ))
                # return parsed_backlinks

                # For now, if the API call itself succeeds, return simulated data
                # to keep the flow working without a real API key.
                self.logger.warning("RealBacklinkAPIClient is using simulated data. Replace with actual parsing.")
                return await SimulatedBacklinkAPIClient().get_backlinks_for_url(target_url)

        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real backlinks for {target_url}: {e}")
            return [] # Return empty list on error
        except Exception as e:
            self.logger.error(f"Unexpected error in real backlink fetch for {target_url}: {e}")
            return []

class BacklinkService:
    """
    Service for retrieving backlink information, either from a crawler or an API.
    """
    def __init__(self, api_client: Optional[BaseBacklinkAPIClient] = None):
        self.logger = logging.getLogger(__name__)
        
        # Determine which API client to use based on environment variable
        if os.getenv("USE_REAL_BACKLINK_API", "false").lower() == "true":
            real_api_key = os.getenv("REAL_BACKLINK_API_KEY")
            if not real_api_key:
                self.logger.error("REAL_BACKLINK_API_KEY environment variable not set. Falling back to simulated Backlink API.")
                self.api_client = SimulatedBacklinkAPIClient()
            else:
                self.logger.info("Using RealBacklinkAPIClient for backlink lookups.")
                self.api_client = RealBacklinkAPIClient(api_key=real_api_key)
        else:
            self.logger.info("Using SimulatedBacklinkAPIClient for backlink lookups.")
            self.api_client = SimulatedBacklinkAPIClient()

    async def __aenter__(self):
        """Async context manager entry for BacklinkService."""
        self.logger.debug("Entering BacklinkService context.")
        await self.api_client.__aenter__() # Enter the client's context
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for BacklinkService."""
        self.logger.debug("Exiting BacklinkService context.")
        await self.api_client.__aexit__(exc_type, exc_val, exc_tb) # Exit the client's context

    async def get_backlinks_from_api(self, target_url: str) -> List[Backlink]:
        """
        Fetches backlinks for a target URL using the configured API client.
        """
        return await self.api_client.get_backlinks_for_url(target_url)
