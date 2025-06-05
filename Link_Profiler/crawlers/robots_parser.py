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
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager

logger = logging.getLogger(__name__) # This logger is for the module, not the class instance

class RobotsParser:
    """
    Fetches and parses robots.txt files for given domains.
    Caches parsed robots.txt content to avoid re-fetching.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None): # New: Accept SessionManager
        self._parsers: Dict[str, RobotFileParser] = {}
        self._cache_timestamps: Dict[str, datetime] = {} # Separate cache for timestamps
        self._fetch_lock: Dict[str, asyncio.Lock] = {} # To prevent multiple fetches for the same domain
        self.session_manager = session_manager # Use the injected session manager
        if self.session_manager is None:
            # Fallback to a local session manager if none is provided (e.g., for testing)
            from Link_Profiler.utils.session_manager import SessionManager as LocalSessionManager # Avoid name collision
            self.session_manager = LocalSessionManager()
            logger.warning("No SessionManager provided to RobotsParser. Falling back to local SessionManager.")

        self.cache_expiry: timedelta = timedelta(hours=1) # Cache robots.txt for 1 hour
        self.logger = logging.getLogger(__name__ + ".RobotsParser") # Initialize logger for the instance

    async def __aenter__(self):
        """Async context manager entry."""
        # The session manager handles its own __aenter__ and __aexit__
        # We just need to ensure it's entered before use.
        await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # The session manager handles its own __aexit__
        await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

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

            try:
                # Use the session manager for fetching
                async with await self.session_manager.get(robots_txt_url) as response:
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
