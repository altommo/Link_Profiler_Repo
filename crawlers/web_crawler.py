"""
Web Crawler - Core crawling engine for link discovery
File: crawlers/web_crawler.py
"""

import asyncio
import aiohttp
import time
from typing import List, Dict, Set, Optional, AsyncGenerator, Tuple
from urllib.parse import urljoin, urlparse, urlencode
from urllib.robotparser import RobotFileParser
import logging
from dataclasses import dataclass
import re
from datetime import datetime, timedelta

from ..core.models import (
    URL, Backlink, CrawlConfig, CrawlStatus, LinkType, 
    CrawlJob, ContentType
)
from .link_extractor import LinkExtractor
from .content_parser import ContentParser
from .robots_parser import RobotsParser


class CrawlerError(Exception):
    """Custom exception for crawler errors"""
    pass


class RateLimiter:
    """Rate limiter to respect website policies"""
    
    def __init__(self, requests_per_second: float = 1.0):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = {}
    
    async def wait_if_needed(self, domain: str) -> None:
        """Wait if needed to respect rate limits"""
        now = time.time()
        last_time = self.last_request_time.get(domain, 0)
        time_since_last = now - last_time
        
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time[domain] = time.time()


@dataclass
class CrawlResult:
    """Result of a single page crawl"""
    url: str
    status_code: int
    content: str = ""
    headers: Dict[str, str] = None
    links_found: List[Backlink] = None
    redirect_url: Optional[str] = None
    error_message: Optional[str] = None
    crawl_time_ms: int = 0
    content_type: str = "text/html"
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.links_found is None:
            self.links_found = []


class WebCrawler:
    """Main web crawler class"""
    
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.rate_limiter = RateLimiter(1.0 / config.delay_seconds)
        self.robots_parser = RobotsParser()
        self.link_extractor = LinkExtractor()
        self.content_parser = ContentParser() 
        self.session: Optional[aiohttp.ClientSession] = None
        self.crawled_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.logger = logging.getLogger(__name__)
        
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(
            limit=10,  # Total connection pool size
            limit_per_host=5,  # Connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout_seconds,
            connect=10
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': self.config.user_agent,
                **self.config.custom_headers
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def crawl_url(self, url: str) -> CrawlResult:
        """Crawl a single URL and extract links"""
        start_time = time.time()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Check if domain is allowed
        if not self.config.is_domain_allowed(domain):
            return CrawlResult(
                url=url,
                status_code=403,
                error_message="Domain not allowed"
            )
        
        # Check robots.txt if enabled
        if self.config.respect_robots_txt:
            can_crawl = await self.robots_parser.can_fetch(url, self.config.user_agent)
            if not can_crawl:
                return CrawlResult(
                    url=url,
                    status_code=403,
                    error_message="Blocked by robots.txt"
                )
        
        # Rate limiting
        await self.rate_limiter.wait_if_needed(domain)
        
        try:
            async with self.session.get(url, allow_redirects=self.config.follow_redirects) as response:
                crawl_time_ms = int((time.time() - start_time) * 1000)
                
                # Get content type
                content_type = response.headers.get('content-type', '').lower()
                
                # Read content based on type
                if 'text/html' in content_type:
                    content = await response.text()
                    links = await self._extract_links_from_html(url, content)
                elif 'application/pdf' in content_type and self.config.extract_pdfs:
                    content = await response.read()
                    links = []  # PDF link extraction would go here
                else:
                    content = ""
                    links = []
                
                return CrawlResult(
                    url=url,
                    status_code=response.status,
                    content=content,
                    headers=dict(response.headers),
                    links_found=links,
                    redirect_url=str(response.url) if str(response.url) != url else None,
                    crawl_time_ms=crawl_time_ms,
                    content_type=content_type
                )
                
        except asyncio.TimeoutError:
            return CrawlResult(
                url=url,
                status_code=408,
                error_message="Request timeout",
                crawl_time_ms=int((time.time() - start_time) * 1000)
            )
        except aiohttp.ClientError as e:
            return CrawlResult(
                url=url,
                status_code=0,
                error_message=f"Client error: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=500,
                error_message=f"Unexpected error: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _extract_links_from_html(self, source_url: str, html_content: str) -> List[Backlink]:
        """Extract links from HTML content"""
        try:
            return await self.link_extractor.extract_links(source_url, html_content)
        except Exception as e:
            self.logger.error(f"Error extracting links from {source_url}: {e}")
            return []
    
    async def crawl_domain_for_backlinks(self, target_url: str) -> AsyncGenerator[CrawlResult, None]:
        """Crawl web to find backlinks to target URL/domain"""
        target_domain = urlparse(target_url).netloc
        
        # Start with seed URLs (you'd implement this based on your strategy)
        seed_urls = await self._get_seed_urls_for_backlink_discovery(target_domain)
        
        urls_to_crawl = set(seed_urls)
        crawled_count = 0
        
        while urls_to_crawl and crawled_count < self.config.max_pages:
            # Get next batch of URLs
            batch_size = min(10, len(urls_to_crawl))
            current_batch = [urls_to_crawl.pop() for _ in range(batch_size)]
            
            # Crawl batch concurrently
            tasks = [self.crawl_url(url) for url in current_batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for url, result in zip(current_batch, results):
                if isinstance(result, Exception):
                    self.logger.error(f"Error crawling {url}: {result}")
                    continue
                
                if isinstance(result, CrawlResult):
                    self.crawled_urls.add(url)
                    crawled_count += 1
                    
                    # Check if this page links to our target
                    target_links = [link for link in result.links_found 
                                  if self._is_link_to_target(link, target_url, target_domain)]
                    
                    if target_links:
                        # Found backlinks! Update the result
                        result.links_found = target_links
                        yield result
                    
                    # Add new URLs to crawl queue (for deeper discovery)
                    if crawled_count < self.config.max_pages:
                        new_urls = await self._extract_urls_for_further_crawling(result)
                        urls_to_crawl.update(new_urls - self.crawled_urls)
    
    def _is_link_to_target(self, link: Backlink, target_url: str, target_domain: str) -> bool:
        """Check if a link points to our target URL or domain"""
        link_domain = urlparse(link.target_url).netloc
        
        # Exact URL match
        if link.target_url == target_url:
            return True
        
        # Domain match
        if link_domain == target_domain:
            return True
        
        # Subdomain match
        if link_domain.endswith('.' + target_domain):
            return True
            
        return False
    
    async def