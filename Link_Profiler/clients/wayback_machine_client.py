"""
clients/wayback_machine_client.py - COMPLETE REWRITE
Based on Internet Archive CDX API documentation
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote_plus
import time # Import time for time.monotonic()
import aiohttp # Re-import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient # Assuming this exists
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class WaybackSnapshot:
    """Data class for a Wayback Machine snapshot."""
    
    def __init__(self, cdx_data: List[str]):
        # CDX format: urlkey, timestamp, original, mimetype, statuscode, digest, length
        self.urlkey = cdx_data[0] if len(cdx_data) > 0 else ""
        self.timestamp = cdx_data[1] if len(cdx_data) > 1 else ""
        self.original_url = cdx_data[2] if len(cdx_data) > 2 else ""
        self.mimetype = cdx_data[3] if len(cdx_data) > 3 else ""
        self.status_code = cdx_data[4] if len(cdx_data) > 4 else ""
        self.digest = cdx_data[5] if len(cdx_data) > 5 else ""
        self.length = cdx_data[6] if len(cdx_data) > 6 else ""
        
        # Generate derived fields
        self.timestamp_iso = self._parse_timestamp()
        self.archive_url = self._generate_archive_url()
        self.raw_archive_url = self._generate_raw_archive_url()
        self.last_fetched_at = datetime.utcnow() # New: Timestamp of last fetch/update
    
    def _parse_timestamp(self) -> Optional[str]:
        """Convert Wayback timestamp to ISO format."""
        if not self.timestamp or len(self.timestamp) < 14:
            return None
        try:
            dt = datetime.strptime(self.timestamp, '%Y%m%d%H%M%S')
            return dt.isoformat()
        except ValueError:
            return None
    
    def _generate_archive_url(self) -> str:
        """Generate the Wayback Machine archive URL."""
        if self.timestamp and self.original_url:
            return f"https://web.archive.org/web/{self.timestamp}/{self.original_url}"
        return ""
    
    def _generate_raw_archive_url(self) -> str:
        """Generate the raw content URL (without Wayback navigation)."""
        if self.timestamp and self.original_url:
            return f"https://web.archive.org/web/{self.timestamp}id_/{self.original_url}"
        return ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            'urlkey': self.urlkey,
            'timestamp': self.timestamp,
            'timestamp_iso': self.timestamp_iso,
            'original_url': self.original_url,
            'mimetype': self.mimetype,
            'status_code': self.status_code,
            'digest': self.digest,
            'length': self.length,
            'archive_url': self.archive_url,
            'raw_archive_url': self.raw_archive_url,
            'last_fetched_at': self.last_fetched_at.isoformat() # Include last_fetched_at
        }

class WaybackClient(BaseAPIClient):
    """
    Real implementation of Wayback Machine CDX API client.
    Based on Internet Archive CDX Server documentation.
    """
    
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Pass api_quota_manager to BaseAPIClient
        self.logger = logging.getLogger(__name__ + ".WaybackClient")
        # The base_url should point to the CDX API endpoint, e.g., "http://web.archive.org/cdx/search/cdx"
        self.base_url = config_loader.get("historical_data.wayback_machine_api.base_url", 
                                         "http://web.archive.org/cdx/search/cdx")
        self.enabled = config_loader.get("historical_data.wayback_machine_api.enabled", False)
        # resilience_manager and api_quota_manager are now handled by BaseAPIClient's __init__
        
        self._last_call_time: float = 0.0 # For explicit throttling

        if not self.enabled:
            self.logger.info("Wayback Machine API is disabled by configuration.")

    async def __aenter__(self):
        """Initializes the aiohttp session."""
        await super().__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the aiohttp session."""
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def _throttle(self):
        """Ensures at least 0.5 second delay between calls to Wayback Machine."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < 0.5:
            wait_time = 0.5 - elapsed
            self.logger.debug(f"Throttling Wayback Machine API. Waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)
        self._last_call_time = time.monotonic()

    @api_rate_limited(service="wayback_machine_api", api_client_type="wayback_client", endpoint="get_snapshots")
    async def get_snapshots(self, url: str, limit: int = 10, from_date: Optional[str] = None, 
                          to_date: Optional[str] = None, collapse: Optional[str] = None) -> List[WaybackSnapshot]:
        """
        Fetch historical snapshots for a URL from Wayback Machine CDX API.
        
        Args:
            url: The URL to query (will be URL encoded)
            limit: Maximum number of snapshots to retrieve
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format  
            collapse: Collapse parameter (e.g., 'timestamp:10' for hourly)
            
        Returns:
            List of WaybackSnapshot objects
        """
        if not self.enabled:
            self.logger.warning("Wayback Machine API is disabled.")
            return []

        await self._throttle() # Apply explicit throttling

        # Normalize dates to YYYYMMDD format
        if from_date:
            try:
                from_date = datetime.strptime(from_date, "%Y-%m-%d").strftime("%Y%m%d")
            except ValueError:
                self.logger.warning(f"Invalid from_date format: {from_date}. Expected YYYY-MM-DD.")
                from_date = None
        if to_date:
            try:
                to_date = datetime.strptime(to_date, "%Y-%m-%d").strftime("%Y%m%d")
            except ValueError:
                self.logger.warning(f"Invalid to_date format: {to_date}. Expected YYYY-MM-DD.")
                to_date = None

        # Build query parameters
        params = {
            'url': url,
            'output': 'json',
            'fl': 'urlkey,timestamp,original,mimetype,statuscode,digest,length',
            'limit': limit
        }
        
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        if collapse:
            params['collapse'] = collapse

        self.logger.info(f"Fetching Wayback snapshots for {url} (limit: {limit})")
        
        start_time = time.monotonic()
        success = False
        try:
            # Use resilience manager for the actual HTTP request
            data = await self._make_request("GET", self.base_url, params=params)
            success = True
            
            if not data or len(data) < 2:  # First row is header
                self.logger.info(f"No snapshots found for {url}")
                return []

            # Skip header row and create snapshots
            snapshots = []
            for row in data[1:]:  # Skip header
                try:
                    snapshot = WaybackSnapshot(row)
                    snapshots.append(snapshot)
                except Exception as e:
                    self.logger.warning(f"Error parsing snapshot data: {e}")
                    continue
            
            self.logger.info(f"Found {len(snapshots)} Wayback snapshots for {url}")
            return snapshots
                
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                self.logger.warning(f"Wayback Machine API rate limit exceeded for {url}. Retrying after 60 seconds.")
                await asyncio.sleep(60)
                return await self.get_snapshots(url, limit, from_date, to_date, collapse) # Retry the call
            else:
                self.logger.error(f"Network error fetching Wayback snapshots for {url} (Status: {e.status}): {e}")
                return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching Wayback snapshots for {url}: {e}")
            return []
        finally:
            response_time_ms = (time.monotonic() - start_time) * 1000
            self.api_quota_manager.record_api_performance("wayback_machine_api", success, response_time_ms)

    @api_rate_limited(service="wayback_machine_api", api_client_type="wayback_client", endpoint="check_availability")
    async def check_availability(self, url: str, timestamp: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Check if a URL is available in Wayback Machine using the availability API.
        
        Args:
            url: URL to check
            timestamp: Optional timestamp in YYYYMMDD format
            
        Returns:
            Dictionary with availability info or None if not available
        """
        if not self.enabled:
            return None
            
        await self._throttle() # Apply explicit throttling

        availability_url = "http://archive.org/wayback/available"
        params = {'url': url}
        
        if timestamp:
            params['timestamp'] = timestamp
            
        start_time = time.monotonic()
        success = False
        try:
            # Use resilience manager for the actual HTTP request
            data = await self._make_request("GET", availability_url, params=params)
            success = True
            
            if data.get('archived_snapshots', {}).get('closest', {}).get('available'):
                data['last_fetched_at'] = datetime.utcnow().isoformat() # Set last_fetched_at for live data
                return data['archived_snapshots']['closest']
                    
            return None
                
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                self.logger.warning(f"Wayback Machine API rate limit exceeded for availability check for {url}. Retrying after 60 seconds.")
                await asyncio.sleep(60)
                return await self.check_availability(url, timestamp) # Retry the call
            else:
                self.logger.error(f"Network error checking Wayback availability for {url} (Status: {e.status}): {e}")
                return None
        except Exception as e:
            self.logger.error(f"Unexpected error checking Wayback availability for {url}: {e}")
            return None
        finally:
            response_time_ms = (time.monotonic() - start_time) * 1000
            self.api_quota_manager.record_api_performance("wayback_machine_api", success, response_time_ms)

    async def get_first_snapshot(self, url: str) -> Optional[WaybackSnapshot]:
        """Get the earliest snapshot of a URL."""
        snapshots = await self.get_snapshots(url, limit=1)
        return snapshots[0] if snapshots else None
    
    async def get_latest_snapshot(self, url: str) -> Optional[WaybackSnapshot]:
        """Get the most recent snapshot of a URL."""
        snapshots = await self.get_snapshots(url, limit=1, collapse='timestamp:1')
        return snapshots[-1] if snapshots else None

