"""
Web Crawler - Core crawling engine for link discovery
File: Link_Profiler/crawlers/web_crawler.py
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
    CrawlJob, ContentType, serialize_model, SEOMetrics, CrawlResult, CrawlError # Import CrawlError
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
from Link_Profiler.config.config_loader import config_loader # Keep this for now, but try to remove direct usage
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

# ADD these imports at the top
from Link_Profiler.utils.circuit_breaker import ResilienceManager, CircuitBreakerOpenError
from Link_Profiler.utils.adaptive_rate_limiter import MLRateLimiter
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue, Priority
from Link_Profiler.monitoring.crawler_metrics import crawler_metrics
from Link_Profiler.monitoring.health_monitor import HealthMonitor


class CrawlerError(Exception):
    """Custom exception for crawler errors"""
    pass


# REMOVED AdaptiveRateLimiter class as it's replaced by MLRateLimiter in utils/adaptive_rate_limiter.py


class WebCrawler:
    """Main web crawler class"""
    
    def __init__(self, 
                 database: Database, 
                 redis_client: Optional[redis.Redis], 
                 clickhouse_loader: Optional[ClickHouseLoader],
                 config: Dict, # This will be the raw dict from config_loader.get("crawler")
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
                 playwright_browser: Optional[Browser] = None,
                 crawl_queue: SmartCrawlQueue = None): # ADD this parameter
        
        self.db = database
        self.redis_client = redis_client
        self.clickhouse_loader = clickhouse_loader
        self.config = CrawlConfig.from_dict(config) # Convert the dict to CrawlConfig
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
        
        # REPLACE the existing AdaptiveRateLimiter with MLRateLimiter
        self.rate_limiter = MLRateLimiter()

        # ADD these lines
        self.resilience_manager = ResilienceManager()
        self.crawl_queue = crawl_queue
        self.metrics = crawler_metrics
        self.health_monitor = HealthMonitor(self.metrics)
        
        self.robots_parser = RobotsParser()
        self.link_extractor = LinkExtractor()
        self.content_parser = ContentParser()
        self.content_validator = ContentValidator()
        self.session: Optional[aiohttp.ClientSession] = None
        self.crawled_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.logger = logging.getLogger(__name__)

        if self.proxy_config.get("use_proxies", False) and self.config.proxy_list: # Use self.proxy_config
            proxy_manager.load_proxies(
                self.config.proxy_list,
                self.proxy_config.get("proxy_retry_delay_seconds", 300) # Use self.proxy_config
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
        
        # User Agent Rotation Logic
        if self.anti_detection_config.get("user_agent_rotation", False):
            if self.anti_detection_config.get("consistent_ua_per_domain", False):
                # This logic needs to be per-request in crawl_url, not here.
                # For __aenter__, we just set a default random one.
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()
            else:
                headers['User-Agent'] = user_agent_manager.get_random_user_agent()
        else:
            headers['User-Agent'] = self.config.user_agent

        if self.anti_detection_config.get("request_header_randomization", False):
            random_headers = user_agent_manager.get_random_headers()
            # Only update specific headers that are randomized, not overwrite all
            headers['Accept'] = random_headers.get('Accept', headers.get('Accept'))
            headers['Accept-Language'] = random_headers.get('Accept-Language', headers.get('Accept-Language'))
            headers['Accept-Encoding'] = random_headers.get('Accept-Encoding', headers.get('Accept-Encoding'))
            headers['DNT'] = random_headers.get('DNT', headers.get('DNT'))
            headers['Connection'] = random_headers.get('Connection', headers.get('Connection'))
            headers['Upgrade-Insecure-Requests'] = random_headers.get('Upgrade-Insecure-Requests', headers.get('Upgrade-Insecure-Requests'))
            headers['Sec-Fetch-Dest'] = random_headers.get('Sec-Fetch-Dest', headers.get('Sec-Fetch-Dest'))
            headers['Sec-Fetch-Mode'] = random_headers.get('Sec-Fetch-Mode', headers.get('Sec-Fetch-Mode'))
            headers['Sec-Fetch-Site'] = random_headers.get('Sec-Fetch-Site', headers.get('Sec-Fetch-Site'))
            headers['Sec-Fetch-User'] = random_headers.get('Sec-Fetch-User', headers.get('Sec-Fetch-User'))


        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=headers
        )
        await self.robots_parser.__aenter__()
        # ADD this line after existing __aenter__ code
        await self.health_monitor.start_monitoring()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # ADD this line before existing __aexit__ code
        self.health_monitor.stop_monitoring()
        if self.session:
            await self.session.close()
        await self.robots_parser.__aexit__(exc_type, exc_val, exc_tb)
    
    async def crawl_url(self, url: str, last_crawl_result: Optional[CrawlResult] = None) -> CrawlResult:
        """REPLACE the entire crawl_url method with this resilient version"""
        try:
            return await self.resilience_manager.execute_with_resilience(
                self._crawl_url_internal, url, last_crawl_result
            )
        except CircuitBreakerOpenError as e:
            self.logger.warning(f"Circuit breaker open for {url}: {e}")
            return CrawlResult(
                url=url,
                status_code=503,
                error_message=str(e),
                crawl_time_ms=0,
                crawl_timestamp=datetime.now(),
                anomaly_flags=["Circuit Breaker Open"]
            )
        except Exception as e:
            self.logger.error(f"Resilience manager error for {url}: {e}", exc_info=True)
            return CrawlResult(
                url=url,
                status_code=500,
                error_message=f"Resilience manager error: {str(e)}",
                crawl_time_ms=0,
                crawl_timestamp=datetime.now(),
                anomaly_flags=["Resilience Manager Error"]
            )
    
    async def _crawl_url_internal(self, url: str, last_crawl_result: Optional[CrawlResult] = None) -> CrawlResult:
        """RENAME your existing crawl_url method to this name"""
        start_time = time.time()
        current_crawl_timestamp = datetime.now()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        self.logger.debug(f"Attempting to crawl_url: {url}")

        # Track request start
        request_context = await self.metrics.track_request_start(url)

        if not self.config.is_domain_allowed(domain):
            self.logger.warning(f"Skipping {url}: Domain '{domain}' not allowed by config.")
            result = CrawlResult(
                url=url,
                status_code=403,
                error_message=f"Domain '{domain}' not allowed by config",
                crawl_timestamp=current_crawl_timestamp
            )
            await self.metrics.track_request_complete(url, result, request_context)
            return result
        
        if self.config.respect_robots_txt:
            user_agent_for_robots = self.session.headers.get('User-Agent', self.config.user_agent)
            self.logger.debug(f"Checking robots.txt for {url} with user agent: {user_agent_for_robots}")
            can_crawl = await self.robots_parser.can_fetch(url, user_agent_for_robots)
            self.logger.debug(f"Robots.txt check for {url}: can_crawl={can_crawl}")
            if not can_crawl:
                self.logger.warning(f"Skipping {url}: Blocked by robots.txt rules.")
                result = CrawlResult(
                    url=url,
                    status_code=403,
                    error_message="Blocked by robots.txt rules",
                    crawl_timestamp=current_crawl_timestamp
                )
                await self.metrics.track_request_complete(url, result, request_context)
                return result
        
        # REPLACE this line
        # await self.rate_limiter.wait_if_needed(domain, last_crawl_result)
        # WITH this line
        await self.rate_limiter.adaptive_wait(domain, last_crawl_result)
        
        # Random delays
        if self.anti_detection_config.get("human_like_delays", False) and self.anti_detection_config.get("random_delay_range"):
            delay = random.uniform(*self.anti_detection_config["random_delay_range"])
            await asyncio.sleep(delay)
        elif self.anti_detection_config.get("human_like_delays", False): # Fallback if range not specified
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
            # Prepare headers for this specific request (including potential rotation)
            request_headers = self.session.headers.copy() # Start with session's default headers
            if self.anti_detection_config.get("user_agent_rotation", False):
                if self.anti_detection_config.get("consistent_ua_per_domain", False):
                    request_headers['User-Agent'] = user_agent_manager.get_user_agent_for_domain(domain)
                else:
                    request_headers['User-Agent'] = user_agent_manager.get_random_user_agent()
            
            if self.anti_detection_config.get("request_header_randomization", False):
                random_headers = user_agent_manager.get_random_headers()
                request_headers.update(random_headers) # Update with randomized headers

            if self.config.render_javascript and self.playwright_browser:
                self.logger.info(f"Using Playwright to render JavaScript for: {url}")
                context_options = {
                    "user_agent": request_headers.get("User-Agent"), # Use the potentially rotated UA
                    "extra_http_headers": request_headers, # Use the potentially randomized headers
                    "viewport": {"width": random.randint(1200, 1600), "height": random.randint(800, 1200)}
                }
                if self.anti_detection_config.get("browser_fingerprint_randomization", False): # Use self.anti_detection_config
                    context_options.update({
                        "device_scale_factor": random.choice([1.0, 1.25, 1.5]),
                        "is_mobile": random.choice([True, False]),
                        "has_touch": random.choice([True, False]),
                        "screen": {
                            "width": random.randint(1366, 1920),
                            "height": random.randint(768, 1080)
                        },
                        "timezone_id": random.choice(["America/New_York", "Europe/London", "Asia/Tokyo", "America/Los_Angeles", "Europe/Berlin", "Asia/Shanghai"]),
                        "locale": random.choice(["en-US", "en-GB", "fr-FR", "de-DE", "ja-JP"]),
                        "color_scheme": random.choice(["light", "dark"]),
                    })

                browser_context = await self.playwright_browser.new_context(**context_options)
                if current_proxy:
                    await browser_context.set_proxy({"server": current_proxy})
                
                page = await browser_context.new_page()
                
                try:
                    if self.anti_detection_config.get("stealth_mode", True): # Use self.anti_detection_config
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
                async with self.session.get(url, allow_redirects=self.config.follow_redirects, proxy=current_proxy, headers=request_headers) as response: # Pass request_headers
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

                    # New: Perform NLP content analysis if enabled
                    # Check if AI service is enabled and if the specific feature is enabled via AI service's internal config
                    if self.ai_service.enabled and self.ai_service.is_nlp_analysis_enabled(): # Assuming AIService has this method
                        nlp_results = await self.ai_service.analyze_content_nlp(content_str)
                        if nlp_results:
                            seo_metrics.nlp_entities = nlp_results.get("entities", [])
                            seo_metrics.nlp_sentiment = nlp_results.get("sentiment")
                            seo_metrics.nlp_topics = nlp_results.get("topics", [])
                            self.logger.debug(f"NLP analysis for {url}: Sentiment={nlp_results.get('sentiment')}, Topics={nlp_results.get('topics')}")

                    # New: Perform video content analysis if enabled and video tags are found
                    if self.config.extract_video_content and self.ai_service.enabled and self.ai_service.is_video_analysis_enabled(): # Assuming AIService has this method
                        soup = BeautifulSoup(content_str, 'lxml')
                        video_tags = soup.find_all('video', src=True)
                        if video_tags:
                            self.logger.info(f"Video content detected on {url}. Simulating video analysis.")
                            # In a real scenario, you'd fetch video stream/metadata and send to a video analysis API.
                            # For now, simulate a generic video analysis result.
                            video_analysis_results = await self.ai_service.analyze_video_content(url)
                            if video_analysis_results:
                                seo_metrics.video_transcription = video_analysis_results.get("transcription")
                                seo_metrics.video_topics = video_analysis_results.get("topics", [])
                                self.logger.debug(f"Video analysis for {url}: Topics={video_analysis_results.get('topics')}")


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

                elif 'video' in content_type and self.config.extract_video_content and self.ai_service.enabled and self.ai_service.is_video_analysis_enabled(): # Assuming AIService has this method
                    # If the URL itself is a video and video analysis is enabled
                    self.logger.info(f"Performing video analysis on video URL: {url}")
                    video_analysis_results = await self.ai_service.analyze_video_content(url)
                    seo_metrics = SEOMetrics(url=url, audit_timestamp=current_crawl_timestamp)
                    if video_analysis_results:
                        seo_metrics.video_transcription = video_analysis_results.get("transcription")
                        seo_metrics.video_topics = video_analysis_results.get("topics", [])
                    seo_metrics.http_status = status_code
                    seo_metrics.response_time_ms = crawl_time_ms
                    seo_metrics.page_size_bytes = len(content)
                    seo_metrics.calculate_seo_score()
                    links = [] # No links from video content itself

                elif 'application/pdf' in content_type and self.config.extract_pdfs:
                    # PDF content is bytes, no direct link extraction from here yet
                    links = []
                
                # Common validation and anomaly detection for all content types
                if self.quality_assurance_config.get("content_validation", False): # Use self.quality_assurance_config
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
                                result = CrawlResult(
                                    url=url,
                                    status_code=status_code,
                                    error_message="CAPTCHA_DETECTED_AND_SOLVING_ATTEMPTED",
                                    crawl_time_ms=crawl_time_ms,
                                    crawl_timestamp=current_crawl_timestamp,
                                    validation_issues=validation_issues
                                )
                                await self.metrics.track_request_complete(url, result, request_context)
                                return result
                            else:
                                self.logger.warning(f"CAPTCHA detected on {url}, but captcha_solving is disabled. Marking as blocked.")
                                result = CrawlResult(
                                    url=url,
                                    status_code=status_code,
                                    error_message="CAPTCHA_DETECTED_AND_SOLVING_DISABLED",
                                    crawl_time_ms=crawl_time_ms,
                                    crawl_timestamp=current_crawl_timestamp,
                                    validation_issues=validation_issues
                                )
                                await self.metrics.track_request_complete(url, result, request_context)
                                return result
                
                if self.anti_detection_config.get("anomaly_detection_enabled", False): # Use self.anti_detection_config
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

                if self.ai_service.enabled and self.ai_service.is_content_classification_enabled(): # Assuming AIService has this method
                    classification = await self.ai_service.classify_content(content_for_validation if 'content_for_validation' in locals() else (content.decode('utf-8', errors='ignore') if isinstance(content, bytes) else content), url)
                    if seo_metrics:
                        seo_metrics.ai_content_classification = classification
                        self.logger.debug(f"AI content classification for {url}: {classification}")

            result = CrawlResult(
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
            await self.metrics.track_request_complete(url, result, request_context)
            return result
                
        except asyncio.TimeoutError:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason="timeout")
            result = CrawlResult(
                url=url,
                status_code=408,
                content=b"", # No content on timeout
                error_message="Request timeout",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Request Timeout"]
            )
            await self.metrics.track_request_complete(url, result, request_context)
            raise # Re-raise to be caught by resilience manager
        except aiohttp.ClientProxyConnectionError as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"proxy_connection_error: {e}")
            result = CrawlResult(
                url=url,
                status_code=502,
                content=b"", # No content on proxy error
                error_message=f"Proxy connection error: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Proxy Connection Error"]
            )
            await self.metrics.track_request_complete(url, result, request_context)
            raise # Re-raise to be caught by resilience manager
        except aiohttp.ClientResponseError as e:
            if current_proxy and e.status in [403, 407, 429, 500, 502, 503, 504]:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"http_status_{e.status}")
            result = CrawlResult(
                url=url,
                status_code=e.status,
                content=b"", # No content on HTTP error
                error_message=f"HTTP error: {e.message}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=[f"HTTP Error {e.status}"]
            )
            await self.metrics.track_request_complete(url, result, request_context)
            raise # Re-raise to be caught by resilience manager
        except aiohttp.ClientError as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"client_error: {e}")
            result = CrawlResult(
                url=url,
                status_code=0,
                content=b"", # No content on network error
                error_message=f"Network or client error: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Network Error"]
            )
            await self.metrics.track_request_complete(url, result, request_context)
            raise # Re-raise to be caught by resilience manager
        except Exception as e:
            if current_proxy:
                proxy_manager.mark_proxy_bad(current_proxy, reason=f"unexpected_error: {e}")
            result = CrawlResult(
                url=url,
                status_code=500,
                content=b"", # No content on unexpected error
                error_message=f"Unexpected error during crawl: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000),
                crawl_timestamp=current_crawl_timestamp,
                anomaly_flags=["Unexpected Error"]
            )
            await self.metrics.track_request_complete(url, result, request_context)
            raise # Re-raise to be caught by resilience manager
    
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
    
    async def _extract_links_from_html(self, source_url: str, html_content: str) -> List[Backlink]:
        """Extract links from HTML content"""
        try:
            return await self.link_extractor.extract_links(source_url, html_content)
        except Exception as e:
            self.logger.error(f"Error extracting links from {source_url}: {e}")
            return []

    async def start_crawl(self, target_url: str, initial_seed_urls: List[str], job_id: str) -> CrawlResult: # Changed return type to CrawlResult
        """
        Crawl web to find backlinks to target URL/domain.
        Starts with initial_seed_urls and returns a final summary result.
        """
        start_crawl_time = time.time() # Overall crawl start time
        target_domain = urlparse(target_url).netloc
        
        # Handle empty seed URLs by using target URL
        if not initial_seed_urls:
            self.logger.info(f"Job {job_id}: No seed URLs provided, using target URL as starting seed")
            initial_seed_urls = [target_url]
        elif not any(initial_seed_urls):  # Handle list of empty strings
            self.logger.info(f"Job {job_id}: All seed URLs empty, using target URL as starting seed")
            initial_seed_urls = [target_url]

        self.logger.info(f"Job {job_id}: Final seed URLs: {initial_seed_urls}")

        # urls_to_visit = asyncio.Queue() # REMOVED
        # for url in initial_seed_urls: # REMOVED
        #     await urls_to_visit.put((url, 0)) # REMOVED
        #     self.logger.info(f"Job {job_id}: Added seed URL to queue: {url}") # Debug log for seed URLs # REMOVED
            
        self.crawled_urls.clear()
        self.failed_urls.clear()
        
        # Track crawl statistics
        pages_crawled_count = 0
        total_links_found_count = 0
        backlinks_found_list: List[Backlink] = [] # Store actual Backlink objects
        crawl_errors_list: List[CrawlError] = [] # Store CrawlError objects
        
        last_crawl_result: Optional[CrawlResult] = None

        self.logger.info(f"Job {job_id}: Starting crawl for {target_url}")
        self.logger.info(f"Job {job_id}: Seed URLs: {initial_seed_urls}")
        self.logger.info(f"Job {job_id}: Config - max_pages: {self.config.max_pages}, max_depth: {self.config.max_depth}")
        self.logger.info(f"Job {job_id}: Target domain: {target_domain}")
        # self.logger.info(f"Job {job_id}: Total URLs in queue after seeding: {urls_to_visit.qsize()}") # REMOVED

        # REPLACE the existing URL queue logic with:
        if self.crawl_queue:
            # Use smart queue system
            self.logger.info(f"Job {job_id}: Using SmartCrawlQueue.")
            for url in initial_seed_urls:
                await self.crawl_queue.enqueue_url(url, Priority.HIGH, job_id=job_id)
            
            while pages_crawled_count < self.config.max_pages:
                current_job = self.db.get_crawl_job(job_id)
                if current_job and current_job.status == CrawlStatus.PAUSED:
                    self.logger.info(f"Crawler for job {job_id} paused. Waiting to resume...")
                    while True:
                        await asyncio.sleep(5)
                        rechecked_job = self.db.get_crawl_job(job_id)
                        if rechecked_job and rechecked_job.status == CrawlStatus.IN_PROGRESS:
                            self.logger.info(f"Crawler for job {job_id} resumed.")
                            break
                        elif rechecked_job and rechecked_job.status == CrawlStatus.STOPPED:
                            self.logger.info(f"Crawler for job {job_id} stopped during pause.")
                            # Return a partial summary if stopped
                            return CrawlResult(
                                url=target_url,
                                status_code=200, # Indicate successful stop
                                pages_crawled=pages_crawled_count,
                                total_links_found=total_links_found_count,
                                backlinks_found=len(backlinks_found_list),
                                failed_urls_count=len(self.failed_urls),
                                is_final_summary=True,
                                crawl_duration_seconds=time.time() - start_crawl_time,
                                errors=crawl_errors_list,
                                error_message="Crawl stopped by command."
                            )

                task = await self.crawl_queue.get_next_task()
                if not task:
                    self.logger.debug(f"Job {job_id}: No more tasks in SmartCrawlQueue. Breaking loop.")
                    break # No more tasks to process

                url = task.url
                current_depth = task.metadata.get('depth', 0) # Assuming depth is stored in metadata

                self.logger.info(f"Job {job_id}: Processing URL: {url} at depth {current_depth}")
                
                if url in self.crawled_urls:
                    self.logger.debug(f"Skipping {url}: Already crawled.")
                    await self.crawl_queue.mark_task_completed(task, success=True) # Mark as completed even if skipped
                    continue
                
                if current_depth >= self.config.max_depth:
                    self.logger.debug(f"Skipping {url} due to max depth ({current_depth})")
                    await self.crawl_queue.mark_task_completed(task, success=True) # Mark as completed even if skipped
                    continue
                
                # Mark as crawled before attempting to fetch to prevent re-adding to queue
                self.crawled_urls.add(url) 
                
                self.logger.info(f"Attempting to crawl: {url} (Depth: {current_depth}, Crawled: {pages_crawled_count}/{self.config.max_pages})")
                
                result = await self._crawl_url_internal(url, last_crawl_result) # Call internal method
                last_crawl_result = result

                if result.error_message:
                    self.logger.warning(f"Failed to crawl {url}: {result.error_message}")
                    self.failed_urls.add(url)
                    crawl_errors_list.append(CrawlError(url=url, error_type="CrawlError", message=result.error_message))
                    await self.crawl_queue.mark_task_completed(task, success=False) # Mark as failed for retry
                    # Do NOT increment pages_crawled_count for failed attempts that didn't yield content
                    continue
                
                # Only increment pages_crawled_count for successfully fetched pages
                pages_crawled_count += 1 
                self.logger.info(f"Successfully crawled: {url}. Total pages crawled: {pages_crawled_count}")
                await self.crawl_queue.mark_task_completed(task, success=True) # Mark as successfully completed

                total_links_found_count += len(result.links_found)

                target_links = [link for link in result.links_found 
                                if self._is_link_to_target(link, target_url, target_domain)]
                
                if target_links:
                    backlinks_found_list.extend(target_links)
                    self.logger.info(f"Found {len(target_links)} backlinks to target on {url}.")
                
                for link in result.links_found:
                    parsed_link_url = urlparse(link.target_url)
                    if self.config.is_domain_allowed(parsed_link_url.netloc):
                        # Enqueue new links with incremented depth
                        await self.crawl_queue.enqueue_url(
                            link.target_url, 
                            Priority.NORMAL, 
                            metadata={'depth': current_depth + 1}, 
                            job_id=job_id
                        )
        else:
            # Fallback to existing queue logic if SmartCrawlQueue is not provided
            self.logger.warning(f"Job {job_id}: SmartCrawlQueue not provided. Falling back to basic queue logic.")
            urls_to_visit = asyncio.Queue()
            for url in initial_seed_urls:
                await urls_to_visit.put((url, 0))
                self.logger.info(f"Job {job_id}: Added seed URL to basic queue: {url}")

            while not urls_to_visit.empty() and pages_crawled_count < self.config.max_pages:
                self.logger.info(f"Job {job_id}: Basic Queue size: {urls_to_visit.qsize()}, Crawled: {pages_crawled_count}/{self.config.max_pages}")

                current_job = self.db.get_crawl_job(job_id) # Use passed job_id
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
                                # Return a partial summary if stopped
                                return CrawlResult(
                                    url=target_url,
                                    status_code=200, # Indicate successful stop
                                    pages_crawled=pages_crawled_count,
                                    total_links_found=total_links_found_count,
                                    backlinks_found=len(backlinks_found_list),
                                    failed_urls_count=len(self.failed_urls),
                                    is_final_summary=True,
                                    crawl_duration_seconds=time.time() - start_crawl_time,
                                    errors=crawl_errors_list,
                                    error_message="Crawl stopped by command."
                                )

                url, current_depth = await urls_to_visit.get()
                self.logger.info(f"Job {job_id}: Processing URL: {url} at depth {current_depth}")
                
                if url in self.crawled_urls:
                    self.logger.debug(f"Skipping {url}: Already crawled.")
                    continue
                
                if current_depth >= self.config.max_depth:
                    self.logger.debug(f"Skipping {url} due to max depth ({current_depth})")
                    continue
                
                # Mark as crawled before attempting to fetch to prevent re-adding to queue
                self.crawled_urls.add(url) 
                
                self.logger.info(f"Attempting to crawl: {url} (Depth: {current_depth}, Crawled: {pages_crawled_count}/{self.config.max_pages})")
                
                result = await self._crawl_url_internal(url, last_crawl_result) # Call internal method
                last_crawl_result = result

                if result.error_message:
                    self.logger.warning(f"Failed to crawl {url}: {result.error_message}")
                    self.failed_urls.add(url)
                    crawl_errors_list.append(CrawlError(url=url, error_type="CrawlError", message=result.error_message))
                    # Do NOT increment pages_crawled_count for failed attempts that didn't yield content
                    continue
                
                # Only increment pages_crawled_count for successfully fetched pages
                pages_crawled_count += 1 
                self.logger.info(f"Successfully crawled: {url}. Total pages crawled: {pages_crawled_count}")

                total_links_found_count += len(result.links_found)

                target_links = [link for link in result.links_found 
                                if self._is_link_to_target(link, target_url, target_domain)]
                
                if target_links:
                    backlinks_found_list.extend(target_links)
                    self.logger.info(f"Found {len(target_links)} backlinks to target on {url}.")
                
                for link in result.links_found:
                    parsed_link_url = urlparse(link.target_url)
                    if self.config.is_domain_allowed(parsed_link_url.netloc):
                        if link.target_url not in self.crawled_urls and \
                           pages_crawled_count + urls_to_visit.qsize() < self.config.max_pages:
                            await urls_to_visit.put((link.target_url, current_depth + 1))
        
        # CRITICAL FIX: Always return a final summary result at the end
        final_crawl_duration = time.time() - start_crawl_time
        final_summary_result = CrawlResult(
            url=target_url, # The target URL for which the crawl was performed
            status_code=200, # Indicate successful completion of the crawl process
            pages_crawled=pages_crawled_count,
            total_links_found=total_links_found_count,
            backlinks_found=len(backlinks_found_list),
            failed_urls_count=len(self.failed_urls),
            is_final_summary=True,  # Flag to indicate this as the summary result
            crawl_duration_seconds=final_crawl_duration,
            errors=crawl_errors_list,
            # Store the actual backlinks found in the links_found field of the summary result
            links_found=backlinks_found_list, 
            crawl_timestamp=datetime.now()
        )
        
        self.logger.info(f"Crawl for job {job_id} finished. Crawled {pages_crawled_count} pages, found {len(backlinks_found_list)} backlinks to target.")
        return final_summary_result # Return the single summary result
