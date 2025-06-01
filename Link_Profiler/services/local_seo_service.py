"""
Local SEO Service - Provides functionalities for local SEO data.
File: Link_Profiler/services/local_seo_service.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import json
import redis.asyncio as redis

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.nominatim_client import NominatimClient

logger = logging.getLogger(__name__)

class LocalSEOService:
    """
    Service for fetching local SEO data using APIs like OpenStreetMap Nominatim.
    """
    def __init__(self, nominatim_client: NominatimClient, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600):
        self.logger = logging.getLogger(__name__)
        self.nominatim_client = nominatim_client
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.enabled = config_loader.get("local_seo.nominatim_api.enabled", False)

        if not self.enabled:
            self.logger.info("Local SEO Service is disabled by configuration (Nominatim API is disabled).")

    async def __aenter__(self):
        """Async context manager entry for LocalSEOService."""
        self.logger.debug("Entering LocalSEOService context.")
        await self.nominatim_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for LocalSEOService."""
        self.logger.debug("Exiting LocalSEOService context.")
        await self.nominatim_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.redis_client:
            await self.redis_client.close()

    async def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                self.logger.error(f"Error retrieving from cache for {cache_key}: {e}", exc_info=True)
        return None

    async def _set_cached_response(self, cache_key: str, data: Any):
        if self.redis_client:
            try:
                await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
                self.logger.debug(f"Cached {cache_key} with TTL {self.cache_ttl}")
            except Exception as e:
                self.logger.error(f"Error setting cache for {cache_key}: {e}", exc_info=True)

    async def geocode_business_location(self, business_name: str, city: str, country: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Geocodes a business location using Nominatim.
        """
        if not self.nominatim_client.enabled:
            self.logger.warning("Nominatim client is disabled. Cannot geocode business location.")
            return []
        
        query = f"{business_name}, {city}"
        if country:
            query += f", {country}"

        cache_key = f"nominatim_geocode:{query}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            return cached_result

        results = await self.nominatim_client.geocode_search(query)
        if results:
            await self._set_cached_response(cache_key, results)
        return results

    async def get_nearby_places(self, lat: float, lon: float, radius_km: float = 1.0, query_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Finds nearby places using reverse geocoding and potentially further searches.
        Note: Nominatim's reverse geocoding is for a single point. For "nearby places",
        a more advanced API or local database would be needed. This is a conceptual placeholder.
        """
        if not self.nominatim_client.enabled:
            self.logger.warning("Nominatim client is disabled. Cannot find nearby places.")
            return []

        self.logger.info(f"Simulating nearby places for {lat}, {lon} (radius: {radius_km}km, type: {query_type}).")
        # Nominatim doesn't directly support "nearby places" search.
        # This would typically involve a spatial database or a dedicated Places API (e.g., Google Places).
        # For now, we'll simulate a few generic nearby points.
        
        import random
        simulated_places = []
        for i in range(random.randint(1, 5)):
            simulated_places.append({
                "name": f"Simulated Cafe {i+1}",
                "address": f"123 Fake St, Simulated City",
                "lat": lat + random.uniform(-0.01, 0.01),
                "lon": lon + random.uniform(-0.01, 0.01),
                "type": query_type or "restaurant",
                "distance_km": round(random.uniform(0.1, radius_km), 2)
            })
        return simulated_places
