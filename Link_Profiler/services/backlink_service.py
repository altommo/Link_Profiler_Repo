import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime, timedelta
import random
import aiohttp

# Google API imports for GSC
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from Link_Profiler.core.models import Backlink, LinkType, SpamLevel, Domain # Assuming Domain model might be needed for context

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.pyc' # Changed to .pyc to avoid accidental git tracking of sensitive token.json

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
                    # We don't care about the actual response, just that the request was made
                    pass
            except aiohttp.ClientConnectorError:
                # This is expected if localhost:8080 is not running, simulating network activity
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
        self.logger.info(f"Attempting real API call for backlinks: {endpoint}?target={target_url}...")

        try:
            # Simulate an actual HTTP request to a dummy endpoint.
            # In a real scenario, this would be your actual API endpoint.
            async with self._session.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                
                # --- Placeholder for parsing real API response into Backlink objects ---
                # This part is highly dependent on the actual API's response structure.
                # You would parse `await response.json()` here.
                
                self.logger.warning("RealBacklinkAPIClient: Returning simulated data. Replace with actual API response parsing.")
                
                # Return a fixed set of dummy backlinks to represent a successful API call
                # This is distinct from SimulatedBacklinkAPIClient's random generation
                return [
                    Backlink(
                        source_url="http://real-api-source1.com/page/1",
                        target_url=target_url,
                        anchor_text="Real API Link 1",
                        link_type=LinkType.FOLLOW,
                        context_text="Context from real API source 1",
                        discovered_date=datetime.now() - timedelta(days=30),
                        spam_level=SpamLevel.CLEAN
                    ),
                    Backlink(
                        source_url="http://real-api-source2.com/blog/post",
                        target_url=target_url,
                        anchor_text="Real API Link 2",
                        link_type=LinkType.NOFOLLOW,
                        context_text="Context from real API source 2",
                        discovered_date=datetime.now() - timedelta(days=60),
                        spam_level=SpamLevel.SUSPICIOUS
                    )
                ]

        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching real backlinks for {target_url}: {e}. Returning empty list.")
            return [] # Return empty list on network/client error
        except Exception as e:
            self.logger.error(f"Unexpected error in real backlink fetch for {target_url}: {e}. Returning empty list.")
            return []

class OpenLinkProfilerAPIClient(BaseBacklinkAPIClient):
    """
    A client for OpenLinkProfiler.org API.
    This API is free with usage limits.
    """
    def __init__(self, base_url: str = "http://www.openlinkprofiler.org/api/index.php"):
        self.logger = logging.getLogger(__name__ + ".OpenLinkProfilerAPIClient")
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering OpenLinkProfilerAPIClient context.")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting OpenLinkProfilerAPIClient context.")
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """
        Fetches backlinks for a given target URL from OpenLinkProfiler.org.
        Note: OpenLinkProfiler API has usage limits and may not return all data.
        """
        # OpenLinkProfiler API requires 'url' and 'output' parameters.
        # It returns data in XML or JSON. Let's assume JSON for easier parsing.
        # Example: http://www.openlinkprofiler.org/api/index.php?url=example.com&output=json
        
        parsed_target_url = urlparse(target_url)
        domain_or_url = parsed_target_url.netloc if parsed_target_url.netloc else target_url
        
        endpoint = self.base_url
        params = {"url": domain_or_url, "output": "json"}
        self.logger.info(f"Attempting OpenLinkProfiler API call for backlinks: {endpoint}?url={domain_or_url}...")

        try:
            async with self._session.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                
                backlinks = []
                # OpenLinkProfiler's JSON structure might vary, this is a common assumption
                for item in data.get("backlinks", []): # Adjust key based on actual API response
                    source_url = item.get("source_url")
                    target_url_from_api = item.get("target_url") # API might return canonical target
                    anchor_text = item.get("anchor_text", "")
                    link_type_str = item.get("link_type", "follow").lower() # e.g., "dofollow", "nofollow"
                    spam_score_val = item.get("spam_score", 0.0) # Assuming a score
                    
                    # Map OpenLinkProfiler's link types to our LinkType enum
                    link_type = LinkType.FOLLOW
                    if "nofollow" in link_type_str:
                        link_type = LinkType.NOFOLLOW
                    elif "sponsored" in link_type_str:
                        link_type = LinkType.SPONSORED
                    elif "ugc" in link_type_str:
                        link_type = LinkType.UGC
                    
                    # Map spam score to our SpamLevel enum (very basic mapping)
                    spam_level = SpamLevel.CLEAN
                    if spam_score_val > 70: # Example threshold
                        spam_level = SpamLevel.CONFIRMED_SPAM
                    elif spam_score_val > 40:
                        spam_level = SpamLevel.LIKELY_SPAM
                    elif spam_score_val > 10:
                        spam_level = SpamLevel.SUSPICIOUS

                    if source_url and target_url_from_api:
                        backlinks.append(
                            Backlink(
                                source_url=source_url,
                                target_url=target_url_from_api,
                                anchor_text=anchor_text,
                                link_type=link_type,
                                context_text="", # OpenLinkProfiler API might not provide context text
                                discovered_date=datetime.now(), # Use current date if API doesn't provide
                                spam_level=spam_level
                            )
                        )
                self.logger.info(f"OpenLinkProfilerAPIClient: Found {len(backlinks)} backlinks for {target_url}.")
                return backlinks

        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching OpenLinkProfiler backlinks for {target_url}: {e}. Returning empty list.")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in OpenLinkProfiler backlink fetch for {target_url}: {e}. Returning empty list.")
            return []


class GSCBacklinkAPIClient(BaseBacklinkAPIClient):
    """
    A client for Google Search Console API.
    Requires OAuth 2.0 authentication setup.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".GSCBacklinkAPIClient")
        self.service = None
        self._creds = None

    async def __aenter__(self):
        """Authenticates and builds the GSC service."""
        self.logger.info("Entering GSCBacklinkAPIClient context. Attempting authentication.")
        
        # This part would typically be run once interactively to generate token.json
        # For a server application, you'd usually have a pre-generated token.json
        # or a more complex OAuth flow.
        
        if os.path.exists(TOKEN_FILE):
            self._creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                self.logger.info("Refreshing GSC access token.")
                self._creds.refresh(Request())
            else:
                self.logger.warning(f"GSC token.json not found or invalid. Attempting interactive flow. Ensure {CREDENTIALS_FILE} exists.")
                # This interactive flow is not suitable for a headless server.
                # You would typically run this part once on a local machine to get token.json.
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    # Use a dummy port for local testing, or configure for web app flow
                    flow.redirect_uri = "http://localhost:8080/" # Or a real redirect URI for web apps
                    self._creds = flow.run_local_server(port=0) # Opens browser for authentication
                    with open(TOKEN_FILE, 'w') as token:
                        token.write(self._creds.to_json())
                    self.logger.info(f"GSC token.json generated. Please restart the application.")
                except FileNotFoundError:
                    self.logger.error(f"GSC credentials.json not found at {CREDENTIALS_FILE}. GSC API will not function.")
                    self._creds = None
                except Exception as e:
                    self.logger.error(f"Error during GSC interactive authentication flow: {e}")
                    self._creds = None

        if self._creds:
            self.service = build('webmasters', 'v3', credentials=self._creds)
            self.logger.info("GSC service built successfully.")
        else:
            self.logger.error("GSC authentication failed. GSC API client will not be functional.")
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific cleanup needed for GSC service object."""
        self.logger.info("Exiting GSCBacklinkAPIClient context.")
        pass

    async def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """
        Fetches backlinks for a given target URL from Google Search Console.
        Note: GSC API only provides data for verified properties.
        """
        if not self.service:
            self.logger.error("GSC service not initialized. Cannot fetch backlinks.")
            return []

        parsed_target_url = urlparse(target_url)
        # GSC API expects the property URL to be the root domain or a verified prefix
        # For simplicity, we'll use the scheme and netloc as the property URL
        property_url = f"{parsed_target_url.scheme}://{parsed_target_url.netloc}/"
        
        self.logger.info(f"Attempting to fetch GSC backlinks for property: {property_url}")

        try:
            # This is a simplified example. Real GSC API calls for backlinks
            # are more complex and involve specific report types.
            # The 'links' endpoint is for external links to your property.
            # You might need to iterate through pages of results.
            
            # Example: Fetching top linking sites
            # request = self.service.searchanalytics().query(
            #     siteUrl=property_url,
            #     body={
            #         'startDate': (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
            #         'endDate': datetime.now().strftime('%Y-%m-%d'),
            #         'dimensions': ['query', 'page'],
            #         'rowLimit': 1000
            #     }
            # )
            # response = request.execute()
            # self.logger.debug(f"GSC API response: {response}")

            # For backlinks, you'd typically use the 'links' resource, but it's complex:
            # https://developers.google.com/webmaster-tools/v3/links
            # Example: request = self.service.links().search(siteUrl=property_url, linkType='external')

            # Since direct backlink data is complex and requires property verification,
            # we'll return simulated data for now, even if the service is built.
            self.logger.warning("GSCBacklinkAPIClient: Returning simulated data. Actual GSC API integration for backlinks is complex and requires property verification.")
            
            # Simulate some GSC-like backlinks
            return [
                Backlink(
                    source_url=f"http://gsc-source1.com/article/{random.randint(100,999)}",
                    target_url=target_url,
                    anchor_text="GSC Link 1",
                    link_type=LinkType.FOLLOW,
                    context_text="Context from GSC source 1",
                    discovered_date=datetime.now() - timedelta(days=random.randint(10, 300)),
                    spam_level=SpamLevel.CLEAN
                ),
                Backlink(
                    source_url=f"http://gsc-source2.net/blog/{random.randint(100,999)}",
                    target_url=target_url,
                    anchor_text="GSC Link 2",
                    link_type=LinkType.NOFOLLOW,
                    context_text="Context from GSC source 2",
                    discovered_date=datetime.now() - timedelta(days=random.randint(10, 300)),
                    spam_level=SpamLevel.CLEAN
                )
            ]

        except Exception as e:
            self.logger.error(f"Error fetching GSC backlinks for {property_url}: {e}. Returning empty list.")
            return []


class BacklinkService:
    """
    Service for retrieving backlink information, either from a crawler or an API.
    """
    def __init__(self, api_client: Optional[BaseBacklinkAPIClient] = None):
        self.logger = logging.getLogger(__name__)
        
        # Determine which API client to use based on environment variable priority
        if os.getenv("USE_GSC_API", "false").lower() == "true":
            self.logger.info("Using GSCBacklinkAPIClient for backlink lookups.")
            self.api_client = GSCBacklinkAPIClient()
        elif os.getenv("USE_OPENLINKPROFILER_API", "false").lower() == "true":
            self.logger.info("Using OpenLinkProfilerAPIClient for backlink lookups.")
            self.api_client = OpenLinkProfilerAPIClient()
        elif os.getenv("USE_REAL_BACKLINK_API", "false").lower() == "true":
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
