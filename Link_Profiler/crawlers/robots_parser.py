"""
Robots Parser - Fetches and parses robots.txt files.
File: Link_Profiler/crawlers/robots_parser.py
"""

import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
import aiohttp
from datetime import datetime, timedelta
import asyncio # Import asyncio for asyncio.Lock

from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.config.config_loader import config_loader

# Conditional import for robotparser (Python 3.8+)
try:
    from urllib.robotparser import RobotFileParser
except ImportError:
    # Fallback for older Python versions or if not available
    class RobotFileParser:
        def __init__(self, url=''):
            self.url = url
            self.disallow_paths = []
            self.allow_paths = []
        def set_url(self, url): self.url = url
        def read(self): pass # No-op for dummy
        def can_fetch(self, useragent, url): return True # Always allow for dummy
        def parse(self, lines):
            for line in lines:
                line = line.strip()
                if line.startswith('Disallow:'):
                    self.disallow_paths.append(line[len('Disallow:'):].strip())
                elif line.startswith('Allow:'):
                    self.allow_paths.append(line[len('Allow:'):].strip())
        def crawl_delay(self, useragent): return None
        def request_rate(self, useragent): return None
    logger.warning("urllib.robotparser.RobotFileParser not available. Using a dummy implementation. Consider upgrading Python.")


logger = logging.getLogger(__name__) # This logger is for the module, not the class instance

class RobotsParser:
    """
    Fetches and parses robots.txt files for given domains.
    Caches parsed robots.txt content to avoid re-fetching.
    """
    def __init__(self, session_manager: SessionManager):
        self.logger = logging.getLogger(__name__ + ".RobotsParser")
        self.session_manager = session_manager
        self.parsers: Dict[str, RobotFileParser] = {} # Cache of RobotFileParser instances
        self.cache_expiry: timedelta = timedelta(hours=config_loader.get("crawler.robots_txt_cache_hours", 24))
        self.last_fetch_time: Dict[str, datetime] = {}
        self._fetch_lock: Dict[str, asyncio.Lock] = {} # To prevent multiple fetches for the same domain

    async def __aenter__(self):
        """No specific async setup needed for this class."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class."""
        pass

    async def _fetch_robots_txt(self, domain: str) -> Optional[str]:
        """Fetches the robots.txt content for a given domain."""
        robots_txt_url = urljoin(f"http://{domain}", "/robots.txt")
        try:
            self.logger.debug(f"Fetching robots.txt from: {robots_txt_url}")
            async with self.session_manager.get(robots_txt_url, timeout=10) as response:
                response.raise_for_status() # Raise an exception for 4xx/5xx responses
                return await response.text()
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                self.logger.info(f"robots.txt not found for {domain} (404). Assuming full access.")
                return "" # Return empty string to indicate no robots.txt
            self.logger.warning(f"Error fetching robots.txt for {domain}: {e.status} - {e.message}")
            return None
        except aiohttp.ClientError as e:
            self.logger.warning(f"Network error fetching robots.txt for {domain}: {e}")
            return None
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout fetching robots.txt for {domain}.")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching robots.txt for {domain}: {e}", exc_info=True)
            return None

    async def _get_parser(self, url: str) -> RobotFileParser:
        """
        Gets or fetches and parses the RobotFileParser for a given URL's domain.
        Caches the parser for future use.
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        if domain not in self._fetch_lock:
            self._fetch_lock[domain] = asyncio.Lock()

        async with self._fetch_lock[domain]:
            parser = self.parsers.get(domain)
            last_fetch = self.last_fetch_time.get(domain)

            # Check if parser exists and is not expired
            if parser and last_fetch and (datetime.now() - last_fetch) < self.cache_expiry:
                self.logger.debug(f"Using cached robots.txt for {domain}.")
                return parser
            
            self.logger.info(f"Fetching/re-fetching robots.txt for {domain}.")
            robots_txt_content = await self._fetch_robots_txt(domain)
            
            new_parser = RobotFileParser()
            new_parser.set_url(urljoin(f"http://{domain}", "/robots.txt"))
            
            if robots_txt_content is not None: # If fetch was successful (even if 404)
                new_parser.parse(robots_txt_content.splitlines())
                self.parsers[domain] = new_parser
                self.last_fetch_time[domain] = datetime.now()
                self.logger.info(f"Parsed robots.txt for {domain}.")
            else: # If fetch failed, assume full access for this session
                self.logger.warning(f"Failed to get robots.txt for {domain}. Assuming full access for this session.")
                # Store a dummy parser that always allows, but mark its fetch time
                new_parser.parse(["User-agent: *", "Allow: /"]) # Explicitly make it permissive
                self.parsers[domain] = new_parser 
                self.last_fetch_time[domain] = datetime.now() # Still cache the fetch attempt time

            return self.parsers[domain]

    async def can_fetch(self, url: str, user_agent: str) -> bool:
        """
        Checks if the given user agent is allowed to fetch the URL based on robots.txt.
        """
        parser = await self._get_parser(url)
        allowed = parser.can_fetch(user_agent, url)
        if not allowed:
            self.logger.debug(f"robots.txt disallows {user_agent} from fetching {url}.")
        return allowed

    async def get_crawl_delay(self, url: str, user_agent: str) -> Optional[float]:
        """
        Returns the crawl-delay specified in robots.txt for the given user agent.
        """
        parser = await self._get_parser(url)
        delay = parser.crawl_delay(user_agent)
        if delay is not None:
            self.logger.debug(f"robots.txt specifies crawl-delay of {delay}s for {user_agent} on {url}.")
        return delay

    async def get_sitemap_urls(self, url: str) -> List[str]:
        """
        Extracts sitemap URLs from robots.txt.
        """
        parser = await self._get_parser(url)
        # RobotFileParser doesn't directly expose sitemaps, need to re-parse content
        # Or, extend RobotFileParser to store sitemaps during parse.
        # For now, re-fetch and parse manually for sitemaps.
        
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        robots_txt_content = await self._fetch_robots_txt(domain)
        
        sitemap_urls = []
        if robots_txt_content:
            for line in robots_txt_content.splitlines():
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line[len('sitemap:'):].strip()
                    sitemap_urls.append(sitemap_url)
        
        if sitemap_urls:
            self.logger.debug(f"Found {len(sitemap_urls)} sitemap URLs in robots.txt for {domain}.")
        return sitemap_urls
