"""
Web Crawler - Core crawling engine for link discovery (FIXED VERSION)
File: Link_Profiler/crawlers/web_crawler_fixed.py
"""

import asyncio
import aiohttp
import time
from typing import List, Dict, Set, Optional, AsyncGenerator, Tuple, Union
from urllib.parse import urljoin, urlparse, urlencode
from urllib.robotparser import RobotFileParser
import logging
from dataclasses import dataclass, field
import re
from datetime import datetime, timedelta
import random
from collections import deque

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

from Link_Profiler.core.models import (
    URL, Backlink, CrawlConfig, CrawlStatus, LinkType, 
    CrawlJob, ContentType, serialize_model, SEOMetrics, CrawlResult, CrawlError
)
from Link_Profiler.database.database import Database
from .link_extractor import LinkExtractor
from .content_parser import ContentParser
from .robots_parser import RobotsParser
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.proxy_manager import proxy_manager
from Link_Profiler.utils.content_validator import ContentValidator
from Link_Profiler.utils.anomaly_detector import anomaly_detector
from Link_Profiler.utils.ocr_processor import ocr_processor
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.services.ai_service import AIService

# New imports for WebCrawler constructor parameters
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
import redis.asyncio as redis
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService
from Link_Profiler.services.link_health_service import LinkHealthService
from Link_Profiler.services.serp_service import SERPService
from Link_Profiler.services.keyword_service import KeywordService
from Link_Profiler.services.social_media_service import SocialMediaService
from Link_Profiler.services.web3_service import Web3Service
from Link_Profiler.services.link_building_service import LinkBuildingService
from Link_Profiler.services.report_service import ReportService


class CrawlerError(Exception):
    """Custom exception for crawler errors"""
    pass


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter to respect website policies and react to server responses.
    """
    
    def __init__(self, initial_delay_seconds: float = 1.0, ml_rate_optimization_enabled: bool = False, rate_limiter_config: Dict = None):
        self.domain_delays: Dict[str, float] = {}
        self.initial_delay = initial_delay_seconds
        self.last_request_time: Dict[str, float] = {}
        self.logger = logging.getLogger(__name__ + ".AdaptiveRateLimiter")

        self.ml_rate_optimization_enabled = ml_rate_optimization_enabled
        self.rate_limiter_config = rate_limiter_config or {}
        self.history_size = self.rate_limiter_config.get("history_size", 10)
        self.success_factor = self.rate_limiter_config.get("success_factor", 0.9)
        self.failure_factor = self.rate_limiter_config.get("failure_factor", 1.5)
        self.min_delay = self.rate_limiter_config.get("min_delay", 0.1)
        self.max_delay = self.rate_limiter_config.get("max_delay", 60.0)

        self.domain_history: Dict[str, deque[Tuple[int, int]]] = {}

    async def wait_if_needed(self, domain: str, last_crawl_result: Optional['CrawlResult'] = None) -> None:
        """Wait if needed to respect rate limits, adapting based on last crawl result and history."""
        current_delay = self.domain_delays.get(domain, self.initial_delay)

        if last_crawl_result:
            if domain not in self.domain_history:
                self.domain_history[domain] = deque(maxlen=self.history_size)
            self.domain_history[domain].append((last_crawl_result.status_code, last_crawl_result.crawl_time_ms))

            if self.ml_rate_optimization_enabled:
                recent_history = self.domain_history[domain]
                successful_responses = [r for r in recent_history if 200 <= r[0] < 400]
                success_ratio = len(successful_responses) / len(recent_history) if recent_history else 1.0
                avg_response_time = sum(r[1] for r in successful_responses) / len(successful_responses) if successful_responses else 0

                if last_crawl_result.status_code == 429:
                    current_delay *= self.failure_factor * 2
                    self.logger.warning(f"ML Rate Limiter: Doubling delay for {domain} due to 429. New delay: {current_delay:.2f}s")
                elif last_crawl_result.status_code >= 500 or last_crawl_result.status_code == 0:
                    current_delay *= self.failure_factor
                    self.logger.warning(f"ML Rate Limiter: Increasing delay for {domain} due to {last_crawl_result.status_code}. New delay: {current_delay:.2f}s")
                elif success_ratio < 0.7:
                    current_delay *= self.failure_factor
                    self.logger.info(f"ML Rate Limiter: Increasing delay for {domain} due to low success ratio ({success_ratio:.1f}). New delay: {current_delay:.2f}s")
                elif avg_response_time > 3000:
                    current_delay *= (1 + (avg_response_time / 10000))
                    self.logger.info(f"ML Rate Limiter: Increasing delay for {domain} due to high avg response time ({avg_response_time}ms). New delay: {current_delay:.2f}s")
                else:
                    current_delay = max(self.initial_delay, current_delay * self.success_factor)
                    self.logger.debug(f"ML Rate Limiter: Decreasing delay for {domain} due to good performance. New delay: {current_delay:.2f}s")
            else:
                if last_crawl_result.status_code == 429:
                    current_delay *= 2.0
                    self.logger.warning(f"Adaptive Rate Limiter: Doubling delay for {domain} due to 429. New delay: {current_delay:.2f}s")
                elif 500 <= last_crawl_result.status_code < 600:
                    current_delay *= 1.5
                    self.logger.warning(f"Adaptive Rate Limiter: Increasing delay for {domain} due to {last_crawl_result.status_code}. New delay: {current_delay:.2f}s")
                elif last_crawl_result.crawl_time_ms > 5000:
                    current_delay *= 1.2
                    self.logger.info(f"Adaptive Rate Limiter: Increasing delay for {domain} due to slow response ({last_crawl_result.crawl_time_ms}ms). New delay: {current_delay:.2f}s")
                else:
                    current_delay = max(self.initial_delay, current_delay * 0.9)
                    self.logger.debug(f"Adaptive Rate Limiter: Decreasing delay for {domain} due to good response. New delay: {current_delay:.2f}s")
            
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


class WebCrawler:
    """Main web crawler class with FIXED start_crawl method"""
    
    def __init__(self, 
                 database: Database, 
                 redis_client: Optional[redis.Redis], 
                 clickhouse_loader: Optional[ClickHouseLoader],
                 config: Dict,
                 anti_detection_config: Dict, 
                 proxy_config: Dict, 
                 quality_assurance_config: Dict, 
                 domain_analyzer_service: DomainAnalyzerService, 
                 ai_service: AIService, 
                 link_health_service: LinkHealthService, 
                 serp_service: SERPService, 
                 keyword_service: KeywordService, 
                 social_media_service: SocialMediaService, 
                 web3_service: Web3Service, 
                 link_building_service: LinkBuildingService, 
                 report_service: ReportService, 
                 playwright_browser: Optional[Browser] = None):
        
        self.db = database
        self.redis_client = redis_client
        self.clickhouse_loader = clickhouse_loader
        self.config = CrawlConfig.from_dict(config)
        self.anti_detection_config = anti_detection_config
        self.proxy_config = proxy_config
        self.quality_assurance_config = quality_assurance_config
        self.domain_analyzer_service = domain_analyzer_service
        self.ai_service = ai_service
        self.link_health_service = link_health_service
        self.serp_service = serp_service
        self.keyword_service = keyword_service
        self.social_media_service = social_media_service
        self.web3_service = web3_service
        self.link_building_service = link_building_service
        self.report_service = report_service
        self.playwright_browser = playwright_browser
        
        self.rate_limiter = AdaptiveRateLimiter(
            initial_delay_seconds=self.config.delay_seconds,
            ml_rate_optimization_enabled=self.anti_detection_config.get("ml_rate_optimization", False),
            rate_limiter_config=config_loader.get("rate_limiter")
        )
        self.robots_parser = RobotsParser()
        self.link_extractor = LinkExtractor()
        self.content_parser = ContentParser()
        self.content_validator = ContentValidator()
        self.session: Optional[aiohttp.ClientSession] = None
        self.crawled_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.logger = logging.getLogger(__name__)

        if self.proxy_config.get("use_proxies", False) and self.config.proxy_list:
            proxy_manager.load_proxies(
                self.config.proxy_list,
                self.proxy_config.get("proxy_retry_delay_seconds", 300)
            )
            self.use_proxies = True
            self.logger.info("WebCrawler initialized with proxy management enabled.")
        else:
            self.use_proxies = False
            self.logger.info("WebCrawler initialized without proxy management.")
        
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout_seconds,
            connect=10
        )
        
        headers = self.config.custom_headers.copy() if self.config.custom_headers else {}
        if self.anti_detection_config.get("request_header_randomization", False):
            random_headers = user_agent_manager.get_random_headers()
            headers.update(random_headers)
        elif self.config.user_agent_rotation:
            headers['User-Agent'] = user_agent_manager.get_random_user_agent()
        else:
            headers['User-Agent'] = self.config.user_agent

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        await self.robots_parser.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
        await self.robots_parser.__aexit__(exc_type, exc_val, exc_tb)
    
    async def crawl_url(self, url: str, last_crawl_result: Optional[CrawlResult] = None) -> CrawlResult:
        """Crawl a single URL and extract links"""
        start_time = time.time()
        current_crawl_timestamp = datetime.now()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        if not self.config.is_domain_allowed(domain):
            return CrawlResult(
                url=url,
                status_code=403,
                error_message="Domain not allowed by config",
                crawl_timestamp=current_crawl_timestamp
            )
        
        if self.config.respect_robots_txt:
            user_agent_for_robots = self.session.headers.get('User-Agent', self.config.user_agent)
            can_crawl = await self.robots_parser.can_fetch(url, user_agent_for_robots)
            if not can_crawl:
                return CrawlResult(
                    url=url,
                    status_code=403,
                    error_message="Blocked by robots.txt rules",
                    crawl_timestamp=current_crawl_timestamp
                )
        
        await self.rate_limiter.wait_if_needed(domain, last_crawl_result)
        
        if self.anti_detection_config.get("human_like_delays", False):
            await asyncio.sleep(random.uniform(0.1, 0.5))

        current_proxy = None
        if self.use_proxies:
            current_proxy = proxy_manager.get_next_proxy(desired_region=self.config.proxy_region)
            if current_proxy:
                self.logger.debug(f"Using proxy {current_proxy} for {url}")
            else:
                self.logger.warning(f"No available proxies for {url}. Proceeding without proxy.")

        content: Union[str, bytes] = ""
        links = []
        seo_metrics = None
        validation_issues = []
        anomaly_flags = []
        status_code = 0
        error_message = None
        redirect_url = None
        response_headers = {}
        content_type = "text/html"

        try:
            if self.config.render_javascript and self.playwright_browser:
                self.logger.info(f"Using Playwright to render JavaScript for: {url}")
                context_options = {
                    "user_agent": self.session.headers.get("User-Agent"),
                    "extra_http_headers": self.session.headers,
                    "viewport": {"width": random.randint(1200, 1600), "height": random.randint(800, 1200)}
                }
                
                browser_context = await self.playwright_browser.new_context(**context_options)
                if current_proxy:
                    await browser_context.set_proxy({"server": current_proxy})
                
                page = await browser_context.new_page()
                
                try:
                    response = await page.goto(url, wait_until="networkidle", timeout=self.config.timeout_seconds * 1000)
                    
                    status_code = response.status if response else 0
                    content = await page.content()
                    response_headers = await response.all_headers() if response else {}
                    redirect_url = page.url if page.url != url else None
                    content_type = response_headers.get('content-type', '').lower()

                    await page.close()
                    await browser_context.close()

                except Exception as e:
                    error_message = f"Playwright rendering error: {e}"
                    status_code = 500
                    self.logger.error(f"Playwright failed to crawl {url}: {e}", exc_info=True)
                    if current_proxy:
                        proxy_manager.mark_proxy_bad(current_proxy, reason=f"playwright_error: {e}")
                    await page.close()
                    await browser_context.close()
                    raise

            else:  # Use aiohttp for direct HTTP requests
                async with self.session.get(url, allow_redirects=self.config.follow_redirects, proxy=current_proxy) as response:
                    status_code = response.status
                    content = await response.read()
                    response_headers = dict(response.headers)
                    redirect_url = str(response.url) if str(response.url) != url else None
                    content_type = response.headers.get('content-type', '').lower()

            crawl_time_ms = int((time.time() - start_time) * 1000)
            
            # Process content based on type
            if 'text/html' in content_type:
                content_str = content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content
                links = await self._extract_links_from_html(url, content_str)
                
                for link in links:
                    link.http_status = status_code
                    link.crawl_timestamp = current_crawl_timestamp

                seo_metrics = await self.content_parser.parse_seo_metrics(url, content_str)
                
                if seo_metrics:
                    seo_metrics.http_status = status_code
                    seo_metrics.response_time_ms = crawl_time_ms
                    content_length_header = response_headers.get('Content-Length')
                    if content_length_header:
                        try:
                            seo_metrics.page_size_bytes = int(content_length_header)
                        except ValueError:
                            self.logger.warning(f"Invalid Content-Length header for {url}: {content_length_header}")
                            seo_metrics.page_size_bytes = len(content_str.encode('utf-8'))
                    else:
                        seo_metrics.page_size_bytes = len(content_str.encode('utf-8'))

            return CrawlResult(
                url=url,
                status_code=status_code,
                content=content,
                headers=response_headers,
                links_found=links,
                redirect_url=redirect_url,
                crawl_time_ms=crawl_time_ms,
                content_type=content_type,
                seo_metrics=seo_metrics,
                crawl_timestamp=current_crawl_timestamp,
                validation_issues=validation_issues,
                anomaly_flags=anomaly_flags
            )
                
        except asyncio.TimeoutError:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason="timeout")
            return CrawlResult(
                url=url,
                status_code=408,
                content=b"",
                error_message="Request timeout",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Request Timeout"]
            )
        except Exception as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"unexpected_error: {e}")
            return CrawlResult(
                url=url,
                status_code=500,
                content=b"",
                error_message=f"Unexpected error during crawl: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Unexpected Error"]
            )
    
    async def _extract_links_from_html(self, source_url: str, html_content: str) -> List[Backlink]:
        """Extract links from HTML content"""
        try:
            return await self.link_extractor.extract_links(source_url, html_content)
        except Exception as e:
            self.logger.error(f"Error extracting links from {source_url}: {e}")
            return []
    
    async def start_crawl(self, target_url: str, initial_seed_urls: List[str], job_id: str) -> AsyncGenerator[CrawlResult, None]:
        """
        FIXED: Crawl web to find backlinks to target URL/domain.
        Always returns a final summary result with crawl statistics.
        """
        target_domain = urlparse(target_url).netloc
        crawl_start_time = time.time()
        
        # Track comprehensive crawl statistics
        crawl_stats = {
            'pages_crawled': 0,
            'total_links_found': 0,
            'backlinks_found': 0,
            'failed_urls_count': 0,
            'errors': [],
            'domains_visited': set(),
            'status_codes': {},
            'avg_response_time': 0,
            'total_response_time': 0
        }
        
        urls_to_visit = asyncio.Queue()
        for url in initial_seed_urls:
            await urls_to_visit.put((url, 0))
            
        self.crawled_urls.clear()
        self.failed_urls.clear()
        crawled_count = 0
        
        last_crawl_result: Optional[CrawlResult] = None
        backlinks_yielded = 0

        self.logger.info(f"Starting crawl for target: {target_url} with {len(initial_seed_urls)} seed URLs")

        while not urls_to_visit.empty() and crawled_count < self.config.max_pages:
            # Check job status for pause/stop
            current_job = self.db.get_crawl_job(job_id)
            if current_job:
                if current_job.status == CrawlStatus.PAUSED:
                    self.logger.info(f"Crawler for job {job_id} paused. Waiting to resume...")
                    while True:
                        await asyncio.sleep(5)
                        rechecked_job = self.db.get_crawl_job(job_id)
                        if rechecked_job and rechecked_job.status == CrawlStatus.IN_PROGRESS:
                            self.logger.info(f"Crawler for job {job_id} resumed.")
                            break
                        elif rechecked_job and rechecked_job.status == CrawlStatus.STOPPED:
                            self.logger.info(f"Crawler for job {job_id} stopped during pause.")
                            break
                elif current_job.status == CrawlStatus.STOPPED:
                    self.logger.info(f"Crawler for job {job_id} stopped.")
                    break

            url, current_depth = await urls_to_visit.get()
            
            if url in self.crawled_urls:
                continue
            
            if current_depth >= self.config.max_depth:
                self.logger.debug(f"Skipping {url} due to max depth ({current_depth})")
                continue
            
            self.crawled_urls.add(url)
            crawled_count += 1
            crawl_stats['pages_crawled'] = crawled_count
            
            self.logger.info(f"Crawling: {url} (Depth: {current_depth}, Crawled: {crawled_count}/{self.config.max_pages})")
            
            result = await self.crawl_url(url, last_crawl_result)
            last_crawl_result = result

            # Update statistics
            parsed_url = urlparse(url)
            crawl_stats['domains_visited'].add(parsed_url.netloc)
            
            if result.status_code in crawl_stats['status_codes']:
                crawl_stats['status_codes'][result.status_code] += 1
            else:
                crawl_stats['status_codes'][result.status_code] = 1
            
            if result.crawl_time_ms:
                crawl_stats['total_response_time'] += result.crawl_time_ms
                crawl_stats['avg_response_time'] = crawl_stats['total_response_time'] / crawled_count

            if result.error_message:
                self.logger.warning(f"Failed to crawl {url}: {result.error_message}")
                self.failed_urls.add(url)
                crawl_stats['failed_urls_count'] = len(self.failed_urls)
                crawl_stats['errors'].append(CrawlError(
                    timestamp=datetime.now(),
                    url=url,
                    error_type="CrawlError",
                    message=result.error_message
                ))
                continue
            
            # Count all links found
            crawl_stats['total_links_found'] += len(result.links_found)
            
            # Check for backlinks to target
            target_links = [link for link in result.links_found 
                            if self._is_link_to_target(link, target_url, target_domain)]
            
            if target_links:
                crawl_stats['backlinks_found'] += len(target_links)
                backlinks_yielded += 1
                
                # Create a result with only target links for yielding
                target_result = CrawlResult(
                    url=result.url,
                    status_code=result.status_code,
                    content=result.content,
                    headers=result.headers,
                    links_found=target_links,
                    redirect_url=result.redirect_url,
                    crawl_time_ms=result.crawl_time_ms,
                    content_type=result.content_type,
                    seo_metrics=result.seo_metrics,
                    crawl_timestamp=result.crawl_timestamp,
                    validation_issues=result.validation_issues,
                    anomaly_flags=result.anomaly_flags,
                    is_final_summary=False
                )
                
                self.logger.info(f"Found {len(target_links)} backlinks to {target_domain} on {url}")
                yield target_result
            
            # Add discovered links to crawl queue
            for link in result.links_found:
                parsed_link_url = urlparse(link.target_url)
                if self.config.is_domain_allowed(parsed_link_url.netloc):
                    if link.target_url not in self.crawled_urls and \
                       crawled_count + urls_to_visit.qsize() < self.config.max_pages:
                        await urls_to_visit.put((link.target_url, current_depth + 1))

        # CRITICAL FIX: Always yield a final summary result
        crawl_duration = time.time() - crawl_start_time
        
        final_result = CrawlResult(
            url=target_url,
            status_code=200,  # Successful crawl completion
            content="",
            headers={},
            links_found=[],
            pages_crawled=crawl_stats['pages_crawled'],
            total_links_found=crawl_stats['total_links_found'],
            backlinks_found=crawl_stats['backlinks_found'],
            failed_urls_count=crawl_stats['failed_urls_count'],
            errors=crawl_stats['errors'],
            crawl_duration_seconds=crawl_duration,
            domains_visited_count=len(crawl_stats['domains_visited']),
            avg_response_time_ms=crawl_stats['avg_response_time'],
            status_code_distribution=crawl_stats['status_codes'],
            crawl_timestamp=datetime.now(),
            is_final_summary=True
        )
        
        self.logger.info(f"Crawl completed for {target_url}: "
                        f"{crawl_stats['pages_crawled']} pages crawled, "
                        f"{crawl_stats['backlinks_found']} backlinks found, "
                        f"{crawl_stats['failed_urls_count']} failures, "
                        f"{crawl_duration:.2f}s duration")
        
        yield final_result
    
    def _is_link_to_target(self, link: Backlink, target_url: str, target_domain: str) -> bool:
        """Check if a link points to our target URL or domain"""
        link_domain = urlparse(link.target_url).netloc
        
        if link.target_url == target_url:
            return True
        
        if link_domain == target_domain:
            return True
        
        if link_domain.endswith('.' + target_domain):
            return True
            
        return False
