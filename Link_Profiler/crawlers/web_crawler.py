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
import random # Import random for human-like delays
from collections import deque # New: Import deque

from Link_Profiler.core.models import ( # Changed to absolute import
    URL, Backlink, CrawlConfig, CrawlStatus, LinkType, 
    CrawlJob, ContentType, serialize_model, SEOMetrics # Import SEOMetrics
)
from Link_Profiler.database.database import Database # Import Database for job status checks
from .link_extractor import LinkExtractor
from .content_parser import ContentParser
from .robots_parser import RobotsParser
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager
from Link_Profiler.utils.proxy_manager import proxy_manager # New: Import ProxyManager
from Link_Profiler.utils.content_validator import ContentValidator # New: Import ContentValidator
from Link_Profiler.config.config_loader import config_loader # New: Import config_loader


class CrawlerError(Exception):
    """Custom exception for crawler errors"""
    pass


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter to respect website policies and react to server responses.
    Adjusts delay based on HTTP status codes and response times.
    Can incorporate a history of past interactions for more informed decisions.
    """
    
    def __init__(self, initial_delay_seconds: float = 1.0, ml_rate_optimization_enabled: bool = False, rate_limiter_config: Dict = None):
        self.domain_delays: Dict[str, float] = {} # Stores current delay for each domain
        self.initial_delay = initial_delay_seconds
        self.last_request_time: Dict[str, float] = {} # Track last request time per domain
        self.logger = logging.getLogger(__name__ + ".AdaptiveRateLimiter")

        self.ml_rate_optimization_enabled = ml_rate_optimization_enabled
        self.rate_limiter_config = rate_limiter_config or {}
        self.history_size = self.rate_limiter_config.get("history_size", 10)
        self.success_factor = self.rate_limiter_config.get("success_factor", 0.9) # Factor to decrease delay on success
        self.failure_factor = self.rate_limiter_config.get("failure_factor", 1.5) # Factor to increase delay on failure
        self.min_delay = self.rate_limiter_config.get("min_delay", 0.1)
        self.max_delay = self.rate_limiter_config.get("max_delay", 60.0)

        # Stores history of (status_code, crawl_time_ms) for each domain
        self.domain_history: Dict[str, deque[Tuple[int, int]]] = {}

    async def wait_if_needed(self, domain: str, last_crawl_result: Optional['CrawlResult'] = None) -> None:
        """
        Wait if needed to respect rate limits, adapting based on last crawl result and history.
        """
        current_delay = self.domain_delays.get(domain, self.initial_delay)

        if last_crawl_result:
            # Update history for the domain
            if domain not in self.domain_history:
                self.domain_history[domain] = deque(maxlen=self.history_size)
            self.domain_history[domain].append((last_crawl_result.status_code, last_crawl_result.crawl_time_ms))

            if self.ml_rate_optimization_enabled:
                # Advanced heuristic based on history (placeholder for ML model)
                recent_history = self.domain_history[domain]
                successful_responses = [r for r in recent_history if 200 <= r[0] < 400]
                failed_responses = [r for r in recent_history if r[0] >= 400 or r[0] == 0] # 0 for network errors

                success_ratio = len(successful_responses) / len(recent_history) if recent_history else 1.0
                avg_response_time = sum(r[1] for r in successful_responses) / len(successful_responses) if successful_responses else 0

                if last_crawl_result.status_code == 429:
                    current_delay *= self.failure_factor * 2 # Aggressive increase for 429
                    self.logger.warning(f"ML Rate Limiter: Doubling delay for {domain} due to 429. New delay: {current_delay:.2f}s")
                elif last_crawl_result.status_code >= 500 or last_crawl_result.status_code == 0:
                    current_delay *= self.failure_factor # Increase for server errors/network issues
                    self.logger.warning(f"ML Rate Limiter: Increasing delay for {domain} due to {last_crawl_result.status_code}. New delay: {current_delay:.2f}s")
                elif success_ratio < 0.7: # If less than 70% of recent requests were successful
                    current_delay *= self.failure_factor # Increase due to general instability
                    self.logger.info(f"ML Rate Limiter: Increasing delay for {domain} due to low success ratio ({success_ratio:.1f}). New delay: {current_delay:.2f}s")
                elif avg_response_time > 3000: # If average response time is high
                    current_delay *= (1 + (avg_response_time / 10000)) # Increase based on slowness
                    self.logger.info(f"ML Rate Limiter: Increasing delay for {domain} due to high avg response time ({avg_response_time}ms). New delay: {current_delay:.2f}s")
                else:
                    current_delay = max(self.initial_delay, current_delay * self.success_factor) # Decrease on good performance
                    self.logger.debug(f"ML Rate Limiter: Decreasing delay for {domain} due to good performance. New delay: {current_delay:.2f}s")
            else:
                # Original adaptive logic if ML optimization is not enabled
                if last_crawl_result.status_code == 429:  # Too Many Requests
                    current_delay *= 2.0 # Double the delay
                    self.logger.warning(f"Adaptive Rate Limiter: Doubling delay for {domain} due to 429. New delay: {current_delay:.2f}s")
                elif 500 <= last_crawl_result.status_code < 600:  # Server errors
                    current_delay *= 1.5 # Increase delay by 50%
                    self.logger.warning(f"Adaptive Rate Limiter: Increasing delay for {domain} due to {last_crawl_result.status_code}. New delay: {current_delay:.2f}s")
                elif last_crawl_result.crawl_time_ms > 5000:  # Slow responses (over 5 seconds)
                    current_delay *= 1.2 # Increase delay by 20%
                    self.logger.info(f"Adaptive Rate Limiter: Increasing delay for {domain} due to slow response ({last_crawl_result.crawl_time_ms}ms). New delay: {current_delay:.2f}s")
                else:
                    current_delay = max(self.initial_delay, current_delay * 0.9) # Decrease by 10%, but not below initial
                    self.logger.debug(f"Adaptive Rate Limiter: Decreasing delay for {domain} due to good response. New delay: {current_delay:.2f}s")
            
            # Ensure delay doesn't go below a reasonable minimum or above a maximum
            current_delay = max(self.min_delay, min(current_delay, self.max_delay))

        self.domain_delays[domain] = current_delay

        now = time.time()
        last_time = self.last_request_time.get(domain, 0)
        time_since_last = now - last_time
        
        if time_since_last < current_delay:
            wait_time = current_delay - time_since_last
            self.logger.debug(f"Waiting {wait_time:.2f}s for {domain} to respect rate limit.")
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
    validation_issues: List[str] = field(default_factory=list) # New: Issues found by ContentValidator


class WebCrawler:
    """Main web crawler class"""
    
    def __init__(self, config: CrawlConfig, db: Database, job_id: str):
        self.config = config
        self.db = db # Database instance to check job status
        self.job_id = job_id # ID of the current crawl job
        
        # Initialize AdaptiveRateLimiter with ML optimization flag and config
        self.rate_limiter = AdaptiveRateLimiter(
            initial_delay_seconds=self.config.delay_seconds,
            ml_rate_optimization_enabled=config_loader.get("anti_detection.ml_rate_optimization", False),
            rate_limiter_config=config_loader.get("rate_limiter")
        )
        self.robots_parser = RobotsParser() # Initialise, but session managed by __aenter__
        self.link_extractor = LinkExtractor()
        self.content_parser = ContentParser() 
        self.content_validator = ContentValidator() # New: Initialize ContentValidator
        self.session: Optional[aiohttp.ClientSession] = None
        self.crawled_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.logger = logging.getLogger(__name__)

        # Initialize ProxyManager if enabled
        if config_loader.get("proxy_management.enabled", False) and self.config.proxy_list:
            proxy_manager.load_proxies(
                self.config.proxy_list, # Pass the new format
                config_loader.get("proxy_management.proxy_retry_delay_seconds", 300)
            )
            self.use_proxies = True
            self.logger.info("WebCrawler initialized with proxy management enabled.")
        else:
            self.use_proxies = False
            self.logger.info("WebCrawler initialized without proxy management.")
        
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
        
        # Determine headers based on config
        headers = self.config.custom_headers.copy() if self.config.custom_headers else {}
        if config_loader.get("anti_detection.request_header_randomization", False):
            random_headers = user_agent_manager.get_random_headers()
            headers.update(random_headers) # Overwrite default user-agent if present
        elif self.config.user_agent_rotation: # Fallback to just user-agent rotation if header randomization is off
            headers['User-Agent'] = user_agent_manager.get_random_user_agent()
        else: # Use user_agent from config if no rotation/randomization
            headers['User-Agent'] = self.config.user_agent

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
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
    
    async def crawl_url(self, url: str, last_crawl_result: Optional[CrawlResult] = None) -> CrawlResult:
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
            can_crawl = await self.robots_parser.can_fetch(url, self.session.headers.get('User-Agent', self.config.user_agent))
            if not can_crawl:
                # This means robots.txt explicitly disallowed it
                return CrawlResult(
                    url=url,
                    status_code=403,
                    error_message="Blocked by robots.txt rules", # More specific message
                    crawl_timestamp=current_crawl_timestamp
                )
        
        # Rate limiting (adaptive)
        await self.rate_limiter.wait_if_needed(domain, last_crawl_result)
        
        # Add human-like delays if configured
        if config_loader.get("anti_detection.human_like_delays", False):
            await asyncio.sleep(random.uniform(0.1, 0.5)) # Small random delay before request

        current_proxy = None
        if self.use_proxies:
            current_proxy = proxy_manager.get_next_proxy(desired_region=self.config.proxy_region) # Pass desired_region
            if current_proxy:
                self.logger.debug(f"Using proxy {current_proxy} for {url}")
            else:
                self.logger.warning(f"No available proxies for {url}. Proceeding without proxy.")

        try:
            async with self.session.get(url, allow_redirects=self.config.follow_redirects, proxy=current_proxy) as response:
                crawl_time_ms = int((time.time() - start_time) * 1000)
                
                # Get content type
                content_type = response.headers.get('content-type', '').lower()
                
                # Read content based on type
                content = ""
                links = []
                seo_metrics = None # Initialize seo_metrics
                validation_issues = [] # Initialize validation issues
                
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

                    # New: Perform content validation if enabled
                    if config_loader.get("quality_assurance.content_validation", False):
                        validation_issues = self.content_validator.validate_crawl_result(url, content, response.status)
                        if seo_metrics:
                            seo_metrics.validation_issues = validation_issues # Store in SEO metrics
                        if validation_issues:
                            self.logger.warning(f"Content validation issues for {url}: {validation_issues}")

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
                    crawl_timestamp=current_crawl_timestamp, # Pass the crawl timestamp
                    validation_issues=validation_issues # Pass validation issues
                )
                
        except asyncio.TimeoutError:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason="timeout")
            return CrawlResult(
                url=url,
                status_code=408,
                error_message="Request timeout",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp
            )
        except aiohttp.ClientProxyConnectionError as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"proxy_connection_error: {e}")
            return CrawlResult(
                url=url,
                status_code=502, # Bad Gateway or Proxy Error
                error_message=f"Proxy connection error: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp
            )
        except aiohttp.ClientResponseError as e:
            if current_proxy and e.status in [403, 407, 429, 500, 502, 503, 504]:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"http_status_{e.status}")
            return CrawlResult(
                url=url,
                status_code=e.status,
                error_message=f"HTTP error: {e.message}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp
            )
        except aiohttp.ClientError as e:
            # This will catch other connection errors, DNS errors, etc.
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"client_error: {e}")
            return CrawlResult(
                url=url,
                status_code=0, # Use 0 or a specific code for network errors
                error_message=f"Network or client error: {str(e)}", # More generic message
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp
            )
        except Exception as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"unexpected_error: {e}")
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
        
        last_crawl_result: Optional[CrawlResult] = None # Track last result for adaptive rate limiting

        while not urls_to_visit.empty() and crawled_count < self.config.max_pages:
            # Periodically check job status from DB
            current_job = self.db.get_crawl_job(self.job_id)
            if current_job:
                if current_job.status == CrawlStatus.PAUSED:
                    self.logger.info(f"Crawler for job {self.job_id} paused. Waiting to resume...")
                    while True:
                        await asyncio.sleep(5) # Check every 5 seconds
                        rechecked_job = self.db.get_crawl_job(self.job_id)
                        if rechecked_job and rechecked_job.status == CrawlStatus.IN_PROGRESS:
                            self.logger.info(f"Crawler for job {self.job_id} resumed.")
                            break
                        elif rechecked_job and rechecked_job.status == CrawlStatus.STOPPED:
                            self.logger.info(f"Crawler for job {self.job_id} stopped during pause.")
                            return # Exit the generator

            url, current_depth = await urls_to_visit.get()
            
            if url in self.crawled_urls:
                continue
            
            if current_depth >= self.config.max_depth:
                self.logger.debug(f"Skipping {url} due to max depth ({current_depth})")
                continue
            
            self.crawled_urls.add(url)
            crawled_count += 1
            
            self.logger.info(f"Crawling: {url} (Depth: {current_depth}, Crawled: {crawled_count}/{self.config.max_pages})")
            
            result = await self.crawl_url(url, last_crawl_result) # Pass last_crawl_result
            last_crawl_result = result # Update last_crawl_result

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
