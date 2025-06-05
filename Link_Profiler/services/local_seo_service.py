"""
Local SEO Service - Provides functionalities for local SEO data.
File: Link_Profiler/services/local_seo_service.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import json
from math import radians, sin, cos, asin, sqrt
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
        Finds nearby places using the OpenStreetMap Overpass API.

        Args:
            lat (float): Latitude of the search center.
            lon (float): Longitude of the search center.
            radius_km (float): Search radius in kilometers.
            query_type (Optional[str]): Amenity type to search for (e.g. 'cafe').

        Returns:
            List[Dict[str, Any]]: List of places with name, address, coordinates and distance.
        """
        if not self.nominatim_client.enabled:
            self.logger.warning("Nominatim client is disabled. Cannot find nearby places.")
            return []

        amenity = query_type or "cafe"
        cache_key = f"overpass_nearby:{lat}:{lon}:{radius_km}:{amenity}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            return cached_result

        radius_m = int(radius_km * 1000)
        overpass_url = "https://overpass-api.de/api/interpreter"
        overpass_query = f"[out:json];node(around:{radius_m},{lat},{lon})[amenity={amenity}];out;"

        self.logger.info(
            f"Querying Overpass API for '{amenity}' around {lat}, {lon} within {radius_km} km."
        )

        try:
            response = await self.nominatim_client.resilience_manager.execute_with_resilience(
                lambda url: self.nominatim_client.session_manager.post(url, data=overpass_query, timeout=10),
                url=overpass_url
            )
            data = await response.json()
        except Exception as e:
            self.logger.error(f"Error querying Overpass API: {e}", exc_info=True)
            return []

        def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            R = 6371.0
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            return R * c

        places: List[Dict[str, Any]] = []
        for element in data.get("elements", []):
            lat_p = element.get("lat")
            lon_p = element.get("lon")
            if lat_p is None or lon_p is None:
                continue

            tags = element.get("tags", {})
            name = tags.get("name", amenity.title())
            address_parts = [
                tags.get("addr:housenumber"),
                tags.get("addr:street"),
                tags.get("addr:city"),
                tags.get("addr:state"),
                tags.get("addr:country"),
            ]
            address = ", ".join(filter(None, address_parts))
            distance_km = round(_haversine(lat, lon, lat_p, lon_p), 2)

            places.append({
                "name": name,
                "address": address,
                "lat": lat_p,
                "lon": lon_p,
                "type": tags.get("amenity", amenity),
                "distance_km": distance_km,
            })

        await self._set_cached_response(cache_key, places)
        return places
