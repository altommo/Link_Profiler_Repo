"""
Web Crawler - Core crawling engine for link discovery
File: Link_Profiler/crawlers/web_crawler.py
"""

import asyncio
import aiohttp
import time
from typing import List, Dict, Set, Optional, AsyncGenerator, Tuple, Union # Added Union
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
    CrawlJob, ContentType, serialize_model, SEOMetrics, CrawlResult
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
        """
        Wait if needed to respect rate limits, adapting based on last crawl result and history.
        """
        current_delay = self.domain_delays.get(domain, self.initial_delay)

        if last_crawl_result:
            if domain not in self.domain_history:
                self.domain_history[domain] = deque(maxlen=self.history_size)
            self.domain_history[domain].append((last_crawl_result.status_code, last_crawl_result.crawl_time_ms))

            if self.ml_rate_optimization_enabled:
                recent_history = self.domain_history[domain]
                successful_responses = [r for r in recent_history if 200 <= r[0] < 400]
                # failed_responses = [r for r in recent_history if r[0] >= 400 or r[0] == 0] # Not directly used in calculation below

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
    """Main web crawler class"""
    
    def __init__(self, config: CrawlConfig, db: Database, job_id: str, ai_service: AIService, playwright_browser: Optional[Browser] = None):
        self.config = config
        self.db = db
        self.job_id = job_id
        self.ai_service = ai_service
        self.playwright_browser = playwright_browser
        
        self.rate_limiter = AdaptiveRateLimiter(
            initial_delay_seconds=self.config.delay_seconds,
            ml_rate_optimization_enabled=config_loader.get("anti_detection.ml_rate_optimization", False),
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

        if config_loader.get("proxy_management.enabled", False) and self.config.proxy_list:
            proxy_manager.load_proxies(
                self.config.proxy_list,
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
        if config_loader.get("anti_detection.request_header_randomization", False):
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
        
        if config_loader.get("anti_detection.human_like_delays", False):
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
        content_type = "text/html" # Default content type

        try:
            if self.config.render_javascript and self.playwright_browser:
                self.logger.info(f"Using Playwright to render JavaScript for: {url}")
                context_options = {
                    "user_agent": self.session.headers.get("User-Agent"),
                    "extra_http_headers": self.session.headers,
                    "viewport": {"width": random.randint(1200, 1600), "height": random.randint(800, 1200)}
                }
                if self.config.browser_fingerprint_randomization:
                    context_options.update({
                        "device_scale_factor": random.choice([1.0, 1.25, 1.5]),
                        "is_mobile": random.choice([True, False]),
                        "has_touch": random.choice([True, False]),
                        "screen": {
                            "width": random.randint(1366, 1920),
                            "height": random.randint(768, 1080)
                        },
                        "timezone_id": random.choice([
                            "America/New_York", "Europe/London", "Asia/Tokyo",
                            "America/Los_Angeles", "Europe/Berlin", "Asia/Shanghai"
                        ]),
                        "locale": random.choice(["en-US", "en-GB", "fr-FR", "de-DE", "ja-JP"]),
                        "color_scheme": random.choice(["light", "dark"]),
                    })

                browser_context = await self.playwright_browser.new_context(**context_options)
                if current_proxy:
                    await browser_context.set_proxy({"server": current_proxy})
                
                page = await browser_context.new_page()
                
                try:
                    if config_loader.get("anti_detection.stealth_mode", True):
                        from playwright_stealth import stealth_async
                        await stealth_async(page)

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

            else: # Use aiohttp for direct HTTP requests
                async with self.session.get(url, allow_redirects=self.config.follow_redirects, proxy=current_proxy) as response:
                    status_code = response.status
                    content = await response.read() # Read as bytes to handle images/PDFs
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

                    # New: Perform OCR on images found within HTML if enabled
                    if self.config.extract_image_text and self.ai_service.enabled:
                        soup = BeautifulSoup(content_str, 'lxml')
                        image_tags = soup.find_all('img', src=True)
                        for img_tag in image_tags:
                            img_url = urljoin(url, img_tag['src'])
                            # In a real scenario, you'd fetch the image bytes here.
                            # For this simulation, we'll just pass a dummy string or fetch a tiny placeholder.
                            # For now, let's simulate a generic OCR text for each image.
                            ocr_text_from_image = await ocr_processor.process_image(f"image_content_from_{img_url}", img_url)
                            if ocr_text_from_image:
                                if seo_metrics.ocr_text:
                                    seo_metrics.ocr_text += "\n" + ocr_text_from_image
                                else:
                                    seo_metrics.ocr_text = ocr_text_from_image
                                self.logger.debug(f"Extracted OCR text from image {img_url} on {url}.")


                elif 'image' in content_type and self.config.extract_image_text and self.ai_service.enabled:
                    # If the URL itself is an image and OCR is enabled
                    self.logger.info(f"Performing OCR on image URL: {url}")
                    ocr_text_from_image = await ocr_processor.process_image(content, url)
                    seo_metrics = SEOMetrics(url=url, audit_timestamp=current_crawl_timestamp, ocr_text=ocr_text_from_image)
                    seo_metrics.http_status = status_code
                    seo_metrics.response_time_ms = crawl_time_ms
                    seo_metrics.page_size_bytes = len(content)
                    seo_metrics.calculate_seo_score()
                    links = [] # No links from image content itself

                elif 'application/pdf' in content_type and self.config.extract_pdfs:
                    # PDF content is bytes, no direct link extraction from here yet
                    links = []
                
                # Common validation and anomaly detection for all content types
                if config_loader.get("quality_assurance.content_validation", False):
                    # Ensure content is string for content_validator
                    content_for_validation = content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content
                    validation_issues = self.content_validator.validate_crawl_result(url, content_for_validation, status_code)
                    if seo_metrics:
                        seo_metrics.validation_issues = validation_issues
                    if validation_issues:
                        self.logger.warning(f"Content validation issues for {url}: {validation_issues}")
                        if "CAPTCHA detected" in validation_issues or "Cloudflare 'Attention Required' page" in validation_issues:
                            if self.config.captcha_solving_enabled:
                                self.logger.info(f"CAPTCHA detected on {url}. Attempting to solve via external service (simulated).")
                                return CrawlResult(
                                    url=url,
                                    status_code=status_code,
                                    error_message="CAPTCHA_DETECTED_AND_SOLVING_ATTEMPTED",
                                    crawl_time_ms=crawl_time_ms,
                                    crawl_timestamp=current_crawl_timestamp,
                                    validation_issues=validation_issues
                                )
                            else:
                                self.logger.warning(f"CAPTCHA detected on {url}, but captcha_solving is disabled. Marking as blocked.")
                                return CrawlResult(
                                    url=url,
                                    status_code=status_code,
                                    error_message="CAPTCHA_DETECTED_AND_SOLVING_DISABLED",
                                    crawl_time_ms=crawl_time_ms,
                                    crawl_timestamp=current_crawl_timestamp,
                                    validation_issues=validation_issues
                                )
                
                if self.config.anomaly_detection_enabled:
                    current_crawl_result = CrawlResult(
                        url=url,
                        status_code=status_code,
                        content=content_for_validation if 'content_for_validation' in locals() else (content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content),
                        links_found=links,
                        crawl_time_ms=crawl_time_ms,
                        content_type=content_type,
                        validation_issues=validation_issues
                    )
                    anomaly_flags = anomaly_detector.detect_anomalies_for_crawl_result(current_crawl_result)
                    if anomaly_flags:
                        self.logger.warning(f"Anomalies detected for {url}: {anomaly_flags}")

                if config_loader.get("ai.content_classification_enabled", False) and self.ai_service.enabled:
                    classification = await self.ai_service.classify_content(content_for_validation if 'content_for_validation' in locals() else (content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content), url)
                    if seo_metrics:
                        seo_metrics.ai_content_classification = classification
                        self.logger.debug(f"AI content classification for {url}: {classification}")


            return CrawlResult(
                url=url,
                status_code=status_code,
                content=content, # Keep original content (str or bytes)
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
                content=b"", # No content on timeout
                error_message="Request timeout",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Request Timeout"]
            )
        except aiohttp.ClientProxyConnectionError as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"proxy_connection_error: {e}")
            return CrawlResult(
                url=url,
                status_code=502,
                content=b"", # No content on proxy error
                error_message=f"Proxy connection error: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Proxy Connection Error"]
            )
        except aiohttp.ClientResponseError as e:
            if current_proxy and e.status in [403, 407, 429, 500, 502, 503, 504]:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"http_status_{e.status}")
            return CrawlResult(
                url=url,
                status_code=e.status,
                content=b"", # No content on HTTP error
                error_message=f"HTTP error: {e.message}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=[f"HTTP Error {e.status}"]
            )
        except aiohttp.ClientError as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"client_error: {e}")
            return CrawlResult(
                url=url,
                status_code=0,
                content=b"", # No content on network error
                error_message=f"Network or client error: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Network Error"]
            )
        except Exception as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"unexpected_error: {e}")
            return CrawlResult(
                url=url,
                status_code=500,
                content=b"", # No content on unexpected error
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
    
    async def crawl_for_backlinks(self, target_url: str, initial_seed_urls: List[str]) -> AsyncGenerator[CrawlResult, None]:
        """
        Crawl web to find backlinks to target URL/domain.
        Starts with initial_seed_urls and explores up to max_depth.
        """
        target_domain = urlparse(target_url).netloc
        
        urls_to_visit = asyncio.Queue()
        for url in initial_seed_urls:
            await urls_to_visit.put((url, 0))
            
        self.crawled_urls.clear()
        self.failed_urls.clear()
        crawled_count = 0
        
        last_crawl_result: Optional[CrawlResult] = None

        while not urls_to_visit.empty() and crawled_count < self.config.max_pages:
            current_job = self.db.get_crawl_job(self.job_id)
            if current_job:
                if current_job.status == CrawlStatus.PAUSED:
                    self.logger.info(f"Crawler for job {self.job_id} paused. Waiting to resume...")
                    while True:
                        await asyncio.sleep(5)
                        rechecked_job = self.db.get_crawl_job(self.job_id)
                        if rechecked_job and rechecked_job.status == CrawlStatus.IN_PROGRESS:
                            self.logger.info(f"Crawler for job {self.job_id} resumed.")
                            break
                        elif rechecked_job and rechecked_job.status == CrawlStatus.STOPPED:
                            self.logger.info(f"Crawler for job {self.job_id} stopped during pause.")
                            return

            url, current_depth = await urls_to_visit.get()
            
            if url in self.crawled_urls:
                continue
            
            if current_depth >= self.config.max_depth:
                self.logger.debug(f"Skipping {url} due to max depth ({current_depth})")
                continue
            
            self.crawled_urls.add(url)
            crawled_count += 1
            
            self.logger.info(f"Crawling: {url} (Depth: {current_depth}, Crawled: {crawled_count}/{self.config.max_pages})")
            
            result = await self.crawl_url(url, last_crawl_result)
            last_crawl_result = result

            if result.error_message:
                self.logger.warning(f"Failed to crawl {url}: {result.error_message}")
                self.failed_urls.add(url)
                continue
            
            target_links = [link for link in result.links_found 
                            if self._is_link_to_target(link, target_url, target_domain)]
            
            if target_links:
                result.links_found = target_links
                yield result
            
            for link in result.links_found:
                parsed_link_url = urlparse(link.target_url)
                if self.config.is_domain_allowed(parsed_link_url.netloc):
                    if link.target_url not in self.crawled_urls and \
                       crawled_count + urls_to_visit.qsize() < self.config.max_pages:
                        await urls_to_visit.put((link.target_url, current_depth + 1))
    
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
