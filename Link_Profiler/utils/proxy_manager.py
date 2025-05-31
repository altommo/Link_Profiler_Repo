"""
Proxy Manager - Provides a mechanism for rotating and managing proxies.
File: Link_Profiler/utils/proxy_manager.py
"""

import random
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field # Import dataclass and field

@dataclass
class ProxyDetails:
    url: str
    region: str = "global"
    # Optional: add more fields for health tracking
    last_used: Optional[datetime] = None
    failure_count: int = 0

class ProxyManager:
    """
    Manages a pool of proxies, providing rotation and temporary blacklisting
    of proxies that fail. Supports geographic distribution.
    Implemented as a singleton.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProxyManager, cls).__new__(cls)
            cls._instance._initialized = False # Flag to ensure __init__ runs only once
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # Stores proxies grouped by region: { "region_name": deque[ProxyDetails] }
        self._regional_proxies: Dict[str, deque[ProxyDetails]] = {}
        # Stores proxies that are temporarily blacklisted: { "proxy_url": datetime_can_retry }
        self._bad_proxies_until: Dict[str, datetime] = {}
        self.logger = logging.getLogger(__name__ + ".ProxyManager")
        self.proxy_retry_delay_seconds = 300 # Default 5 minutes

    def load_proxies(self, proxy_list_raw: List[Dict[str, str]], proxy_retry_delay_seconds: int = 300):
        """
        Loads proxies into the manager.
        proxy_list_raw: List of dictionaries, e.g., [{"url": "http://ip:port", "region": "us-east"}]
        """
        self._regional_proxies.clear() # Clear existing proxies
        self._bad_proxies_until = {} # Clear blacklist on reload

        for proxy_data in proxy_list_raw:
            proxy_url = proxy_data.get("url")
            proxy_region = proxy_data.get("region", "global")
            if not proxy_url:
                self.logger.warning(f"Skipping proxy entry with missing 'url': {proxy_data}")
                continue
            
            proxy_details = ProxyDetails(url=proxy_url, region=proxy_region)
            if proxy_region not in self._regional_proxies:
                self._regional_proxies[proxy_region] = deque()
            self._regional_proxies[proxy_region].append(proxy_details)
        
        total_loaded = sum(len(d) for d in self._regional_proxies.values())
        self.proxy_retry_delay_seconds = proxy_retry_delay_seconds
        self.logger.info(f"Loaded {total_loaded} proxies across {len(self._regional_proxies)} regions. Retry delay: {proxy_retry_delay_seconds}s.")

    def get_next_proxy(self, desired_region: Optional[str] = None) -> Optional[str]:
        """
        Returns the next available proxy URL.
        Prioritizes the desired_region if specified and available.
        """
        candidate_regions = []
        if desired_region and desired_region in self._regional_proxies:
            candidate_regions.append(desired_region)
        
        # Add all other regions for fallback, shuffled to ensure fair distribution
        other_regions = list(self._regional_proxies.keys())
        if desired_region and desired_region in other_regions: # Ensure desired_region is not duplicated if it was already added
            other_regions.remove(desired_region)
        random.shuffle(other_regions)
        candidate_regions.extend(other_regions)

        for region in candidate_regions:
            if region not in self._regional_proxies or not self._regional_proxies[region]:
                continue # Skip empty regions

            num_proxies_in_region = len(self._regional_proxies[region])
            for _ in range(num_proxies_in_region): # Iterate through proxies in this region once
                proxy_details = self._regional_proxies[region][0] # Get the current head
                self._regional_proxies[region].rotate(-1) # Rotate for next time

                if proxy_details.url in self._bad_proxies_until:
                    if datetime.now() < self._bad_proxies_until[proxy_details.url]:
                        self.logger.debug(f"Skipping bad proxy {proxy_details.url} (Region: {region}). Will retry after {self._bad_proxies_until[proxy_details.url]}.")
                        continue # This proxy is still bad
                    else:
                        # Proxy is no longer bad, remove from blacklist
                        del self._bad_proxies_until[proxy_details.url]
                        self.logger.info(f"Rehabilitated proxy: {proxy_details.url} (Region: {region}).")
                
                proxy_details.last_used = datetime.now()
                self.logger.debug(f"Using proxy: {proxy_details.url} (Region: {region})")
                return proxy_details.url
        
        self.logger.warning("No available proxies found across all regions.")
        return None # All proxies are currently bad or no proxies loaded

    def mark_proxy_bad(self, proxy_url: str, reason: str = "unknown"):
        """
        Marks a proxy URL as bad, preventing its use for a specified duration.
        """
        if proxy_url:
            retry_time = datetime.now() + timedelta(seconds=self.proxy_retry_delay_seconds)
            self._bad_proxies_until[proxy_url] = retry_time
            self.logger.warning(f"Marked proxy {proxy_url} as bad until {retry_time} due to: {reason}.")

# Create a singleton instance
proxy_manager = ProxyManager()
