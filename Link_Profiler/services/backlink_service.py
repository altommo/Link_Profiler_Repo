import asyncio
import logging
import os
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse
from datetime import datetime, timedelta
import random
import aiohttp
import uuid # Import uuid module
import json # Import json for caching
import redis.asyncio as redis # Import redis for type hinting

# Google API imports for GSC
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from Link_Profiler.core.models import Backlink, LinkType, SpamLevel, Domain, LinkIntersectResult # Assuming Domain model might be needed for context
from Link_Profiler.config.config_loader import config_loader # Import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited # Import the rate limiter
from Link_Profiler.monitoring.prometheus_metrics import ( # Import Prometheus metrics
    API_CACHE_HITS_TOTAL, API_CACHE_MISSES_TOTAL, API_CACHE_SET_TOTAL, API_CACHE_ERRORS_TOTAL
)
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager
from Link_Profiler.database.database import Database # Import Database
from Link_Profiler.clients.google_search_console_client import GoogleSearchConsoleClient # Import GSC Client
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

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
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept ResilienceManager
        self.logger = logging.getLogger(__name__ + ".SimulatedBacklinkAPIClient")
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to SimulatedBacklinkAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to SimulatedBacklinkAPIClient. Falling back to global instance.")


    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.debug("Entering SimulatedBacklinkAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.debug("Exiting SimulatedBacklinkAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="backlink_api", api_client_type="simulated_api", endpoint="get_backlinks")
    async def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """
        Simulates fetching backlinks for a given target URL.
        """
        self.logger.info(f"Simulating API call for backlinks for: {target_url}")
        
        try:
            # Simulate an actual HTTP request, even if it's to a dummy URL
            # Use resilience manager for the actual HTTP request
            await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(f"http://localhost:8080/simulate_backlinks/{target_url}"),
                url=f"http://localhost:8080/simulate_backlinks/{target_url}" # Pass the URL for circuit breaker naming
            )
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
                    link_type=LinkType.DOFOLLOW,
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
    This implementation demonstrates where actual API calls would go.
    """
    def __init__(self, api_key: str, base_url: str, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept ResilienceManager
        self.logger = logging.getLogger(__name__ + ".RealBacklinkAPIClient")
        self.api_key = api_key
        self.base_url = base_url
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to RealBacklinkAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to RealBacklinkAPIClient. Falling back to global instance.")


    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering RealBacklinkAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting RealBacklinkAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="backlink_api", api_client_type="real_api", endpoint="get_backlinks")
    async def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """
        Fetches backlinks for a given target URL from a real API.
        Replace with actual API call logic for your chosen provider.
        """
        endpoint = f"{self.base_url}/v1/backlinks" # Hypothetical endpoint
        params = {"target": target_url, "limit": 100, "apiKey": self.api_key} # Example parameters
        self.logger.info(f"Attempting real API call for backlinks: {endpoint}?target={target_url}...")

        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(endpoint, params=params, timeout=30),
                url=endpoint # Pass the endpoint for circuit breaker naming
            )
            response.raise_for_status() # Raise an exception for HTTP errors
            data = await response.json()
            
            backlinks = []
            # --- Replace with actual parsing logic for your chosen API ---
            # Example: assuming 'items' key with list of backlink dicts
            for item in data.get("items", []):
                # Example parsing, adjust according to actual API response structure
                source_url = item.get("source_url")
                target_url_from_api = item.get("target_url")
                anchor_text = item.get("anchor_text", "")
                link_type_str = item.get("link_type", "dofollow").lower()
                spam_score_val = item.get("spam_score", 0.0)
                
                link_type = LinkType.DOFOLLOW
                if "nofollow" in link_type_str:
                    link_type = LinkType.NOFOLLOW
                elif "sponsored" in link_type_str:
                    link_type = LinkType.SPONSORED
                elif "ugc" in link_type_str:
                    link_type = LinkType.UGC
                
                spam_level = SpamLevel.CLEAN
                if spam_score_val > 70:
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
                            context_text=item.get("context_text", ""),
                            discovered_date=datetime.fromisoformat(item.get("discovered_date")) if item.get("discovered_date") else datetime.now(),
                            spam_level=spam_level
                        )
                    )
            self.logger.info(f"RealBacklinkAPIClient: Fetched {len(backlinks)} backlinks for {target_url}.")
            return backlinks

        except Exception as e:
            self.logger.error(f"Error fetching real backlinks for {target_url}: {e}. Returning empty list.", exc_info=True)
            return []

class OpenLinkProfilerAPIClient(BaseBacklinkAPIClient):
    """
    A client for OpenLinkProfiler.org API.
    This API is free with usage limits.
    """
    def __init__(self, base_url: str, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept ResilienceManager
        self.logger = logging.getLogger(__name__ + ".OpenLinkProfilerAPIClient")
        self.base_url = base_url
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to OpenLinkProfilerAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to OpenLinkProfilerAPIClient. Falling back to global instance.")


    async def __aenter__(self):
        """Async context manager entry for client session."""
        self.logger.info("Entering OpenLinkProfilerAPIClient context.")
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        self.logger.info("Exiting OpenLinkProfilerAPIClient context.")
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="backlink_api", api_client_type="openlinkprofiler_api", endpoint="get_backlinks")
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

        try:
            # Use resilience manager for the actual HTTP request
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(endpoint, params=params, timeout=30),
                url=endpoint # Pass the endpoint for circuit breaker naming
            )
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
                link_type = LinkType.DOFOLLOW
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
            self.logger.info(f"OpenLinkProfilerAPIClient: Fetched {len(backlinks)} backlinks for {target_url}.")
            return backlinks

        except Exception as e:
            self.logger.error(f"Error fetching OpenLinkProfiler backlinks for {target_url}: {e}. Returning empty list.", exc_info=True)
            return []


class GSCBacklinkAPIClient(BaseBacklinkAPIClient):
    """
    A client for Google Search Console API.
    Requires OAuth 2.0 authentication setup.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept ResilienceManager
        self.logger = logging.getLogger(__name__ + ".GSCBacklinkAPIClient")
        self.service = None
        self._creds = None
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to GSCBacklinkAPIClient. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to GSCBacklinkAPIClient. Falling back to global instance.")


    async def __aenter__(self):
        """Authenticates and builds the GSC service."""
        self.logger.info("Entering GSCBacklinkAPIClient context. Attempting authentication.")
        
        # This part would typically be run once interactively to generate token.json
        # For a server application, you'd usually have a pre-generated token.json
        # or a more complex OAuth flow.
        
        # Use project_root from main.py for consistent path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        credentials_file_path = os.path.join(project_root, config_loader.get("backlink_api.gsc_api.credentials_file", "credentials.json"))
        token_file_path = os.path.join(project_root, config_loader.get("backlink_api.gsc_api.token_file", "token.json"))
        
        SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly'] # Define SCOPES here or import from a client config

        if os.path.exists(token_file_path):
            self._creds = Credentials.from_authorized_user_file(token_file_path, SCOPES)
        
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                self.logger.info("Refreshing GSC access token.")
                try:
                    # Use resilience manager for the synchronous refresh
                    await self.resilience_manager.execute_with_resilience(
                        lambda: self._creds.refresh(Request()),
                        url="https://oauth2.googleapis.com/token" # Representative URL for CB
                    )
                except Exception as e:
                    self.logger.error(f"Error refreshing GSC token: {e}")
                    self._creds = None # Invalidate credentials if refresh fails
            else:
                self.logger.warning(f"GSC token.json not found or invalid. Attempting interactive flow. Ensure {credentials_file_path} exists.")
                # This interactive flow is not suitable for a headless server.
                # You would typically run this part once on a local machine to get token.json.
                try:
                    # Use resilience manager for the synchronous OAuth flow
                    flow = InstalledAppFlow.from_client_secrets_file(credentials_file_path, SCOPES)
                    self._creds = await self.resilience_manager.execute_with_resilience(
                        lambda: flow.run_local_server(port=0),
                        url="https://accounts.google.com/o/oauth2/auth" # Representative URL for CB
                    )
                    with open(token_file_path, 'w') as token:
                        token.write(self._creds.to_json())
                    self.logger.info(f"GSC token.json generated at {token_file_path}. Please restart the application if this was an interactive setup.")
                except FileNotFoundError:
                    self.logger.error(f"GSC credentials.json not found at {credentials_file_path}. GSC API will not function.")
                    self._creds = None
                except Exception as e:
                    self.logger.error(f"Error during GSC interactive authentication flow: {e}", exc_info=True)
                    self._creds = None

        if self._creds:
            # Build GSC service synchronously, as build() is not async
            self.service = await asyncio.to_thread(build, 'webmasters', 'v3', credentials=self._creds)
            self.logger.info("GSC service built successfully.")
        else:
            self.logger.error("GSC authentication failed. GSC API client will not be functional.")
            self.enabled = False # Disable if auth fails
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific cleanup needed for GSC service object."""
        self.logger.info("Exiting GSCBacklinkAPIClient context.")
        pass

    @api_rate_limited(service="backlink_api", api_client_type="gsc_api", endpoint="search")
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
            gsc_response = await self.resilience_manager.execute_with_resilience(
                lambda: self.service.links().search(
                    siteUrl=property_url,
                    linkType='external', # 'external' for backlinks
                    direction='incoming', # 'incoming' for backlinks to your site
                    relationship='all' # 'all' or 'dofollow'
                ),
                url=f"https://www.googleapis.com/webmasters/v3/sites/{property_url}/links" # Representative URL for CB
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
                            link_type=LinkType.DOFOLLOW, # GSC doesn't specify nofollow for this report
                            context_text="From GSC Top Linking Site",
                            discovered_date=datetime.now(), # GSC doesn't provide discovery date for this report
                            spam_level=SpamLevel.CLEAN
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
    def __init__(self, api_client: Optional[BaseBacklinkAPIClient] = None, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600, database: Optional[Database] = None, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept ResilienceManager
        self.logger = logging.getLogger(__name__)
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.api_cache_enabled = config_loader.get("api_cache.enabled", False)
        self.db = database # New: Store database instance
        self.session_manager = session_manager # Store the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import session_manager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to BacklinkService. Falling back to local SessionManager.")
        
        self.resilience_manager = resilience_manager # New: Store ResilienceManager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to BacklinkService. Falling back to global instance.")

        # Determine which API client to use based on config_loader priority
        if config_loader.get("backlink_api.gsc_api.enabled"):
            # GSC API client handles its own authentication and potential failures
            self.logger.info("Using GSCBacklinkAPIClient for backlink lookups.")
            self.api_client = GSCBacklinkAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)
        elif config_loader.get("backlink_api.openlinkprofiler_api.enabled"):
            openlinkprofiler_base_url = config_loader.get("backlink_api.openlinkprofiler_api.base_url")
            if not openlinkprofiler_base_url:
                self.logger.warning("OpenLinkProfiler API enabled but base_url not found in config. Falling back to simulated Backlink API.")
                self.api_client = SimulatedBacklinkAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)
            else:
                self.logger.info("Using OpenLinkProfilerAPIClient for backlink lookups.")
                self.api_client = OpenLinkProfilerAPIClient(base_url=openlinkprofiler_base_url, session_manager=self.session_manager, resilience_manager=self.resilience_manager)
        elif config_loader.get("backlink_api.real_api.enabled"):
            real_api_key = config_loader.get("backlink_api.real_api.api_key")
            real_api_base_url = config_loader.get("backlink_api.real_api.base_url")
            if not real_api_key or not real_api_base_url:
                self.logger.warning("Real Backlink API enabled but API key or base_url not found in config. Falling back to simulated Backlink API.")
                self.api_client = SimulatedBacklinkAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)
            else:
                self.logger.info("Using RealBacklinkAPIClient for backlink lookups.")
                self.api_client = RealBacklinkAPIClient(api_key=real_api_key, base_url=real_api_base_url, session_manager=self.session_manager, resilience_manager=self.resilience_manager)
        else:
            self.logger.info("No specific Backlink API enabled. Using SimulatedBacklinkAPIClient.")
            self.api_client = SimulatedBacklinkAPIClient(session_manager=self.session_manager, resilience_manager=self.resilience_manager)

    async def __aenter__(self):
        """Async context manager entry for BacklinkService."""
        self.logger.debug("Entering BacklinkService context.")
        await self.api_client.__aenter__() # Enter the client's context
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for BacklinkService."""
        self.logger.debug("Exiting BacklinkService context.")
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

    async def get_backlinks_from_api(self, target_url: str) -> List[Backlink]:
        """
        Fetches backlinks for a target URL using the configured API client.
        Uses caching.
        """
        cache_key = f"backlinks:{target_url}"
        cached_result = await self._get_cached_response(cache_key, "backlink_api", "get_backlinks")
        if cached_result is not None:
            # Convert cached list of dicts back to list of Backlink objects
            return [Backlink.from_dict(bl_data) for bl_data in cached_result]

        result = await self.api_client.get_backlinks_for_url(target_url)
        if result: # Only cache if result is not empty
            await self._set_cached_response(cache_key, [bl.to_dict() for bl in result], "backlink_api", "get_backlinks") # Cache as list of dicts
        return result

    async def perform_link_intersect_analysis(self, primary_domain: str, competitor_domains: List[str]) -> LinkIntersectResult:
        """
        Performs a link intersect analysis to find common linking domains.
        Finds source domains that link to the primary domain AND at least one of the competitor domains.
        """
        if not self.db:
            self.logger.error("Database instance not provided to BacklinkService. Cannot perform link intersect analysis.")
            return LinkIntersectResult(primary_domain=primary_domain, competitor_domains=competitor_domains, common_linking_domains=[])

        all_target_domains = [primary_domain] + competitor_domains
        linking_domains_map = self.db.get_source_domains_for_target_domains(all_target_domains)

        primary_linking_domains = linking_domains_map.get(primary_domain, set())
        
        common_linking_domains = set()
        for comp_domain in competitor_domains:
            comp_linking_domains = linking_domains_map.get(comp_domain, set())
            # Find sources that link to primary AND this specific competitor
            intersection = primary_linking_domains.intersection(comp_linking_domains)
            common_linking_domains.update(intersection) # Add to the overall set of common domains

        self.logger.info(f"Performed link intersect analysis for {primary_domain} against {competitor_domains}. Found {len(common_linking_domains)} common linking domains.")
        return LinkIntersectResult(
            primary_domain=primary_domain,
            competitor_domains=competitor_domains,
            common_linking_domains=sorted(list(common_linking_domains)) # Return sorted list for consistency
        )
