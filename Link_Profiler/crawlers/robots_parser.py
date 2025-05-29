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
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch_robots_txt(self, domain: str) -> Optional[RobotFileParser]:
        """
        Fetches and parses the robots.txt file for a given domain.
        """
        if domain not in self._fetch_lock:
            self._fetch_lock[domain] = asyncio.Lock()

        async with self._fetch_lock[domain]:
            if domain in self._parsers:
                return self._parsers[domain] # Already fetched and parsed

            robots_txt_url = urljoin(f"http://{domain}", "/robots.txt")
            
            if self._session is None:
                logger.warning(f"aiohttp session not active for fetching robots.txt for {domain}. Please use RobotsParser within an 'async with' block.")
                # Fallback for cases where it's not used as context manager, but less efficient
                async with aiohttp.ClientSession() as temp_session:
                    return await self._fetch_robots_txt_with_session(domain, robots_txt_url, temp_session)
            else:
                return await self._fetch_robots_txt_with_session(domain, robots_txt_url, self._session)

    async def _fetch_robots_txt_with_session(self, domain: str, robots_txt_url: str, session: aiohttp.ClientSession) -> Optional[RobotFileParser]:
        parser = RobotFileParser()
        parser.set_url(robots_txt_url)

        try:
            async with session.get(robots_txt_url, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    parser.parse(content.splitlines())
                    self._parsers[domain] = parser
                    logger.info(f"Successfully fetched and parsed robots.txt for {domain}")
                    return parser
                elif response.status == 404:
                    logger.info(f"No robots.txt found for {domain} (404 Not Found). Assuming full crawl allowed.")
                    # If no robots.txt, assume everything is allowed
                    self._parsers[domain] = parser # Store empty parser
                    return parser
                else:
                    logger.warning(f"Failed to fetch robots.txt for {domain}. Status: {response.status}")
        except aiohttp.ClientError as e:
            logger.warning(f"Client error fetching robots.txt for {domain}: {e}")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching robots.txt for {domain}.")
        except Exception as e:
            logger.error(f"Unexpected error fetching robots.txt for {domain}: {e}")
        
        # If fetching fails, assume everything is allowed to avoid blocking
        # but log the failure.
        self._parsers[domain] = parser # Store empty parser
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
        if parser:
            can_crawl = parser.can_fetch(user_agent, url)
            if not can_crawl:
                logger.debug(f"Blocked by robots.txt: {url} for {user_agent}")
            return can_crawl
        
        # If parser could not be fetched or created, default to allowing
        return True
