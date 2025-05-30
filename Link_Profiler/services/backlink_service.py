import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime, timedelta
import random
import aiohttp
import uuid # Import uuid module

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
TOKEN_FILE = 'token.json' # Corrected to .json

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
        
        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("SimulatedBacklinkAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession()
            close_session_after_use = True

        try:
            async with session_to_use.get(f"http://localhost:8080/simulate_backlinks/{target_url}") as response:
                # We don't care about the actual response, just that the request was made
                pass
        except aiohttp.ClientConnectorError:
            # This is expected if localhost:8080 is not running, simulating network activity
            pass
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated backlink fetch: {e}")
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

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
                    id=str(uuid.uuid4()), # Ensure ID is generated
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
                    id=str(uuid.uuid4()), # Ensure ID is generated
                    source_url="http://example.com/blog/quotes-review",
                    target_url="http://quotes.toscrape.com/",
                    anchor_text="Great Quotes Site",
                    link_type=LinkType.FOLLOW,
                    context_text="Check out this great quotes site.",
                    spam_level=SpamLevel.CLEAN
                ),
                Backlink(
                    id=str(uuid.uuid4()), # Ensure ID is generated
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

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("RealBacklinkAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession(headers={"X-API-Key": self.api_key})
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                
                # --- Placeholder for parsing real API response into Backlink objects ---
                # This part is highly dependent on the actual API's response structure.
                # You would parse `await response.json()` here.
                
                self.logger.warning("RealBacklinkAPIClient: Returning simulated data. Replace with actual API response parsing.")
                
                # Return a fixed set of dummy backlinks to represent a successful API call
                # This is distinct from SimulatedBacklinkAPIClient's random generation
                return [
                    Backlink(
                        id=str(uuid.uuid4()), # Generate a unique ID
                        source_url="http://real-api-source1.com/page/1",
                        target_url=target_url,
                        anchor_text="Real API Link 1",
                        link_type=LinkType.FOLLOW,
                        context_text="Context from real API source 1",
                        discovered_date=datetime.now() - timedelta(days=30),
                        spam_level=SpamLevel.CLEAN
                    ),
                    Backlink(
                        id=str(uuid.uuid4()), # Generate a unique ID
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
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()

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
        # OpenLinkProfiler often works best with just the domain or root URL
        domain_or_url = f"{parsed_target_url.scheme}://{parsed_target_url.netloc}" if parsed_target_url.netloc else target_url
        
        endpoint = self.base_url
        params = {"url": domain_or_url, "output": "json"}
        self.logger.info(f"Attempting OpenLinkProfiler API call for backlinks: {endpoint}?url={domain_or_url}...")

        session_to_use = self._session
        close_session_after_use = False
        if session_to_use is None or session_to_use.closed:
            self.logger.warning("OpenLinkProfilerAPIClient: aiohttp session not active. Creating temporary session for this call.")
            session_to_use = aiohttp.ClientSession()
            close_session_after_use = True
        else:
            close_session_after_use = False

        try:
            async with session_to_use.get(endpoint, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                
                backlinks = []
                # OpenLinkProfiler's JSON structure might vary, this is a common assumption
                # Based on their documentation, backlinks are under 'links' key
                for item in data.get("links", []): # Adjust key based on actual API response
                    source_url = item.get("source_url")
                    target_url_from_api = item.get("target_url") # API might return canonical target
                    anchor_text = item.get("anchor_text", "")
                    link_type_str = item.get("link_type", "dofollow").lower() # e.g., "dofollow", "nofollow"
                    spam_score_val = item.get("spam_score", 0.0) # Assuming a score
                    
                    # Map OpenLinkProfiler's link types to our LinkType enum
                    link_type = LinkType.FOLLOW
                    if "nofollow" in link_type_str:
                        link_type = LinkType.NOFOLLOW
                    elif "sponsored" in link_type_str:
                        link_type = LinkType.SPONSORED
                    elif "ugc" in link_type_str:
                        link_type = LinkType.UGC
                    elif "redirect" in link_type_str: # OpenLinkProfiler might have redirect type
                        link_type = LinkType.REDIRECT
                    elif "canonical" in link_type_str: # OpenLinkProfiler might have canonical type
                        link_type = LinkType.CANONICAL
                    
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
                                id=str(uuid.uuid4()), # Generate a unique ID
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
        finally:
            if close_session_after_use and not session_to_use.closed:
                await session_to_use.close()


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
                    # Use asyncio.to_thread to run the synchronous OAuth flow
                    self._creds = await asyncio.to_thread(InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES).run_local_server, port=0)
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
            # Build GSC service synchronously, as build() is not async
            self.service = await asyncio.to_thread(build, 'webmasters', 'v3', credentials=self._creds)
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
            # GSC API does not provide a direct "list all backlinks" endpoint.
            # The 'links' resource provides aggregated data (e.g., top linking sites, top linked URLs).
            # We'll fetch 'top linking sites' as a proxy for backlink data.
            # This requires the property to be verified in GSC.
            
            # Use asyncio.to_thread to run the synchronous GSC API call
            # This fetches top linking sites, which is the closest to "backlinks" GSC offers for general use.
            gsc_response = await asyncio.to_thread(
                self.service.links().search,
                siteUrl=property_url,
                linkType='external', # 'external' for backlinks
                direction='incoming', # 'incoming' for backlinks to your site
                relationship='all' # 'all' or 'dofollow'
            )
            result = await asyncio.to_thread(gsc_response.execute)
            
            backlinks = []
            # Parse the GSC response into Backlink objects
            # GSC 'links' data is aggregated, so source_url will be the linking domain,
            # and target_url will be the property_url. Anchor text is not provided.
            for site_row in result.get('linkingSites', []):
                source_domain = site_row.get('siteUrl')
                if source_domain:
                    # GSC provides siteUrl, not specific page URL, so we'll use domain as source_url
                    backlinks.append(
                        Backlink(
                            id=str(uuid.uuid4()),
                            source_url=source_domain,
                            target_url=property_url, # Target is the property itself
                            anchor_text="", # GSC API doesn't provide anchor text for this report
                            link_type=LinkType.FOLLOW, # GSC doesn't specify nofollow for this report
                            context_text="From GSC Top Linking Site",
                            discovered_date=datetime.now(), # GSC doesn't provide discovery date for this report
                            spam_level=SpamLevel.CLEAN # Assume clean from GSC
                        )
                    )
            self.logger.info(f"GSCBacklinkAPIClient: Found {len(backlinks)} backlinks for {target_url} from GSC.")
            return backlinks

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
