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

from Link_Profiler.core.models import ( # Changed to absolute import
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
                content = ""
                links = []
                
                if 'text/html' in content_type:
                    content = await response.text()
                    links = await self._extract_links_from_html(url, content)
                    # Future: Pass content to ContentParser for SEO metrics
                    # seo_metrics = await self.content_parser.parse_seo_metrics(url, content)
                elif 'application/pdf' in content_type and self.config.extract_pdfs:
                    content = await response.read() # Read as bytes for PDF
                    links = []  # PDF link extraction would go here
                # Add other content types as needed (e.g., images, video, etc.)
                
                return CrawlResult(
                    url=url,
                    status_code=response.status,
                    content=content, # Store content for further parsing if needed
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
    
    async def _get_seed_urls_for_backlink_discovery(self, target_domain: str) -> Set[str]:
        """
        Placeholder for generating initial seed URLs for backlink discovery.
        In a real system, this might involve:
        - Querying search engines (e.g., Google, Bing) for pages mentioning the target domain.
        - Using known backlink databases (e.g., Ahrefs, SEMrush APIs - if available/free tier).
        - Starting with common directories or industry-specific sites.
        For now, we'll use a very basic approach: just the target domain itself.
        """
        self.logger.info(f"Generating seed URLs for target domain: {target_domain}")
        # Example: A very basic seed could be the target domain's homepage
        # or a few common pages. For finding backlinks, we need *other* sites.
        # This is a complex problem. For a simple start, we might assume
        # we have a list of "known good" sites to crawl.
        
        # For demonstration, let's assume we have a few external sites
        # that might link to our target. In a real scenario, these would
        # come from a more intelligent discovery process.
        
        # IMPORTANT: For finding backlinks, we need to crawl *other* domains,
        # not just the target domain itself.
        
        # For now, let's return a dummy set of external URLs that *might* link
        # to the target. In a real system, this would be populated by
        # external data sources or a more sophisticated discovery phase.
        
        # If the goal is to find expired domains, you might start by crawling
        # lists of expired domains or domains known to have many backlinks.
        
        # For the purpose of demonstrating the backlink discovery,
        # let's assume we have a few external sites to start crawling.
        # These would typically be discovered via external means (e.g., search queries).
        
        # This is a critical point: the crawler needs to know *where to look* for backlinks.
        # Without external data, it's hard to find them.
        
        # Let's return an empty set for now, and rely on an external process
        # to feed URLs into the crawl. The `crawl_domain_for_backlinks`
        # method will need to be initiated with some starting URLs.
        
        # For a minimal viable product, one might manually provide a list of
        # high-authority sites to crawl, or use a very basic search query.
        
        # For now, let's just return the target URL itself as a seed,
        # assuming it might have internal links that eventually lead to external ones
        # (though this is not ideal for *finding* backlinks from *other* sites).
        # A better approach would be to have a separate module that queries
        # search engines or backlink databases to get initial "source" URLs.
        
        # Let's assume for now that the `crawl_domain_for_backlinks` method
        # will be given an initial set of URLs to start with, rather than
        # generating them here. This method will be removed or refactored.
        
        # Instead, the `crawl_domain_for_backlinks` will take an initial list of
        # `seed_urls` as an argument.
        return set() # This method will be refactored out or replaced.
    
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
            
            # For now, let's follow all discovered links (internal and external)
            # up to max_depth, but only yield results for links *to the target*.
            
            for link in result.links_found:
                # Only add links that are within the allowed domains or are external
                # and could potentially lead to more backlink sources.
                # This logic needs careful consideration based on the crawl strategy.
                
                # For a backlink crawler, we are interested in finding pages that link
                # to our target. So, we crawl a page, extract its links. If any of
                # those links point to our target, we record it.
                # If we want to find *more* pages that might link to our target,
                # we need to decide which *other* links on the current page to follow.
                
                # A common strategy for backlink discovery is a "breadth-first"
                # approach on external domains.
                
                # Let's refine: we add *any* discovered URL to the queue if it hasn't
                # been crawled and is within depth limits. The `_is_link_to_target`
                # filters what we *yield* as a backlink.
                
                # Ensure we don't re-add already crawled URLs or exceed max_pages
                if link.target_url not in self.crawled_urls and \
                   crawled_count + urls_to_visit.qsize() < self.config.max_pages:
                    # Only add if the domain is allowed by the config
                    parsed_link_url = urlparse(link.target_url)
                    if self.config.is_domain_allowed(parsed_link_url.netloc):
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
