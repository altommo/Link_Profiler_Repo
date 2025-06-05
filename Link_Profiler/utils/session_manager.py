"""
Smart Session Manager - Provides a centralized, optimized aiohttp ClientSession
for all HTTP requests within the crawler system.
Handles adaptive connection pooling, connection health checks, and automatic retries.
File: Link_Profiler/utils/session_manager.py
"""

import asyncio
import aiohttp
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from collections import deque
from datetime import datetime, timedelta
import random

# Removed direct import of config_loader, will use global instance
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.proxy_manager import proxy_manager, ProxyDetails # Import ProxyDetails

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages a single, optimized aiohttp.ClientSession for all HTTP requests.
    Implements adaptive connection pooling, connection health checks, and retries.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger(__name__ + ".SessionManager")

        # Import config_loader here to avoid circular dependency at module level
        from Link_Profiler.config.config_loader import config_loader 

        # Configuration from config_loader
        self.max_connections = config_loader.get("connection_optimization.max_connections", 200)
        self.max_connections_per_host = config_loader.get("connection_optimization.max_connections_per_host", 20)
        self.timeout_total = config_loader.get("connection_optimization.timeout_total", 30)
        self.timeout_connect = config_loader.get("connection_optimization.timeout_connect", 10)
        self.timeout_sock_read = config_loader.get("connection_optimization.timeout_sock_read", 30)
        self.retry_attempts = config_loader.get("connection_optimization.retry_attempts", 3)
        self.retry_delay_base = config_loader.get("connection_optimization.retry_delay_base", 0.5)
        self.enable_health_checks = config_loader.get("connection_optimization.connection_health_check", True)
        self.use_proxies = config_loader.get("proxy.use_proxies", False)
        self.user_agent_rotation = config_loader.get("anti_detection.user_agent_rotation", False)
        self.request_header_randomization = config_loader.get("anti_detection.request_header_randomization", False)
        self.human_like_delays = config_loader.get("anti_detection.human_like_delays", False)
        self.random_delay_range = config_loader.get("anti_detection.random_delay_range", [0.1, 0.5])

        # Connection pool monitoring (for adaptive sizing, not fully implemented yet)
        self._connection_pool_stats: Dict[str, Any] = {} # Placeholder for per-host stats

    async def __aenter__(self):
        """Initializes the aiohttp ClientSession."""
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
                verify_ssl=True,
            )
            timeout = aiohttp.ClientTimeout(
                total=self.timeout_total,
                connect=self.timeout_connect,
                sock_read=self.timeout_sock_read
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self._get_base_headers()
            )
            self.logger.info("aiohttp ClientSession initialized.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the aiohttp ClientSession."""
        if self.session and not self.session.closed:
            self.logger.info("Closing aiohttp ClientSession.")
            await self.session.close()
            self.session = None

    def _get_base_headers(self) -> Dict[str, str]:
        """Returns base headers for the session, potentially with rotation."""
        # Import config_loader here to avoid circular dependency at module level
        from Link_Profiler.config.config_loader import config_loader 

        if self.request_header_randomization:
            return user_agent_manager.get_random_headers()
        elif self.user_agent_rotation:
            return {"User-Agent": user_agent_manager.rotate_user_agent()}
        else:
            return {"User-Agent": config_loader.get("crawler.user_agent", "LinkProfilerBot/1.0")}

    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """
        Performs an HTTP request with built-in retry logic, proxy rotation,
        and adaptive delays.
        """
        if not self.session or self.session.closed:
            raise RuntimeError("SessionManager is not active. Call __aenter__ first.")

        headers = kwargs.pop("headers", {})
        proxy_details: Optional[ProxyDetails] = None
        
        for attempt in range(self.retry_attempts):
            try:
                # Apply human-like delays
                if self.human_like_delays:
                    delay = random.uniform(*self.random_delay_range)
                    await asyncio.sleep(delay)

                # Get proxy if enabled
                if self.use_proxies:
                    proxy_details = proxy_manager.get_next_proxy()
                    if proxy_details:
                        kwargs["proxy"] = proxy_details.url
                        self.logger.debug(f"Using proxy {proxy_details.url} for {url} (Attempt {attempt + 1})")
                    else:
                        self.logger.warning(f"No available proxies for {url}. Proceeding without proxy.")

                # Update headers for each request (e.g., for UA rotation)
                request_headers = self._get_base_headers()
                request_headers.update(headers) # Allow kwargs headers to override base

                async with self.session.request(method, url, headers=request_headers, **kwargs) as response:
                    # Check for connection health (e.g., if response indicates a bad proxy)
                    if self.enable_health_checks and response.status in [403, 429, 503, 504]:
                        if proxy_details:
                            proxy_manager.mark_proxy_bad(proxy_details.url, f"Status {response.status}")
                        self.logger.warning(f"Request to {url} failed with status {response.status}. Retrying (attempt {attempt + 1}).")
                        if attempt < self.retry_attempts - 1:
                            await asyncio.sleep(self.retry_delay_base * (2 ** attempt))
                            continue # Retry with potentially new proxy
                        else:
                            raise aiohttp.ClientError(f"Final attempt failed for {url} with status {response.status}")
                    
                    if proxy_details:
                        proxy_manager.mark_proxy_good(proxy_details.url)
                    return response

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if proxy_details:
                    proxy_manager.mark_proxy_bad(proxy_details.url, str(e))
                self.logger.warning(f"Request to {url} failed (Attempt {attempt + 1}): {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay_base * (2 ** attempt))
                else:
                    self.logger.error(f"All {self.retry_attempts} attempts failed for {url}.")
                    raise # Re-raise exception after all retries
            except Exception as e:
                self.logger.error(f"Unexpected error during request to {url}: {e}", exc_info=True)
                raise # Re-raise unexpected errors immediately

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Convenience method for GET requests."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Convenience method for POST requests."""
        return await self.request("POST", url, **kwargs)

# Create a singleton instance
session_manager = SessionManager()
