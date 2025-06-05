"""
clients/wayback_machine_client.py - COMPLETE REWRITE
Based on Internet Archive CDX API documentation
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
from datetime import datetime
from urllib.parse import quote_plus

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient # Assuming this exists
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager

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
            'raw_archive_url': self.raw_archive_url
        }

class WaybackClient(BaseAPIClient):
    """
    Real implementation of Wayback Machine CDX API client.
    Based on Internet Archive CDX Server documentation.
    """
    
    def __init__(self, session_manager: Optional[SessionManager] = None):
        super().__init__(session_manager)
        self.logger = logging.getLogger(__name__ + ".WaybackClient")
        self.base_url = config_loader.get("historical_data.wayback_machine_api.base_url", 
                                         "http://web.archive.org/cdx/search/cdx")
        self.enabled = config_loader.get("historical_data.wayback_machine_api.enabled", False)
        
        if not self.enabled:
            self.logger.info("Wayback Machine API is disabled by configuration.")

    @api_rate_limited(service="wayback_machine_api", api_client_type="wayback_client", endpoint="get_snapshots")
    async def get_snapshots(self, url: str, limit: int = 10, from_date: Optional[str] = None, 
                          to_date: Optional[str] = None, collapse: Optional[str] = None) -> List[WaybackSnapshot]:
        """
        Fetch historical snapshots for a URL from Wayback Machine CDX API.
        
        Args:
            url: The URL to query (will be URL encoded)
            limit: Maximum number of snapshots to retrieve
            from_date: Start date in YYYYMMDD format
            to_date: End date in YYYYMMDD format  
            collapse: Collapse parameter (e.g., 'timestamp:10' for hourly)
            
        Returns:
            List of WaybackSnapshot objects
        """
        if not self.enabled:
            self.logger.warning("Wayback Machine API is disabled.")
            return []

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
        
        try:
            async with self.session_manager.get(self.base_url, params=params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                
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
                
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error fetching Wayback snapshots for {url}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching Wayback snapshots for {url}: {e}")
            return []

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
            
        availability_url = "http://archive.org/wayback/available"
        params = {'url': url}
        
        if timestamp:
            params['timestamp'] = timestamp
            
        try:
            async with self.session_manager.get(availability_url, params=params, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
                
                if data.get('archived_snapshots', {}).get('closest', {}).get('available'):
                    return data['archived_snapshots']['closest']
                    
                return None
                
        except Exception as e:
            self.logger.error(f"Error checking Wayback availability for {url}: {e}")
            return None

    async def get_first_snapshot(self, url: str) -> Optional[WaybackSnapshot]:
        """Get the earliest snapshot of a URL."""
        snapshots = await self.get_snapshots(url, limit=1)
        return snapshots[0] if snapshots else None
    
    async def get_latest_snapshot(self, url: str) -> Optional[WaybackSnapshot]:
        """Get the most recent snapshot of a URL."""
        snapshots = await self.get_snapshots(url, limit=1, collapse='timestamp:1')
        return snapshots[-1] if snapshots else None
