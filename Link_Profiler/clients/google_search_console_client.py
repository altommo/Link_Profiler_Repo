import logging
import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

# Google API imports for GSC
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapicl.discovery import build

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager

logger = logging.getLogger(__name__)

# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly'] # Define SCOPES here

class GoogleSearchConsoleClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Real Google Search Console API client.
    
    Note: The GSC API does NOT provide backlink data. That's only available
    in the web interface. This client provides search analytics data.
    """
    
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None): # Accept session_manager and resilience_manager
        super().__init__(session_manager, resilience_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".GoogleSearchConsoleClient")
        self.service = None
        self._creds = None
        self.enabled = config_loader.get("backlink_api.gsc_api.enabled", False)
        self.credentials_file_path = config_loader.get("backlink_api.gsc_api.credentials_file", CREDENTIALS_FILE)
        self.token_file_path = config_loader.get("backlink_api.gsc_api.token_file", TOKEN_FILE)
        
        if self.enabled and self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        if not self.enabled:
            self.logger.info("Google Search Console API is disabled by configuration.")
        elif not os.path.exists(self.credentials_file_path):
            self.logger.error(f"GSC API enabled but credentials.json not found at {self.credentials_file_path}. GSC API will not function.")
            self.enabled = False
    
    async def __aenter__(self):
        """Initialize the GSC API service."""
        await super().__aenter__() # Call base client's __aenter__
        if not self.enabled:
            return self
            
        self.logger.info("Entering GSCClient context. Attempting authentication.")

        if os.path.exists(self.token_file_path):
            self._creds = Credentials.from_authorized_user_file(self.token_file_path, SCOPES)
        
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                self.logger.info("Refreshing GSC access token.")
                try:
                    # Use resilience manager for the synchronous refresh
                    await self.resilience_manager.execute_with_resilience(
                        lambda: self._creds.refresh(Request()),
                        url="https://oauth2.googleapis.com/token" # Representative URL for CB
                    )
                    # Save the refreshed token
                    with open(self.token_file_path, 'w') as token:
                        token.write(self._creds.to_json())
                    self.logger.info("GSC access token refreshed successfully.")
                except Exception as e:
                    self.logger.error(f"Error refreshing GSC token: {e}. Will retry authentication on next run.", exc_info=True)
                    self._creds = None # Invalidate credentials if refresh fails
                    self.enabled = False # Disable for current run, allow retry on next __aenter__
            else:
                self.logger.warning(f"GSC token.json not found or invalid. Attempting interactive flow. Ensure {self.credentials_file_path} exists.")
                # This interactive flow is not suitable for a headless server.
                # You would typically run this part once on a local machine to get token.json.
                try:
                    # Use resilience manager for the synchronous OAuth flow
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file_path, SCOPES)
                    self._creds = await self.resilience_manager.execute_with_resilience(
                        lambda: flow.run_local_server(port=0),
                        url="https://accounts.google.com/o/oauth2/auth" # Representative URL for CB
                    )
                    with open(self.token_file_path, 'w') as token:
                        token.write(self._creds.to_json())
                    self.logger.info(f"GSC token.json generated at {self.token_file_path}. Please restart the application if this was an interactive setup.")
                except FileNotFoundError:
                    self.logger.error(f"GSC credentials.json not found at {self.credentials_file_path}. GSC API will not function.")
                    self._creds = None
                    self.enabled = False
                except Exception as e:
                    self.logger.error(f"Error during GSC interactive authentication flow: {e}", exc_info=True)
                    self._creds = None
                    self.enabled = False

        if self._creds:
            # Build GSC service synchronously, as build() is not async
            self.service = await asyncio.to_thread(build, 'searchconsole', 'v1', credentials=self._creds)
            self.logger.info("GSC service built successfully.")
        else:
            self.logger.error("GSC authentication failed. GSC API client will not be functional.")
            self.enabled = False # Disable if auth fails
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources."""
        await super().__aexit__(exc_type, exc_val, exc_tb) # Call base client's __aexit__
        pass # No explicit cleanup for GSC service object
    
    @api_rate_limited(service="gsc_api", api_client_type="gsc_client", endpoint="get_search_analytics")
    async def get_search_analytics(self, site_url: str, start_date: str, end_date: str,
                                 dimensions: List[str] = None, row_limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get search analytics data from Google Search Console.
        
        Args:
            site_url: The site URL (must be verified in GSC)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format  
            dimensions: List of dimensions (query, page, country, device, etc.)
            row_limit: Maximum rows to return (default 1000)
            
        Returns:
            List of search analytics data
        """
        if not self.enabled or not self.service:
            self.logger.warning("GSC API is disabled or not authenticated.")
            return []
        
        if not dimensions:
            dimensions = ['query', 'page']
        
        all_rows: List[Dict[str, Any]] = []
        start_row = 0
        hard_cap = 5000 # Prevent infinite loops, configurable if needed

        while True:
            request_body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': dimensions,
                'rowLimit': row_limit,
                'startRow': start_row
            }
            
            try:
                # Use resilience manager for the synchronous GSC API call
                response = await self.resilience_manager.execute_with_resilience(
                    lambda: self.service.searchanalytics().query(
                        siteUrl=site_url,
                        body=request_body
                    ).execute(),
                    url=f"https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query" # Representative URL for CB
                )
                
                rows = response.get('rows', [])
                all_rows.extend(rows)
                
                if len(rows) < row_limit or (start_row + len(rows)) >= hard_cap:
                    break # No more pages or hit hard cap
                
                start_row += len(rows)
                await asyncio.sleep(1) # Delay between pages to avoid 429s
                
            except Exception as e: # Catch generic exception for GSC API errors
                self.logger.error(f"Error fetching search analytics for {site_url} (startRow: {start_row}): {e}")
                break # Break on other errors
        
        # Add last_fetched_at to each row
        now = datetime.utcnow().isoformat()
        for row in all_rows:
            row['last_fetched_at'] = now
        
        self.logger.info(f"Retrieved {len(all_rows)} search analytics rows for {site_url}")
        return all_rows
    
    @api_rate_limited(service="gsc_api", api_client_type="gsc_client", endpoint="get_sites")
    async def get_sites(self) -> List[Dict[str, Any]]:
        """Get list of sites in Search Console account."""
        if not self.enabled or not self.service:
            return []
        
        try:
            # Use resilience manager for the synchronous GSC API call
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.service.sites().list().execute(),
                url="https://www.googleapis.com/webmasters/v3/sites" # Representative URL for CB
            )
            sites = response.get('siteEntry', [])
            
            # Add last_fetched_at to each site entry
            now = datetime.utcnow().isoformat()
            for site in sites:
                site['last_fetched_at'] = now

            self.logger.info(f"Found {len(sites)} sites in GSC account")
            return sites
            
        except Exception as e: # Catch generic exception for GSC API errors
            self.logger.error(f"Error fetching GSC sites: {e}")
            return []
    
    @api_rate_limited(service="gsc_api", api_client_type="gsc_client", endpoint="get_sitemaps")
    async def get_sitemaps(self, site_url: str) -> List[Dict[str, Any]]:
        """Get sitemaps for a site."""
        if not self.enabled or not self.service:
            return []
        
        try:
            # Use resilience manager for the synchronous GSC API call
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.service.sitemaps().list(siteUrl=site_url).execute(),
                url=f"https://www.googleapis.com/webmasters/v3/sites/{site_url}/sitemaps" # Representative URL for CB
            )
            sitemaps = response.get('sitemap', [])
            
            # Add last_fetched_at to each sitemap entry
            now = datetime.utcnow().isoformat()
            for sitemap in sitemaps:
                sitemap['last_fetched_at'] = now

            self.logger.info(f"Found {len(sitemaps)} sitemaps for {site_url}")
            return sitemaps
            
        except Exception as e: # Catch generic exception for GSC API errors
            self.logger.error(f"Error fetching sitemaps for {site_url}: {e}")
            return []
    
    @api_rate_limited(service="gsc_api", api_client_type="gsc_client", endpoint="inspect_url")
    async def inspect_url(self, site_url: str, inspection_url: str) -> Optional[Dict[str, Any]]:
        """
        Inspect a URL (equivalent to URL Inspection tool in GSC).
        
        Args:
            site_url: The property URL
            inspection_url: The URL to inspect
            
        Returns:
            URL inspection results
        """
        if not self.enabled or not self.service:
            return None
        
        try:
            request_body = {
                'inspectionUrl': inspection_url,
                'siteUrl': site_url
            }
            
            # Use resilience manager for the synchronous GSC API call
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.service.urlInspection().index().inspect(body=request_body).execute(),
                url=f"https://www.googleapis.com/webmasters/v3/urlInspection/index:inspect" # Representative URL for CB
            )
            
            response['last_fetched_at'] = datetime.utcnow().isoformat() # Set last_fetched_at for live data
            self.logger.info(f"URL inspection completed for {inspection_url}")
            return response
            
        except Exception as e: # Catch generic exception for GSC API errors
            self.logger.error(f"Error inspecting URL {inspection_url}: {e}")
            return None
    
    async def fetch_backlinks(self, site_url: str) -> List[Dict[str, Any]]:
        """
        Fetches backlink data using the legacy Webmasters V3 Links API.
        Note: This API provides aggregated data (top linking sites, top linked URLs),
        not individual backlinks with anchor text or specific page URLs.
        """
        if not self.enabled or not self._creds:
            self.logger.warning("GSC API is disabled or not authenticated. Cannot fetch backlinks.")
            return []

        try:
            # Build a webmasters v3 service specifically for the links API
            wm_service = await asyncio.to_thread(build, 'webmasters', 'v3', credentials=self._creds)
            
            # Fetch top linking sites
            # This is the closest to "backlinks" that the GSC API offers for general use.
            # It provides domains linking to your site, not specific URLs or anchor texts.
            response = await self.resilience_manager.execute_with_resilience(
                lambda: wm_service.links().get(
                    siteUrl=site_url,
                    resource_name='topLinkingSites' # Or 'topLinkedUrls'
                ).execute(),
                url=f"https://www.googleapis.com/webmasters/v3/sites/{site_url}/links" # Representative URL for CB
            )
            
            linking_sites = response.get('topLinkingSites', [])
            
            # Normalize the output
            normalized_backlinks = []
            now = datetime.utcnow().isoformat()
            for site_data in linking_sites:
                normalized_backlinks.append({
                    "source_url": site_data.get("url"), # This is the linking domain, not a specific URL
                    "target_url": site_url,
                    "anchor_text": "N/A (GSC API limitation)",
                    "link_type": "external", # Assuming external
                    "last_fetched_at": now,
                    "gsc_data": site_data # Keep raw GSC data for context
                })
            
            self.logger.info(f"Retrieved {len(normalized_backlinks)} linking sites from GSC for {site_url}.")
            return normalized_backlinks

        except Exception as e: # Catch generic exception for GSC API errors
            self.logger.error(f"Error fetching backlinks from GSC for {site_url}: {e}", exc_info=True)
            return []

