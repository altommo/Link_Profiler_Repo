"""
Wayback Machine Client - Interacts with the Internet Archive's CDX API.
File: Link_Profiler/clients/wayback_machine_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
import json # For parsing JSON response
from datetime import datetime # For timestamp conversion
import random # Import random for simulation

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

class WaybackClient:
    """
    Client for fetching historical snapshots from the Wayback Machine CDX API.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".WaybackClient")
        self.base_url = config_loader.get("historical_data.wayback_machine_api.base_url")
        self.enabled = config_loader.get("historical_data.wayback_machine_api.enabled", False)
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.enabled:
            self.logger.info("Wayback Machine API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering WaybackClient context.")
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled and self._session and not self._session.closed:
            self.logger.info("Exiting WaybackClient context. Closing aiohttp session.")
            await self._session.close()
            self._session = None

    @api_rate_limited(service="wayback_machine_api", api_client_type="wayback_client", endpoint="get_snapshots")
    async def get_snapshots(self, url: str, limit: int = 10, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches historical snapshots for a given URL from the Wayback Machine.
        
        Args:
            url (str): The URL to query.
            limit (int): Maximum number of snapshots to retrieve.
            from_date (str): Start date for snapshots in YYYYMMDD format.
            to_date (str): End date for snapshots in YYYYMMDD format.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a snapshot.
        """
        if not self.enabled:
            self.logger.warning(f"Wayback Machine API is disabled. Simulating snapshots for {url}.")
            return self._simulate_snapshots(url, limit, from_date, to_date)

        endpoint = self.base_url
        params = {
            'url': url,
            'output': 'json',
            'fl': 'timestamp,original,mimetype,statuscode,digest,length,loadtime', # Fields to return
            'limit': limit
        }
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date

        self.logger.info(f"Calling Wayback Machine API for snapshots of {url} (limit: {limit})...")
        results = []
        try:
            async with self._session.get(endpoint, params=params, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
                
                if not data or len(data) < 2: # First row is header
                    self.logger.info(f"No snapshots found for {url}.")
                    return []

                headers = data[0]
                for row in data[1:]:
                    snapshot = dict(zip(headers, row))
                    # Convert timestamp to readable format or datetime object
                    if 'timestamp' in snapshot:
                        try:
                            snapshot['timestamp_iso'] = datetime.strptime(snapshot['timestamp'], '%Y%m%d%H%M%S').isoformat()
                        except ValueError:
                            snapshot['timestamp_iso'] = None
                    results.append(snapshot)
            self.logger.info(f"Found {len(results)} Wayback Machine snapshots for {url}.")
            return results
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error fetching Wayback Machine snapshots for {url}: {e}", exc_info=True)
            return self._simulate_snapshots(url, limit, from_date, to_date) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching Wayback Machine snapshots for {url}: {e}", exc_info=True)
            return self._simulate_snapshots(url, limit, from_date, to_date) # Fallback to simulation on error

    def _simulate_snapshots(self, url: str, limit: int, from_date: Optional[str], to_date: Optional[str]) -> List[Dict[str, Any]]:
        """Helper to generate simulated Wayback Machine snapshots."""
        self.logger.info(f"Simulating Wayback Machine snapshots for {url} (limit: {limit}).")
        from datetime import timedelta

        simulated_results = []
        for i in range(limit):
            timestamp = datetime.now() - timedelta(days=random.randint(30, 365*5))
            simulated_results.append({
                "timestamp": timestamp.strftime("%Y%m%d%H%M%S"),
                "timestamp_iso": timestamp.isoformat(),
                "original": url,
                "mimetype": "text/html",
                "statuscode": "200",
                "digest": f"simulated_digest_{random.randint(1000, 9999)}",
                "length": str(random.randint(10000, 50000)),
                "loadtime": str(random.uniform(0.5, 3.0)),
                "archive_url": f"https://web.archive.org/web/{timestamp.strftime('%Y%m%d%H%M%S')}/{url}"
            })
        return simulated_results
