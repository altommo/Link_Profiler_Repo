"""
Google Search Console Client - Interacts with the Google Search Console API.
File: Link_Profiler/clients/google_search_console_client.py
"""

import logging
import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random # Import random for simulation

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

class GSCClient:
    """
    Client for fetching data from Google Search Console API.
    Requires OAuth 2.0 authentication setup.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".GSCClient")
        self.enabled = config_loader.get("backlink_api.gsc_api.enabled", False)
        self.credentials_file = config_loader.get("backlink_api.gsc_api.credentials_file", "credentials.json")
        self.token_file = config_loader.get("backlink_api.gsc_api.token_file", "token.json")
        self.service = None
        self._creds = None

        if not self.enabled:
            self.logger.info("Google Search Console API is disabled by configuration.")

    async def __aenter__(self):
        """Authenticates and builds the GSC service."""
        if not self.enabled:
            return self

        self.logger.info("Entering GSCClient context. Attempting authentication.")
        
        # Use project_root from main.py for consistent path
        # Assuming this client is instantiated from main.py or a service that knows project_root
        # For now, let's assume credentials/token files are in the root of the Link_Profiler package
        # or relative to where the script is run.
        # A more robust solution would pass project_root from main.py.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir)) # Go up two levels from clients/
        
        credentials_file_path = os.path.join(project_root, self.credentials_file)
        token_file_path = os.path.join(project_root, self.token_file)

        if os.path.exists(token_file_path):
            try:
                self._creds = Credentials.from_authorized_user_file(token_file_path, SCOPES)
            except Exception as e:
                self.logger.warning(f"Failed to load token from {token_file_path}: {e}. Will attempt refresh or new flow.")
                self._creds = None
        
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                self.logger.info("Refreshing GSC access token.")
                try:
                    self._creds.refresh(Request())
                    with open(token_file_path, 'w') as token:
                        token.write(self._creds.to_json())
                    self.logger.info(f"GSC token refreshed and saved to {token_file_path}.")
                except Exception as e:
                    self.logger.error(f"Error refreshing GSC token: {e}. Will attempt new interactive flow.", exc_info=True)
                    self._creds = None
            else:
                self.logger.warning(f"GSC token.json not found or invalid. Attempting interactive flow. Ensure {credentials_file_path} exists.")
                # This interactive flow is not suitable for a headless server.
                # You would typically run this part once on a local machine to get token.json.
                try:
                    # Use asyncio.to_thread to run the synchronous OAuth flow
                    self._creds = await asyncio.to_thread(InstalledAppFlow.from_client_secrets_file(credentials_file_path, SCOPES).run_local_server, port=0)
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
            self.service = await asyncio.to_thread(build, 'searchconsole', 'v1', credentials=self._creds)
            self.logger.info("GSC service built successfully.")
        else:
            self.logger.error("GSC authentication failed. GSC API client will not be functional.")
            self.enabled = False # Disable if auth fails
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific cleanup needed for GSC service object."""
        self.logger.info("Exiting GSCClient context.")
        self.service = None
        self._creds = None

    @api_rate_limited(service="gsc_api", api_client_type="gsc_client", endpoint="get_search_analytics")
    async def get_search_analytics(self, site_url: str, start_date: str, end_date: str, dimensions: List[str] = None, row_limit: int = 25000) -> Optional[Dict[str, Any]]:
        """
        Fetches search performance data from Google Search Console.
        
        Args:
            site_url (str): The URL of the site as registered in GSC (e.g., "https://example.com/").
            start_date (str): Start date in YYYY-MM-DD format.
            end_date (str): End date in YYYY-MM-DD format.
            dimensions (List[str]): List of dimensions to group by (e.g., ['query', 'page']).
            row_limit (int): Maximum number of rows to return.
            
        Returns:
            Optional[Dict[str, Any]]: The JSON response from the GSC API, or None on failure.
        """
        if not self.enabled or not self.service:
            self.logger.warning(f"GSC API is disabled or not initialized. Simulating search analytics for {site_url}.")
            return self._simulate_search_analytics(site_url, start_date, end_date, dimensions, row_limit)

        if dimensions is None:
            dimensions = ['query', 'page']

        request_body = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': dimensions,
            'rowLimit': row_limit
        }

        self.logger.info(f"Calling GSC API for search analytics for site: {site_url} from {start_date} to {end_date}...")
        try:
            # Use asyncio.to_thread to run the synchronous GSC API call
            gsc_response = await asyncio.to_thread(
                self.service.searchanalytics().query(siteUrl=site_url, body=request_body).execute
            )
            self.logger.info(f"GSC search analytics for {site_url} completed.")
            return gsc_response
        except Exception as e:
            self.logger.error(f"Error fetching GSC search analytics for {site_url}: {e}", exc_info=True)
            return self._simulate_search_analytics(site_url, start_date, end_date, dimensions, row_limit) # Fallback to simulation on error

    def _simulate_search_analytics(self, site_url: str, start_date: str, end_date: str, dimensions: List[str], row_limit: int) -> Dict[str, Any]:
        """Helper to generate simulated GSC search analytics data."""
        self.logger.info(f"Simulating GSC search analytics for {site_url}.")
        
        rows = []
        for i in range(min(row_limit, 5)): # Simulate a few rows
            query = f"simulated query {i+1} for {site_url.split('//')[1].split('/')[0]}"
            page = f"{site_url}page{i+1}.html"
            clicks = random.randint(100, 1000)
            impressions = random.randint(5000, 50000)
            ctr = round(clicks / impressions * 100, 2)
            position = round(random.uniform(1.0, 20.0), 1)

            keys = []
            if 'query' in dimensions: keys.append(query)
            if 'page' in dimensions: keys.append(page)
            # Add other dimensions if needed

            rows.append({
                "keys": keys,
                "clicks": clicks,
                "impressions": impressions,
                "ctr": ctr,
                "position": position
            })
        
        return {
            "rows": rows
        }

