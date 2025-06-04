import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import random 

from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.config.config_loader import config_loader

logger = logging.getLogger(__name__) # This logger is for the module, not the class instance

class RobotsParser:
    """
    Fetches and parses robots.txt files for given domains.
    Caches parsed robots.txt content to avoid re-fetching.
    """
    def __init__(self):
        self._parsers: Dict[str, RobotFileParser] = {}
        self._cache_timestamps: Dict[str, datetime] = {} # Separate cache for timestamps
        self._fetch_lock: Dict[str, asyncio.Lock] = {} # To prevent multiple fetches for the same domain
        self._session: Optional[aiohttp.ClientSession] = None
        self.cache_expiry: timedelta = timedelta(hours=1) # Cache robots.txt for 1 hour
        self.logger = logging.getLogger(__name__ + ".RobotsParser") # Initialize logger for the instance

    async def __aenter__(self):
        """Async context manager entry."""
        if self._session is None or self._session.closed:
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("anti_detection.user_agent_rotation", False): # Use anti_detection config for rotation
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()
            # If neither is enabled, aiohttp uses its default user agent.

            self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch_and_parse_robots_txt(self, domain: str) -> RobotFileParser:
        """
        Fetches robots.txt content for a given domain and returns a configured RobotFileParser.
        Handles caching and network errors.
        """
        if domain not in self._fetch_lock:
            self._fetch_lock[domain] = asyncio.Lock()

        async with self._fetch_lock[domain]:
            # Check cache first (inside lock)
            if domain in self._parsers and (datetime.now() - self._cache_timestamps.get(domain, datetime.min)) < self.cache_expiry:
                self.logger.debug(f"Using cached robots.txt parser for {domain}")
                return self._parsers[domain]

            robots_txt_url = urljoin(f"http://{domain}", "/robots.txt")
            parser = RobotFileParser()
            parser.set_url(robots_txt_url) # Set URL for the parser

            session_to_use = self._session
            if session_to_use is None:
                self.logger.warning(f"RobotsParser session not active for {domain}. Creating temporary session.")
                headers = {}
                if config_loader.get("anti_detection.request_header_randomization", False):
                    headers.update(user_agent_manager.get_random_headers())
                elif config_loader.get("anti_detection.user_agent_rotation", False):
                    headers['User-Agent'] = user_agent_manager.get_random_user_agent()
                session_to_use = aiohttp.ClientSession(headers=headers)

            # Add human-like delays if configured
            if config_loader.get("anti_detection.human_like_delays", False) and config_loader.get("anti_detection.random_delay_range"):
                delay = random.uniform(*config_loader["anti_detection"]["random_delay_range"])
                await asyncio.sleep(delay)
            elif config_loader.get("anti_detection.human_like_delays", False):
                await asyncio.sleep(random.uniform(0.1, 0.5))

            try:
                async with session_to_use.get(robots_txt_url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        parser.parse(content.splitlines())
                        self.logger.info(f"Successfully fetched and parsed robots.txt for {domain}")
                    elif response.status == 404:
                        self.logger.info(f"No robots.txt found for {domain} (404 Not Found). Assuming full crawl allowed.")
                        # CRITICAL FIX: Explicitly parse a permissive robots.txt for 404
                        parser.parse(["User-agent: *", "Allow: /"])
                    else:
                        self.logger.warning(f"Failed to fetch robots.txt for {domain}. Status: {response.status}. Defaulting to allow.")
                        # CRITICAL FIX: Explicitly parse a permissive robots.txt for other errors
                        parser.parse(["User-agent: *", "Allow: /"])
            except aiohttp.ClientError as e:
                self.logger.warning(f"Network/Client error fetching robots.txt for {domain}: {e}. Defaulting to allow.")
                # CRITICAL FIX: Explicitly parse a permissive robots.txt on network errors
                parser.parse(["User-agent: *", "Allow: /"])
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout fetching robots.txt for {domain}. Defaulting to allow.")
                # CRITICAL FIX: Explicitly parse a permissive robots.txt on timeout
                parser.parse(["User-agent: *", "Allow: /"])
            except Exception as e:
                self.logger.error(f"Unexpected error fetching robots.txt for {domain}: {e}. Defaulting to allow.")
                # CRITICAL FIX: Explicitly parse a permissive robots.txt on unexpected errors
                parser.parse(["User-agent: *", "Allow: /"])
            finally:
                if session_to_use is not self._session and not session_to_use.closed:
                    await session_to_use.close()

            self._parsers[domain] = parser
            self._cache_timestamps[domain] = datetime.now()
            self.logger.debug(f"Parsed robots.txt for {domain} and cached.")
            return parser

    async def can_fetch(self, url: str, user_agent: str) -> bool:
        """
        Checks if the given URL can be fetched by the specified user agent
        according to the domain's robots.txt.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        if not domain:
            self.logger.warning(f"Invalid URL for robots.txt check: {url}. Allowing by default.")
            return True

        # Ensure the parser for this domain is fetched and cached
        parser = await self._fetch_and_parse_robots_txt(domain)
        
        # Now, use the obtained parser to check if the URL is allowed
        can_crawl = parser.can_fetch(user_agent, url)
        
        if not can_crawl:
            self.logger.debug(f"Blocked by robots.txt: {url} for user agent {user_agent}")
        
        return can_crawl
