"""
Web Crawler - Core crawling engine for link discovery
File: Link_Profiler/crawlers/web_crawler.py
"""

import asyncio
import aiohttp
import time
from typing import List, Dict, Set, Optional, AsyncGenerator, Tuple
from urllib.parse import urljoin, urlparse, urlencode
from urllib.robotparser import RobotFileParser
import logging
from dataclasses import dataclass, field # Import field
import re
from datetime import datetime, timedelta

from Link_Profiler.core.models import ( # Changed to absolute import
    URL, Backlink, CrawlConfig, CrawlStatus, LinkType, 
    CrawlJob, ContentType, serialize_model, SEOMetrics # Import SEOMetrics
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


@dataclass # Convert to dataclass
class CrawlResult:
    """Result of a single page crawl"""
    url: str
    status_code: int
    content: str = ""
    headers: Dict[str, str] = field(default_factory=dict) # Use field(default_factory=dict)
    links_found: List[Backlink] = field(default_factory=list) # Use field(default_factory=list)
    redirect_url: Optional[str] = None
    error_message: Optional[str] = None
    crawl_time_ms: int = 0
    content_type: str = "text/html"
    seo_metrics: Optional[SEOMetrics] = None # Added for SEO metrics
    crawl_timestamp: Optional[datetime] = None # New: UTC timestamp when the page was crawled


class WebCrawler:
    """Main web crawler class"""
    
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.rate_limiter = RateLimiter(1.0 / config.delay_seconds)
        self.robots_parser = RobotsParser() # Initialise, but session managed by __aenter__
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
        # Enter robots_parser's context to manage its aiohttp session
        await self.robots_parser.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
        # Exit robots_parser's context
        await self.robots_parser.__aexit__(exc_type, exc_val, exc_tb)
    
    async def crawl_url(self, url: str) -> CrawlResult:
        """Crawl a single URL and extract links"""
        start_time = time.time()
        current_crawl_timestamp = datetime.now() # Capture timestamp at the start of the crawl attempt
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        # Check if domain is allowed
        if not self.config.is_domain_allowed(domain):
            return CrawlResult(
                url=url,
                status_code=403,
                error_message="Domain not allowed by config", # More specific message
                crawl_timestamp=current_crawl_timestamp
            )
        
        # Check robots.txt if enabled
        if self.config.respect_robots_txt:
            can_crawl = await self.robots_parser.can_fetch(url, self.config.user_agent)
            if not can_crawl:
                # This means robots.txt explicitly disallowed it
                return CrawlResult(
                    url=url,
                    status_code=403,
                    error_message="Blocked by robots.txt rules", # More specific message
                    crawl_timestamp=current_crawl_timestamp
                )
        
        # Rate limiting
        await self.rate_limiter.wait_if_needed(domain)
        
        try:
            async with self.session.get(url, allow_redirects=self.config.follow_redirects) as response:
                crawl_time_ms = int((time.time() - start_time) * 1000)
                
                # Get content type
                content_type = response.headers.get('content-type', '').lower()
                
                # Read content based on type
                content = ""
                links = []
                seo_metrics = None # Initialize seo_metrics
                
                if 'text/html' in content_type:
                    content = await response.text()
                    links = await self._extract_links_from_html(url, content)
                    
                    # Populate http_status and crawl_timestamp for each extracted Backlink
                    for link in links:
                        link.http_status = response.status
                        link.crawl_timestamp = current_crawl_timestamp

                    seo_metrics = await self.content_parser.parse_seo_metrics(url, content) # Parse SEO metrics
                    
                    # Populate SEOMetrics with page-level metrics from the HTTP response
                    if seo_metrics:
                        seo_metrics.http_status = response.status
                        seo_metrics.response_time_ms = crawl_time_ms
                        # Get page size from Content-Length header or content length
                        content_length_header = response.headers.get('Content-Length')
                        if content_length_header:
                            try:
                                seo_metrics.page_size_bytes = int(content_length_header)
                            except ValueError:
                                self.logger.warning(f"Invalid Content-Length header for {url}: {content_length_header}")
                                seo_metrics.page_size_bytes = len(content.encode('utf-8')) # Fallback to content length
                        else:
                            seo_metrics.page_size_bytes = len(content.encode('utf-8')) # Fallback to content length

                elif 'application/pdf' in content_type and self.config.extract_pdfs:
                    content = await response.read() # Read as bytes for PDF
                    links = []  # PDF link extraction would go here
                # Add other content types as needed (e.g., images, video, etc.)
                
                self.logger.debug(f"SEO metrics for {url}: {seo_metrics}") # Added debug log
                return CrawlResult(
                    url=url,
                    status_code=response.status,
                    content=content, # Store content for further parsing if needed
                    headers=dict(response.headers),
                    links_found=links,
                    redirect_url=str(response.url) if str(response.url) != url else None,
                    crawl_time_ms=crawl_time_ms,
                    content_type=content_type,
                    seo_metrics=seo_metrics, # Pass SEO metrics in CrawlResult
                    crawl_timestamp=current_crawl_timestamp # Pass the crawl timestamp
                )
                
        except asyncio.TimeoutError:
            return CrawlResult(
                url=url,
                status_code=408,
                error_message="Request timeout",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp
            )
        except aiohttp.ClientError as e:
            # This will catch connection errors, DNS errors, etc.
            return CrawlResult(
                url=url,
                status_code=0, # Use 0 or a specific code for network errors
                error_message=f"Network or client error: {str(e)}", # More generic message
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp
            )
        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=500,
                error_message=f"Unexpected error during crawl: {str(e)}", # More specific message
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp
            )
    
    async def _extract_links_from_html(self, source_url: str, html_content: str) -> List[Backlink]:
        """Extract links from HTML content"""
        try:
            return await self.link_extractor.extract_links(source_url, html_content)
        except Exception as e:
            self.logger.error(f"Error extracting links from {source_url}: {e}")
            return []
    
    async def crawl_for_backlinks(self, target_url: str, initial_seed_urls: List[str]) -> AsyncGenerator[CrawlResult, None]:
        """
        Crawl web to find backlinks to target URL/domain.
        Starts with initial_seed_urls and explores up to max_depth.
        """
        target_domain = urlparse(target_url).netloc
        
        # Use a queue for URLs to crawl, storing (url, current_depth)
        # A simple set for visited URLs is fine for now.
        urls_to_visit = asyncio.Queue()
        for url in initial_seed_urls:
            await urls_to_visit.put((url, 0)) # (url, depth)
            
        self.crawled_urls.clear() # Reset for new crawl job
        self.failed_urls.clear()
        crawled_count = 0
        
        while not urls_to_visit.empty() and crawled_count < self.config.max_pages:
            url, current_depth = await urls_to_visit.get()
            
            if url in self.crawled_urls:
                continue
            
            if current_depth >= self.config.max_depth:
                self.logger.debug(f"Skipping {url} due to max depth ({current_depth})")
                continue
            
            self.crawled_urls.add(url)
            crawled_count += 1
            
            self.logger.info(f"Crawling: {url} (Depth: {current_depth}, Crawled: {crawled_count}/{self.config.max_pages})")
            
            result = await self.crawl_url(url)
            
            if result.error_message:
                self.logger.warning(f"Failed to crawl {url}: {result.error_message}")
                self.failed_urls.add(url)
                continue
            
            # Check if this page links to our target
            target_links = [link for link in result.links_found 
                            if self._is_link_to_target(link, target_url, target_domain)]
            
            if target_links:
                # Found backlinks! Update the result and yield
                result.links_found = target_links
                yield result
            
            # Add new URLs to crawl queue for further exploration
            # Only add internal links of the *source* domain for deeper crawling
            # if we are trying to find more potential sources of backlinks.
            # For backlink discovery, we typically only care about the first level
            # of links from a source page. However, if we want to find *more*
            # potential source pages, we might follow internal links on the source.
            
            for link in result.links_found:
                # Only add if the domain is allowed by the config
                parsed_link_url = urlparse(link.target_url)
                if self.config.is_domain_allowed(parsed_link_url.netloc):
                    # Ensure we don't re-add already crawled URLs or exceed max_pages
                    if link.target_url not in self.crawled_urls and \
                       crawled_count + urls_to_visit.qsize() < self.config.max_pages:
                        await urls_to_visit.put((link.target_url, current_depth + 1))
    
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
