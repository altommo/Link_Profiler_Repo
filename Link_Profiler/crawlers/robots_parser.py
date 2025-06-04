import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import random # New: Import random for human-like delays

from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager
from Link_Profiler.config.config_loader import config_loader # New: Import config_loader

logger = logging.getLogger(__name__)

class RobotsParser:
    """
    Fetches and parses robots.txt files for given domains.
    Caches parsed robots.txt content to avoid re-fetching.
    """
    def __init__(self):
        self._parsers: Dict[str, RobotFileParser] = {}
        self._fetch_lock: Dict[str, asyncio.Lock] = {} # To prevent multiple fetches for the same domain
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        if self._session is None or self._session.closed:
            headers = {}
            if config_loader.get("anti_detection.request_header_randomization", False):
                headers.update(user_agent_manager.get_random_headers())
            elif config_loader.get("crawler.user_agent_rotation", False):
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()
            # If neither is enabled, aiohttp uses its default user agent.

            self._session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch_robots_txt(self, domain: str) -> Optional[str]:
        """
        Fetches and parses the robots.txt file for a given domain.
        Returns the parser if successful, or an empty parser if not found/failed.
        """
        if domain not in self._fetch_lock:
            self._fetch_lock[domain] = asyncio.Lock()

        async with self._fetch_lock[domain]:
            # Check cache first (moved inside lock to prevent race conditions on cache check)
            if domain in self._parsers and (datetime.now() - self._parsers[domain].mtime) < timedelta(hours=1): # Using mtime for cache expiry
                self.logger.debug(f"Using cached robots.txt for {domain}")
                return None # Content already parsed and cached

            robots_txt_url = urljoin(f"http://{domain}", "/robots.txt")
            
            session_to_use = self._session
            if session_to_use is None:
                # This case should ideally not happen if used within WebCrawler's context
                self.logger.warning(f"RobotsParser session not active for {domain}. Creating temporary session.")
                
                headers = {}
                if config_loader.get("anti_detection.request_header_randomization", False):
                    headers.update(user_agent_manager.get_random_headers())
                elif config_loader.get("crawler.user_agent_rotation", False):
                    headers['User-Agent'] = user_agent_manager.get_random_user_agent()

                session_to_use = aiohttp.ClientSession(headers=headers) # Create a temporary session if not active

            parser = RobotFileParser()
            parser.set_url(robots_txt_url)

            # Add human-like delays if configured
            if config_loader.get("anti_detection.human_like_delays", False):
                await asyncio.sleep(random.uniform(0.1, 0.5))

            try:
                async with session_to_use.get(robots_txt_url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        parser.parse(content.splitlines())
                        self._parsers[domain] = parser
                        self._parsers[domain].mtime = datetime.now() # Update mtime for cache
                        self.logger.info(f"Successfully fetched and parsed robots.txt for {domain}")
                        return content # Return content for parsing
                    elif response.status == 404:
                        self.logger.info(f"No robots.txt found for {domain} (404 Not Found). Assuming full crawl allowed.")
                        # If no robots.txt, assume everything is allowed. Store an empty parser.
                        self._parsers[domain] = parser 
                        self._parsers[domain].mtime = datetime.now() # Update mtime for cache
                        return "" # Empty string indicates no robots.txt, which means full crawl allowed
                    else:
                        self.logger.warning(f"Failed to fetch robots.txt for {domain}. Status: {response.status}")
            except aiohttp.ClientError as e:
                self.logger.warning(f"Client error fetching robots.txt for {domain}: {e}")
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout fetching robots.txt for {domain}.")
            except Exception as e:
                self.logger.error(f"Unexpected error fetching robots.txt for {domain}: {e}")
            finally:
                if session_to_use is not self._session and not session_to_use.closed:
                    await session_to_use.close() # Close temporary session

            # If fetching fails for any reason (e.g., network error, timeout),
            # we should still store an empty parser to avoid re-attempting for this domain
            # and default to allowing the crawl.
            self._parsers[domain] = parser 
            self._parsers[domain].mtime = datetime.now() # Update mtime for cache
            return None # Indicate failure to fetch content, but parser is set to allow by default

    async def can_fetch(self, url: str, user_agent: str) -> bool:
        """
        Checks if the given URL can be fetched by the specified user agent
        according to the domain's robots.txt.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        if not domain:
            self.logger.warning(f"Invalid URL for robots.txt check: {url}")
            return True # Cannot determine, so allow

        # Ensure the parser for this domain is fetched and cached
        await self._fetch_robots_txt(domain) # This call ensures self._parsers[domain] is populated

        # Now, safely access the parser from the cache
        parser = self._parsers.get(domain)
        
        if parser is None:
            # This case should ideally not happen if _fetch_robots_txt always sets a parser,
            # but as a fallback, if parser is somehow missing, allow.
            self.logger.warning(f"Robots.txt parser not found for {domain} after fetch attempt. Defaulting to allow.")
            return True
        
        # Check if the parser explicitly disallows fetching
        can_crawl = parser.can_fetch(user_agent, url)
        if not can_crawl:
            self.logger.debug(f"Blocked by robots.txt: {url} for {user_agent}")
        return can_crawl
