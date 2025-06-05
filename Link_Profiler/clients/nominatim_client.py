"""
Nominatim Client - Interacts with OpenStreetMap Nominatim API.
File: Link_Profiler/clients/nominatim_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp
import json # For parsing JSON response
import random # Import random for simulation
import time # Import time for time.monotonic()

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class NominatimClient:
    """
    Client for geocoding and reverse geocoding using OpenStreetMap Nominatim API.
    Requires a custom User-Agent.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        self.logger = logging.getLogger(__name__ + ".NominatimClient")
        self.base_url = config_loader.get("local_seo.nominatim_api.base_url")
        self.user_agent = config_loader.get("local_seo.nominatim_api.user_agent")
        self.enabled = config_loader.get("local_seo.nominatim_api.enabled", False)
        self.session_manager = session_manager
        if self.session_manager is None:
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager
            self.session_manager = global_session_manager
            logger.warning("No SessionManager provided to NominatimClient. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager
        if self.resilience_manager is None:
            from Link_Profiler.utils.distributed_circuit_breaker import distributed_resilience_manager as global_resilience_manager
            self.resilience_manager = global_resilience_manager
            logger.warning("No DistributedResilienceManager provided to NominatimClient. Falling back to global instance.")

        self._last_call_time: float = 0.0 # For explicit throttling

        if not self.enabled:
            self.logger.info("Nominatim API is disabled by configuration.")
        elif not self.user_agent:
            self.logger.warning("Nominatim API is enabled but user_agent is missing. Functionality will be simulated.")
            self.enabled = False # Effectively disable if user_agent is missing

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering NominatimClient context.")
            await self.session_manager.__aenter__()
            # Set user-agent for the session manager's client session
            if self.session_manager._session:
                self.session_manager._session.headers.update({'User-Agent': self.user_agent})
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled:
            self.logger.info("Exiting NominatimClient context.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def _throttle(self):
        """Ensures at least 1 second delay between calls to Nominatim."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < 1.0:
            wait_time = 1.0 - elapsed
            self.logger.debug(f"Throttling Nominatim API. Waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)
        self._last_call_time = time.monotonic()

    @api_rate_limited(service="nominatim_api", api_client_type="nominatim_client", endpoint="geocode_search")
    async def geocode_search(self, query: str, limit: int = 1) -> List[Dict[str, Any]]:
        """
        Performs a geocoding search for a given query (e.g., address, business name).
        
        Args:
            query (str): The search query (e.g., "Eiffel Tower, Paris", "1600 Amphitheatre Parkway, Mountain View, CA").
            limit (int): Maximum number of results to return.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a geocoded location.
        """
        if not self.enabled:
            self.logger.warning(f"Nominatim API is disabled. Simulating geocode search for '{query}'.")
            return self._simulate_geocode_results(query, limit)

        await self._throttle() # Apply explicit throttling

        endpoint = f"{self.base_url}/search" # Corrected endpoint for search
        params = {
            'q': query,
            'format': 'json',
            'limit': limit,
            'addressdetails': 1 # Include detailed address breakdown
        }

        self.logger.info(f"Calling Nominatim API for geocode search: '{query}' (limit: {limit})...")
        results = []
        try:
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(endpoint, params=params, timeout=10),
                url=endpoint # Pass the endpoint for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            results.extend(data)
            self.logger.info(f"Found {len(results)} geocode results for '{query}'.")
            return results
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                self.logger.warning(f"Nominatim API rate limit exceeded for '{query}'. Retrying after 60 seconds.")
                await asyncio.sleep(60)
                return await self.geocode_search(query, limit) # Retry the call
            else:
                self.logger.error(f"Network/API error geocoding '{query}' with Nominatim (Status: {e.status}): {e}", exc_info=True)
                return self._simulate_geocode_results(query, limit) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error geocoding '{query}' with Nominatim: {e}", exc_info=True)
            return self._simulate_geocode_results(query, limit) # Fallback to simulation on error

    @api_rate_limited(service="nominatim_api", api_client_type="nominatim_client", endpoint="reverse_geocode")
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """
        Performs a reverse geocoding lookup for given latitude and longitude.
        
        Args:
            lat (float): Latitude.
            lon (float): Longitude.
            
        Returns:
            Optional[Dict[str, Any]]: A dictionary representing the location, or None.
        """
        if not self.enabled:
            self.logger.warning(f"Nominatim API is disabled. Simulating reverse geocode for {lat}, {lon}.")
            return self._simulate_reverse_geocode_result(lat, lon)

        await self._throttle() # Apply explicit throttling

        endpoint = f"{self.base_url}/reverse"
        params = {
            'lat': lat,
            'lon': lon,
            'format': 'json',
            'addressdetails': 1
        }

        self.logger.info(f"Calling Nominatim API for reverse geocode: {lat}, {lon}...")
        try:
            response = await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(endpoint, params=params, timeout=10),
                url=endpoint # Pass the endpoint for circuit breaker naming
            )
            response.raise_for_status()
            data = await response.json()
            return data
        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                self.logger.warning(f"Nominatim API rate limit exceeded for {lat}, {lon}. Retrying after 60 seconds.")
                await asyncio.sleep(60)
                return await self.reverse_geocode(lat, lon) # Retry the call
            else:
                self.logger.error(f"Network/API error reverse geocoding {lat}, {lon} with Nominatim (Status: {e.status}): {e}", exc_info=True)
                return self._simulate_reverse_geocode_result(lat, lon) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error reverse geocoding {lat}, {lon} with Nominatim: {e}", exc_info=True)
            return self._simulate_reverse_geocode_result(lat, lon) # Fallback to simulation on error

    def _simulate_geocode_results(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Helper to generate simulated geocode results."""
        self.logger.info(f"Simulating Nominatim geocode results for '{query}' (limit: {limit}).")
        simulated_results = []
        for i in range(limit):
            simulated_results.append({
                "place_id": random.randint(100000, 999999),
                "licence": "Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright",
                "osm_type": "node",
                "osm_id": random.randint(1000000, 9999999),
                "lat": str(random.uniform(30.0, 50.0)),
                "lon": str(random.uniform(-120.0, -70.0)),
                "display_name": f"Simulated Location {i+1}, {query}",
                "address": {
                    "road": f"Simulated Street {random.randint(1, 100)}",
                    "city": "Simulated City",
                    "state": "Simulated State",
                    "postcode": f"{random.randint(10000, 99999)}",
                    "country": "United States",
                    "country_code": "us"
                },
                "boundingbox": [str(random.uniform(30.0, 30.1)), str(random.uniform(50.0, 50.1)), str(random.uniform(-120.0, -119.9)), str(random.uniform(-70.0, -69.9))]
            })
        return simulated_results

    def _simulate_reverse_geocode_result(self, lat: float, lon: float) -> Dict[str, Any]:
        """Helper to generate simulated reverse geocode result."""
        self.logger.info(f"Simulating Nominatim reverse geocode result for {lat}, {lon}.")
        return {
            "place_id": random.randint(100000, 999999),
            "licence": "Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright",
            "osm_type": "way",
            "osm_id": random.randint(1000000, 9999999),
            "lat": str(lat),
            "lon": str(lon),
            "display_name": f"Simulated Address, Near {lat:.2f}, {lon:.2f}",
            "address": {
                "house_number": str(random.randint(1, 500)),
                "road": f"Simulated Road {random.randint(1, 100)}",
                "neighbourhood": "Simulated Neighbourhood",
                "suburb": "Simulated Suburb",
                "city": "Simulated City",
                "state": "Simulated State",
                "postcode": f"{random.randint(10000, 99999)}",
                "country": "United States",
                "country_code": "us"
            },
            "boundingbox": [str(lat - 0.01), str(lat + 0.01), str(lon - 0.01), str(lon + 0.01)]
        }

