"""
Robots Parser - Handles robots.txt fetching and parsing.
File: Link_Profiler/crawlers/robots_parser.py
"""

import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import logging
from typing import Dict, Optional
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
        """Async context manager entry for client session."""
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
        """Async context manager exit for client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch_robots_txt(self, domain: str) -> Optional[RobotFileParser]:
        """
        Fetches and parses the robots.txt file for a given domain.
        Returns the parser if successful, or an empty parser if not found/failed.
        """
        if domain not in self._fetch_lock:
            self._fetch_lock[domain] = asyncio.Lock()

        async with self._fetch_lock[domain]:
            if domain in self._parsers:
                return self._parsers[domain] # Already fetched and parsed

            robots_txt_url = urljoin(f"http://{domain}", "/robots.txt")
            
            # Use the session managed by __aenter__/__aexit__
            session_to_use = self._session
            if session_to_use is None:
                # This case should ideally not happen if used within WebCrawler's context
                logger.warning(f"RobotsParser session not active for {domain}. Creating temporary session.")
                
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
                        logger.info(f"Successfully fetched and parsed robots.txt for {domain}")
                        return parser
                    elif response.status == 404:
                        logger.info(f"No robots.txt found for {domain} (404 Not Found). Assuming full crawl allowed.")
                        # If no robots.txt, assume everything is allowed. Store an empty parser.
                        self._parsers[domain] = parser 
                        return parser
                    else:
                        logger.warning(f"Failed to fetch robots.txt for {domain}. Status: {response.status}")
            except aiohttp.ClientError as e:
                logger.warning(f"Client error fetching robots.txt for {domain}: {e}")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching robots.txt for {domain}.")
            except Exception as e:
                logger.error(f"Unexpected error fetching robots.txt for {domain}: {e}")
            finally:
                if session_to_use is not self._session and not session_to_use.closed:
                    await session_to_use.close() # Close temporary session

            # If fetching fails for any reason, assume everything is allowed by default
            # and store an empty parser to avoid re-attempting for this domain.
            self._parsers[domain] = parser 
            return parser

    async def can_fetch(self, url: str, user_agent: str) -> bool:
        """
        Checks if the given URL can be fetched by the specified user agent
        according to the domain's robots.txt.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        if not domain:
            logger.warning(f"Invalid URL for robots.txt check: {url}")
            return True # Cannot determine, so allow

        parser = await self._fetch_robots_txt(domain)
        
        # If parser is None (shouldn't happen with current _fetch_robots_txt logic)
        # or if fetching failed and an empty parser was returned, it means
        # we couldn't get rules, so we default to allowing.
        if parser is None: # This case should be covered by _fetch_robots_txt returning a parser
            return True
        
        # Check if the parser explicitly disallows fetching
        can_crawl = parser.can_fetch(user_agent, url)
        if not can_crawl:
            logger.debug(f"Blocked by robots.txt: {url} for {user_agent}")
        return can_crawl
