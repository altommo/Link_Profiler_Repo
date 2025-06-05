"""
Google Search Console Client - Authenticates and interacts with Google Search Console API.
File: Link_Profiler/clients/google_search_console_client.py
"""

import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

# The file token.json stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

class GSCClient:
    """
    Client for interacting with the Google Search Console API.
    Handles OAuth 2.0 authentication.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self.logger = logging.getLogger(__name__ + ".GSCClient")
        self.service = None
        self._creds = None
        self.enabled = config_loader.get("backlink_api.gsc_api.enabled", False)
        self.credentials_file = config_loader.get("backlink_api.gsc_api.credentials_file", CREDENTIALS_FILE)
        self.token_file = config_loader.get("backlink_api.gsc_api.token_file", TOKEN_FILE)
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to GSCClient. Falling back to local SessionManager.")

        if not self.enabled:
            self.logger.info("Google Search Console API is disabled by configuration.")
        elif not os.path.exists(self.credentials_file_path):
            self.logger.error(f"GSC API enabled but credentials.json not found at {self.credentials_file_path}. GSC API will not function.")
            self.enabled = False

    async def __aenter__(self):
        """Authenticates and builds the GSC service."""
        if not self.enabled:
            return self

        self.logger.info("Entering GSCClient context. Attempting authentication.")
        
        # Ensure session manager is entered
        await self.session_manager.__aenter__()

        if os.path.exists(self.token_file_path):
            self._creds = Credentials.from_authorized_user_file(self.token_file_path, SCOPES)
        
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                self.logger.info("Refreshing GSC access token.")
                try:
                    # Use asyncio.to_thread to run the synchronous refresh
                    await asyncio.to_thread(self._creds.refresh, Request())
                except Exception as e:
                    self.logger.error(f"Error refreshing GSC token: {e}")
                    self._creds = None # Invalidate credentials if refresh fails
            else:
                self.logger.warning(f"GSC token.json not found or invalid. Attempting interactive flow. Ensure {self.credentials_file_path} exists.")
                # This interactive flow is not suitable for a headless server.
                # You would typically run this part once on a local machine to get token.json.
                try:
                    # Use asyncio.to_thread to run the synchronous OAuth flow
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file_path, SCOPES)
                    self._creds = await asyncio.to_thread(flow.run_local_server, port=0)
                    with open(self.token_file_path, 'w') as token:
                        token.write(self._creds.to_json())
                    self.logger.info(f"GSC token.json generated at {self.token_file_path}. Please restart the application if this was an interactive setup.")
                except FileNotFoundError:
                    self.logger.error(f"GSC credentials.json not found at {self.credentials_file_path}. GSC API will not function.")
                    self._creds = None
                except Exception as e:
                    self.logger.error(f"Error during GSC interactive authentication flow: {e}", exc_info=True)
                    self._creds = None

        if self._creds:
            # Build GSC service synchronously, as build() is not async
            self.service = await asyncio.to_thread(build, 'searchconsole', 'v1', credentials=self._creds)
            self.logger.info("GSC service built successfully.")
        else:
            self.logger.error("GSC authentication failed. GSC API client will not be functional.")
            self.enabled = False # Disable if auth fails
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific cleanup needed for GSC service object."""
        if self.enabled:
            self.logger.info("Exiting GSCClient context.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="google_search_console_api", api_client_type="gsc_client", endpoint="list_sites")
    async def list_sites(self) -> List[str]:
        """
        Lists all sites verified in the authenticated Google Search Console account.
        """
        if not self.service:
            self.logger.error("GSC service not initialized. Cannot list sites.")
            return []
        try:
            # Use asyncio.to_thread to run the synchronous GSC API call
            response = await asyncio.to_thread(self.service.sites().list().execute)
            site_urls = [site['siteUrl'] for site in response.get('siteEntry', [])]
            self.logger.info(f"Found {len(site_urls)} sites in GSC.")
            return site_urls
        except Exception as e:
            self.logger.error(f"Error listing GSC sites: {e}. Returning empty list.", exc_info=True)
            return []

    @api_rate_limited(service="google_search_console_api", api_client_type="gsc_client", endpoint="query_search_analytics")
    async def query_search_analytics(self, site_url: str, start_date: datetime, end_date: datetime, dimensions: List[str], row_limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Queries Search Analytics data for a given site.
        """
        if not self.service:
            self.logger.error("GSC service not initialized. Cannot query search analytics.")
            return []
        
        request_body = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'dimensions': dimensions,
            'rowLimit': row_limit
        }
        self.logger.info(f"Querying GSC Search Analytics for {site_url} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")

        try:
            # Use asyncio.to_thread to run the synchronous GSC API call
            response = await asyncio.to_thread(
                self.service.searchanalytics().query,
                siteUrl=site_url,
                body=request_body
            ).execute()
            
            rows = response.get('rows', [])
            self.logger.info(f"Found {len(rows)} rows of search analytics data for {site_url}.")
            return rows
        except Exception as e:
            self.logger.error(f"Error querying GSC Search Analytics for {site_url}: {e}. Returning empty list.", exc_info=True)
            return []
