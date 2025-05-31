"""
Proxy Manager - Provides a mechanism for rotating and managing proxies.
File: Link_Profiler/utils/proxy_manager.py
"""

import random
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque

class ProxyManager:
    """
    Manages a pool of proxies, providing rotation and temporary blacklisting
    of proxies that fail. Implemented as a singleton.
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

        self._proxies: deque[str] = deque() # Use deque for efficient rotation
        self._bad_proxies_until: Dict[str, datetime] = {} # proxy_string -> datetime when it can be retried
        self._current_index = 0 # For simple round-robin if deque is not used
        self.logger = logging.getLogger(__name__ + ".ProxyManager")
        self.proxy_retry_delay_seconds = 300 # Default 5 minutes

    def load_proxies(self, proxy_list: List[str], proxy_retry_delay_seconds: int = 300):
        """
        Loads proxies into the manager. Can be called multiple times to refresh.
        """
        self._proxies = deque(proxy_list)
        self.proxy_retry_delay_seconds = proxy_retry_delay_seconds
        self.logger.info(f"Loaded {len(proxy_list)} proxies. Retry delay: {proxy_retry_delay_seconds}s.")
        # Clear old bad proxy states if new list is loaded
        self._bad_proxies_until = {p: t for p, t in self._bad_proxies_until.items() if p in self._proxies}


    def get_next_proxy(self) -> Optional[str]:
        """
        Returns the next available proxy in a rotating fashion.
        Skips proxies that are currently marked as bad.
        """
        if not self._proxies:
            self.logger.warning("No proxies loaded in ProxyManager.")
            return None

        num_proxies = len(self._proxies)
        for _ in range(num_proxies): # Iterate through all proxies once
            current_proxy = self._proxies[0] # Get the current head of the deque
            self._proxies.rotate(-1) # Rotate the deque to move current_proxy to the end

            if current_proxy in self._bad_proxies_until:
                if datetime.now() < self._bad_proxies_until[current_proxy]:
                    self.logger.debug(f"Skipping bad proxy {current_proxy}. Will retry after {self._bad_proxies_until[current_proxy]}.")
                    continue # This proxy is still bad, try the next one
                else:
                    # Proxy is no longer bad, remove from blacklist
                    del self._bad_proxies_until[current_proxy]
                    self.logger.info(f"Rehabilitated proxy: {current_proxy}.")
            
            self.logger.debug(f"Using proxy: {current_proxy}")
            return current_proxy
        
        self.logger.warning("All proxies are currently marked as bad or unavailable.")
        return None # All proxies are currently bad

    def mark_proxy_bad(self, proxy: str, reason: str = "unknown"):
        """
        Marks a proxy as bad, preventing its use for a specified duration.
        """
        if proxy:
            retry_time = datetime.now() + timedelta(seconds=self.proxy_retry_delay_seconds)
            self._bad_proxies_until[proxy] = retry_time
            self.logger.warning(f"Marked proxy {proxy} as bad until {retry_time} due to: {reason}.")

# Create a singleton instance
proxy_manager = ProxyManager()
