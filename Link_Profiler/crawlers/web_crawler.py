"""
Production-Ready Web Crawler with Full Feature Integration
"""
import asyncio
import aiohttp
import time
from typing import Optional, List, Dict, Any, Union, Set, Tuple
from datetime import datetime
from urllib.parse import urlparse, urljoin
import logging
from dataclasses import dataclass
import random
import json

# Existing imports
from Link_Profiler.utils.circuit_breaker import ResilienceManager, CircuitBreakerOpenError
from Link_Profiler.utils.adaptive_rate_limiter import MLRateLimiter
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue, Priority
from Link_Profiler.monitoring.crawler_metrics import crawler_metrics
from Link_Profiler.monitoring.health_monitor import HealthMonitor
from Link_Profiler.core.models import CrawlResult, CrawlConfig, Backlink, SEOMetrics, CrawlError
from Link_Profiler.crawlers.robots_parser import RobotsParser
from Link_Profiler.crawlers.content_parser import ContentParser
from Link_Profiler.crawlers.link_extractor import LinkExtractor
from Link_Profiler.utils.content_validator import ContentValidator
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.proxy_manager import proxy_manager
from Link_Profiler.services.ai_service import AIService

# New imports needed
from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)

class EnhancedWebCrawler:
    """Production-ready web crawler with comprehensive features"""
    
    def __init__(self, 
                 config: CrawlConfig,
                 crawl_queue: Optional[SmartCrawlQueue] = None,
                 ai_service: Optional[AIService] = None,
                 browser: Optional[Browser] = None):
        
        # Core configuration
        self.config = config
        self.crawl_queue = crawl_queue
        self.ai_service = ai_service
        self.browser = browser # Playwright browser instance passed from main.py
        
        # Advanced components
        self.resilience_manager = ResilienceManager()
        self.rate_limiter = MLRateLimiter()
        self.metrics = crawler_metrics
        self.health_monitor = HealthMonitor(self.metrics)
        
        # Content processing
        self.robots_parser = RobotsParser()
        self.content_parser = ContentParser()
        self.link_extractor = LinkExtractor()
        self.content_validator = ContentValidator()
        
        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.crawled_urls: set = set()
        self.failed_urls: set = set()
        
        # Statistics
        self.stats = {
            'pages_crawled': 0,
            'links_found': 0,
            'errors': [],
            'start_time': None
        }
    
    async def __aenter__(self):
        """Initialize crawler with proper session management"""
        # Create persistent HTTP session
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=10,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True,
            # New: Connection health checks
            verify_ssl=True, # Always verify SSL certificates
            # For more advanced health checks, a custom connector class might be needed
            # or periodic checks on existing connections.
        )
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout_seconds,
            connect=10,
            sock_read=30
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self._get_default_headers()
        )
        
        # Initialize parsers
        await self.robots_parser.__aenter__()
        
        # Start health monitoring
        await self.health_monitor.start_monitoring()
        
        self.stats['start_time'] = time.time()
        logger.info("Enhanced WebCrawler initialized successfully")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup resources"""
        self.health_monitor.stop_monitoring()
        
        if self.session:
            await self.session.close()
            
        await self.robots_parser.__aexit__(exc_type, exc_val, exc_tb)
        
        # Browser is managed by main.py's lifespan, so no need to close here
        # if self.browser:
        #     await self.browser.close()
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default HTTP headers with anti-detection"""
        headers = {
            'User-Agent': self.config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        if self.config.custom_headers:
            headers.update(self.config.custom_headers)
            
        return headers
    
    async def crawl_url(self, url: str, depth: int = 0, 
                       last_crawl_result: Optional[CrawlResult] = None) -> CrawlResult:
        """Main crawl method with full resilience"""
        try:
            return await self.resilience_manager.execute_with_resilience(
                self._crawl_url_internal, url, depth, last_crawl_result
            )
        except CircuitBreakerOpenError as e:
            # Enhanced error handling: Classify error
            error_type = "CircuitBreakerOpen"
            logger.error(f"Circuit breaker open for {url}: {e}")
            return self._create_error_result(url, 503, f"Circuit breaker open: {e}", error_type=error_type)
        except Exception as e:
            # Enhanced error handling: Catch all unexpected errors
            error_type = "UnexpectedCrawlError"
            logger.error(f"Unexpected error crawling {url}: {e}", exc_info=True)
            return self._create_error_result(url, 500, f"Unexpected error: {e}", error_type=error_type)
    
    async def _crawl_url_internal(self, url: str, depth: int = 0,
                                 last_crawl_result: Optional[CrawlResult] = None) -> CrawlResult:
        """Internal crawl implementation with full feature integration"""
        start_time = time.time()
        current_timestamp = datetime.now()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        logger.debug(f"Crawling {url} at depth {depth}")
        
        # Track request start
        request_context = await self.metrics.track_request_start(url, {
            'depth': depth,
            'job_id': getattr(self, 'current_job_id', None)
        })
        
        # Domain filtering
        if not self.config.is_domain_allowed(domain):
            result = self._create_error_result(url, 403, f"Domain {domain} not allowed", error_type="DomainBlocked")
            await self.metrics.track_request_complete(url, result, request_context)
            return result
        
        # Robots.txt check
        if self.config.respect_robots_txt:
            can_crawl = await self.robots_parser.can_fetch(url, self.config.user_agent)
            if not can_crawl:
                result = self._create_error_result(url, 403, "Blocked by robots.txt", error_type="RobotsTxtBlocked")
                await self.metrics.track_request_complete(url, result, request_context)
                return result
        
        # Rate limiting
        await self.rate_limiter.adaptive_wait(domain, last_crawl_result)
        
        # Human-like delays
        if self.config.human_like_delays:
            delay = random.uniform(0.5, 2.0)
            await asyncio.sleep(delay)
        
        # Determine crawl method
        if self.config.render_javascript and self.browser:
            result = await self._crawl_with_browser(url, domain, request_context)
        else:
            result = await self._crawl_with_http(url, domain, request_context)
        
        # Post-processing
        result.crawl_time_ms = int((time.time() - start_time) * 1000)
        result.crawl_timestamp = current_timestamp
        
        # Content validation
        if result.content and result.status_code == 200:
            result = await self._validate_and_enhance_content(result)
        
        # Update statistics
        self.stats['pages_crawled'] += 1
        self.stats['links_found'] += len(result.links_found)
        
        await self.metrics.track_request_complete(url, result, request_context)
        return result
    
    async def _crawl_with_http(self, url: str, domain: str, 
                              request_context: Dict) -> CrawlResult:
        """HTTP-based crawling with session reuse"""
        headers = self._get_request_headers(domain)
        proxy = None
        proxy_details = None # New: Store ProxyDetails object
        if self.config.use_proxies:
            proxy_details = proxy_manager.get_next_proxy(desired_region=self.config.proxy_region)
            if proxy_details:
                proxy = proxy_details.url
            else:
                logger.warning(f"No proxy available for region {self.config.proxy_region}. Proceeding without proxy.")

        try:
            async with self.session.get(url, headers=headers, proxy=proxy) as response:
                content = await response.text()
                response_headers = dict(response.headers)
                
                # Extract links
                links = await self.link_extractor.extract_links(url, content)
                
                # Parse SEO metrics
                seo_metrics = await self.content_parser.parse_seo_metrics(url, content)
                seo_metrics.http_status = response.status
                seo_metrics.response_time_ms = (time.time() - request_context.get('start_time', time.time())) * 1000
                
                # Mark proxy good if used
                if proxy_details:
                    proxy_manager.mark_proxy_good(proxy_details.url)

                return CrawlResult(
                    url=url,
                    status_code=response.status,
                    content=content,
                    headers=response_headers,
                    links_found=links,
                    seo_metrics=seo_metrics,
                    content_type=response.headers.get('content-type', 'text/html')
                )
                
        except aiohttp.ClientError as e:
            if proxy_details:
                proxy_manager.mark_proxy_bad(proxy_details.url, reason=f"ClientError: {e}")
            return self._create_error_result(url, 0, f"HTTP error: {e}", error_type="ClientError")
        except asyncio.TimeoutError:
            if proxy_details:
                proxy_manager.mark_proxy_bad(proxy_details.url, reason="TimeoutError")
            return self._create_error_result(url, 408, "Request timeout", error_type="TimeoutError")
        except Exception as e:
            if proxy_details:
                proxy_manager.mark_proxy_bad(proxy_details.url, reason=f"UnexpectedHTTPError: {e}")
            return self._create_error_result(url, 500, f"Unexpected HTTP crawl error: {e}", error_type="UnexpectedHTTPError")
    
    async def _crawl_with_browser(self, url: str, domain: str,
                                 request_context: Dict) -> CrawlResult:
        """Browser-based crawling for JavaScript content"""
        if not self.browser:
            return self._create_error_result(url, 500, "Browser not initialized for JavaScript rendering.", error_type="BrowserNotInitialized")

        context: Optional[BrowserContext] = None
        proxy = None
        proxy_details = None # New: Store ProxyDetails object
        if self.config.use_proxies:
            proxy_details = proxy_manager.get_next_proxy(desired_region=self.config.proxy_region)
            if proxy_details:
                proxy = {"server": proxy_details.url}
            else:
                logger.warning(f"No proxy available for region {self.config.proxy_region}. Proceeding without proxy.")

        try:
            context = await self.browser.new_context(
                user_agent=self._get_user_agent_for_domain(domain),
                viewport={'width': 1920, 'height': 1080},
                proxy=proxy # Pass proxy dict directly
            )
            
            page = await context.new_page()
            
            # Navigate and wait for content
            response = await page.goto(url, wait_until='networkidle')
            content = await page.content()
            
            # Extract links from rendered content
            links = await self.link_extractor.extract_links(url, content)
            
            # Parse SEO metrics
            seo_metrics = await self.content_parser.parse_seo_metrics(url, content)
            seo_metrics.http_status = response.status if response else 200
            seo_metrics.response_time_ms = (time.time() - request_context.get('start_time', time.time())) * 1000
            
            # Mark proxy good if used
            if proxy_details:
                proxy_manager.mark_proxy_good(proxy_details.url)

            return CrawlResult(
                url=url,
                status_code=response.status if response else 200,
                content=content,
                links_found=links,
                seo_metrics=seo_metrics,
                content_type='text/html'
            )
            
        except Exception as e:
            if proxy_details:
                proxy_manager.mark_proxy_bad(proxy_details.url, reason=f"BrowserCrawlError: {e}")
            return self._create_error_result(url, 500, f"Browser error: {e}", error_type="BrowserCrawlError")
        finally:
            if context:
                await context.close()
    
    async def _validate_and_enhance_content(self, result: CrawlResult) -> CrawlResult:
        """Validate content and enhance with AI analysis"""
        # Content validation
        validation_issues = self.content_validator.validate_crawl_result(
            result.url, result.content, result.status_code
        )
        result.validation_issues = validation_issues
        
        # AI content quality assessment
        if self.ai_service and self.ai_service.enabled and result.content:
            try:
                ai_score, ai_classification = await self.ai_service.assess_content_quality(
                    result.content, result.url
                )
                if ai_score is not None and ai_classification is not None:
                    if result.seo_metrics is None:
                        result.seo_metrics = SEOMetrics(url=result.url)
                    result.seo_metrics.ai_content_score = ai_score
                    result.seo_metrics.ai_content_classification = ai_classification
                    # Recalculate SEO score if AI metrics are added
                    result.seo_metrics.calculate_seo_score()
            except Exception as e:
                logger.warning(f"AI content quality analysis failed for {result.url}: {e}")
        
        return result
    
    def _get_request_headers(self, domain: str) -> Dict[str, str]:
        """Get headers with rotation if enabled"""
        headers = self._get_default_headers().copy()
        
        if self.config.user_agent_rotation:
            headers['User-Agent'] = user_agent_manager.get_random_user_agent() # Use UserAgentManager
        
        # Add other random headers if enabled
        if self.config.request_header_randomization:
            # This would involve a more sophisticated header randomization utility
            pass # Placeholder for actual implementation
        
        return headers
    
    def _get_user_agent_for_domain(self, domain: str) -> str:
        """Get user agent for domain with consistency if enabled"""
        if self.config.consistent_ua_per_domain:
            return user_agent_manager.get_user_agent_for_domain(domain)
        return user_agent_manager.get_random_user_agent()
    
    def _get_proxy(self) -> Optional[str]:
        """Get proxy if available"""
        if self.config.use_proxies and self.config.proxy_list:
            # ProxyManager.get_next_proxy should return a dict with 'url' key
            proxy_info = proxy_manager.get_next_proxy(desired_region=self.config.proxy_region)
            return proxy_info.get('url') if proxy_info else None
        return None
    
    def _create_error_result(self, url: str, status_code: int, error_message: str, error_type: str = "UnknownError") -> CrawlResult:
        """Create standardized error result"""
        return CrawlResult(
            url=url,
            status_code=status_code,
            error_message=error_message,
            crawl_time_ms=0,
            crawl_timestamp=datetime.now(),
            anomaly_flags=[f"Error: {error_message}"],
            errors=[CrawlError(url=url, error_type=error_type, message=error_message)]
        )
    
    async def start_crawl(self, target_url: str, initial_seed_urls: List[str], 
                         job_id: str) -> CrawlResult:
        """Enhanced crawl orchestration"""
        self.current_job_id = job_id
        start_time = time.time()
        
        logger.info(f"Starting enhanced crawl for job {job_id}")
        
        # Initialize stats
        pages_crawled = 0
        total_links = 0
        backlinks_found_list: List[Backlink] = [] # Renamed to avoid conflict with method
        errors: List[CrawlError] = []
        
        target_domain = urlparse(target_url).netloc
        
        if self.crawl_queue:
            # Smart queue implementation
            try:
                # Enqueue initial URLs
                for url in initial_seed_urls:
                    await self.crawl_queue.enqueue_url(
                        url, Priority.HIGH, 
                        metadata={'depth': 0}, 
                        job_id=job_id
                    )
                
                # Process queue
                while pages_crawled < self.config.max_pages:
                    task = await self.crawl_queue.get_next_task()
                    if not task:
                        break
                    
                    depth = task.metadata.get('depth', 0)
                    if depth >= self.config.max_depth:
                        await self.crawl_queue.mark_task_completed(task, True)
                        continue
                    
                    result = await self.crawl_url(task.url, depth)
                    
                    if result.error_message:
                        await self.crawl_queue.mark_task_completed(task, False)
                        errors.append(CrawlError(
                            url=task.url,
                            error_type="CrawlError",
                            message=result.error_message
                        ))
                    else:
                        await self.crawl_queue.mark_task_completed(task, True)
                        pages_crawled += 1
                        total_links += len(result.links_found)
                        
                        # Check for backlinks to target
                        target_links = [
                            link for link in result.links_found
                            if self._is_backlink_to_target(link, target_url, target_domain)
                        ]
                        backlinks_found_list.extend(target_links)
                        
                        # Enqueue discovered links
                        for link in result.links_found:
                            link_domain = urlparse(link.target_url).netloc
                            if self.config.is_domain_allowed(link_domain):
                                await self.crawl_queue.enqueue_url(
                                    link.target_url,
                                    Priority.NORMAL,
                                    metadata={'depth': depth + 1},
                                    job_id=job_id
                                )
                
            except Exception as e:
                logger.error(f"Smart queue crawl failed: {e}")
                errors.append(CrawlError(
                    url=target_url,
                    error_type="QueueError",
                    message=str(e)
                ))
        
        else:
            # Fallback simple crawl
            logger.warning("No smart queue available, using simple crawl")
            crawled_urls_set: Set[str] = set()
            urls_to_crawl_list: List[Tuple[str, int]] = [(url, 0) for url in initial_seed_urls] # (url, depth)
            
            while urls_to_crawl_list and pages_crawled < self.config.max_pages:
                current_url, current_depth = urls_to_crawl_list.pop(0)
                
                if current_url in crawled_urls_set or current_depth >= self.config.max_depth:
                    continue
                
                logger.info(f"Fallback crawling: {current_url} (Depth: {current_depth})")
                result = await self.crawl_url(current_url, current_depth)
                crawled_urls_set.add(current_url)
                
                if result.error_message:
                    errors.append(CrawlError(
                        url=current_url,
                        error_type="FallbackCrawlError",
                        message=result.error_message
                    ))
                else:
                    pages_crawled += 1
                    total_links += len(result.links_found)
                    
                    target_links = [
                        link for link in result.links_found
                        if self._is_backlink_to_target(link, target_url, target_domain)
                    ]
                    backlinks_found_list.extend(target_links)
                    
                    for link in result.links_found:
                        link_domain = urlparse(link.target_url).netloc
                        if self.config.is_domain_allowed(link_domain):
                            urls_to_crawl_list.append((link.target_url, current_depth + 1))
        
        # Return comprehensive summary
        return CrawlResult(
            url=target_url,
            status_code=200, # Overall success status
            pages_crawled=pages_crawled,
            total_links_found=total_links,
            backlinks_found=len(backlinks_found_list),
            failed_urls_count=len(errors),
            is_final_summary=True,
            crawl_duration_seconds=time.time() - start_time,
            errors=errors,
            links_found=backlinks_found_list, # Return the list of backlinks found to target
            crawl_timestamp=datetime.now()
        )
    
    def _is_backlink_to_target(self, link: Backlink, target_url: str, target_domain: str) -> bool:
        """Check if link is a backlink to target"""
        link_domain = urlparse(link.target_url).netloc
        
        if link.target_url == target_url:
            return True
        if link_domain == target_domain:
            return True
        if link_domain.endswith('.' + target_domain):
            return True
        
        return False
    
    async def get_crawl_statistics(self) -> Dict[str, Any]:
        """Get comprehensive crawl statistics"""
        return {
            **self.stats,
            'uptime_seconds': time.time() - (self.stats['start_time'] or time.time()),
            'rate_limiter_stats': self.rate_limiter.get_statistics(),
            'circuit_breaker_health': self.resilience_manager.get_health_status(),
            'queue_stats': self.crawl_queue.get_queue_stats() if self.crawl_queue else None,
            'health_report': self.metrics.generate_health_report()
        }
