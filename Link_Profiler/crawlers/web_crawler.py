import asyncio
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta
import random
import aiohttp # Import aiohttp
import json
import re
import uuid # Import uuid for Backlink ID

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

from Link_Profiler.core.models import URL, Backlink, CrawlConfig, CrawlResult, SEOMetrics, CrawlError, ContentType, SpamLevel, LinkType # Import LinkType
from Link_Profiler.database.database import Database
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.content_validator import ContentValidator
from Link_Profiler.utils.anomaly_detector import anomaly_detector
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.services.ai_service import AIService
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue # Import SmartCrawlQueue

logger = logging.getLogger(__name__)

class EnhancedWebCrawler:
    """
    An enhanced web crawler that uses Playwright for JavaScript rendering
    and aiohttp for efficient HTTP requests.
    Includes advanced features like anti-bot detection, content validation,
    and anomaly detection.
    """
    def __init__(self, config: CrawlConfig, db: Database, job_id: str, ai_service: AIService, playwright_browser: Optional[Browser] = None, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, crawl_queue: Optional[SmartCrawlQueue] = None):
        self.config = config
        self.db = db
        self.job_id = job_id
        self.ai_service = ai_service
        self.logger = logging.getLogger(__name__ + f".EnhancedWebCrawler({job_id})")
        self.playwright_browser = playwright_browser # Injected Playwright browser instance
        self.session_manager = session_manager
        if self.session_manager is None:
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager
            self.session_manager = global_session_manager
            self.logger.warning("No SessionManager provided to EnhancedWebCrawler. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager
        if self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        self.crawl_queue = crawl_queue # Store the crawl_queue instance

        self.content_validator = ContentValidator()
        self.crawled_urls: Set[str] = set()
        self.domain_crawl_delays: Dict[str, float] = {} # To store per-domain delays for politeness
        self.last_crawl_time: Dict[str, float] = {} # To track last crawl time per domain

    async def __aenter__(self):
        """No specific async setup needed for this class, as browser and session are injected."""
        self.logger.debug("Entering EnhancedWebCrawler context.")
        # The session_manager is already entered by the caller (main.py lifespan)
        # The playwright_browser is already launched by the caller (main.py lifespan)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class, as browser and session are managed externally."""
        self.logger.debug("Exiting EnhancedWebCrawler context.")
        pass

    async def _apply_politeness_delay(self, url: str):
        """Applies a delay based on robots.txt crawl-delay or a configured delay."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        if self.config.respect_robots_txt:
            # In a real scenario, you'd fetch and parse robots.txt for each domain
            # and extract the crawl-delay directive for your user agent.
            # For simplicity, we'll use a fixed delay or a learned delay.
            pass # Placeholder for robots.txt parsing

        # Apply human-like delays if configured
        if self.config.human_like_delays:
            delay_range = config_loader.get("anti_detection.random_delay_range", [0.5, 2.0])
            delay = random.uniform(delay_range[0], delay_range[1])
            self.logger.debug(f"Applying human-like delay of {delay:.2f} seconds for {domain}.")
            await asyncio.sleep(delay)
        elif self.config.delay_seconds > 0:
            self.logger.debug(f"Applying fixed delay of {self.config.delay_seconds:.2f} seconds for {domain}.")
            await asyncio.sleep(self.config.delay_seconds)

        # Ensure minimum delay between requests to the same domain
        now = datetime.now().timestamp()
        if domain in self.last_crawl_time:
            elapsed = now - self.last_crawl_time[domain]
            min_delay = self.config.delay_seconds # Use configured delay as minimum
            if elapsed < min_delay:
                wait_time = min_delay - elapsed
                self.logger.debug(f"Waiting {wait_time:.2f} seconds for {domain} to respect per-domain politeness.")
                await asyncio.sleep(wait_time)
        self.last_crawl_time[domain] = datetime.now().timestamp()

    async def crawl_url(self, url: str, job_id: str, depth: int) -> CrawlResult:
        """
        Crawls a single URL, extracts content, links, and SEO metrics.
        """
        self.logger.info(f"Crawling URL: {url} (Job ID: {job_id}, Depth: {depth})")
        self.crawled_urls.add(url)
        
        await self._apply_politeness_delay(url)

        crawl_result = CrawlResult(url=url, job_id=job_id, depth=depth, timestamp=datetime.now())
        
        try:
            if self.config.render_javascript and self.playwright_browser:
                self.logger.debug(f"Using Playwright to render JavaScript for {url}.")
                page_content, final_url, status_code, headers, validation_issues, anomaly_flags = await self._fetch_with_playwright(url)
                crawl_result.content = page_content
                crawl_result.final_url = final_url
                crawl_result.status_code = status_code
                crawl_result.headers = headers
                crawl_result.content_type = ContentType.HTML # Assume HTML for Playwright
                crawl_result.validation_issues.extend(validation_issues)
                crawl_result.anomaly_flags.extend(anomaly_flags)
            else:
                self.logger.debug(f"Using aiohttp for direct HTTP fetch for {url}.")
                page_content, final_url, status_code, headers, content_type, validation_issues, anomaly_flags = await self._fetch_with_aiohttp(url)
                crawl_result.content = page_content
                crawl_result.final_url = final_url
                crawl_result.status_code = status_code
                crawl_result.headers = headers
                crawl_result.content_type = content_type
                crawl_result.validation_issues.extend(validation_issues)
                crawl_result.anomaly_flags.extend(anomaly_flags)

            if crawl_result.status_code >= 400:
                crawl_result.error_message = f"HTTP Error: {crawl_result.status_code}"
                self.logger.warning(f"Failed to crawl {url}: HTTP Status {crawl_result.status_code}")
                return crawl_result

            if crawl_result.content:
                # Extract links
                crawl_result.links_found = self._extract_links(crawl_result.content, crawl_result.url)
                
                # Validate content quality
                content_quality_analysis = self.content_validator.validate_content_quality(crawl_result.content, crawl_result.url)
                crawl_result.metadata["content_quality"] = content_quality_analysis
                if content_quality_analysis.get("bot_detection_indicators"):
                    self.logger.warning(f"Bot detection indicators found for {url}: {content_quality_analysis['bot_detection_indicators']}")
                    # Consider this a failure for circuit breaker if it's a strong indicator
                    self.resilience_manager.get_circuit_breaker(urlparse(url).netloc).record_failure()

                # Perform AI-powered content analysis if enabled
                if self.ai_service.enabled:
                    ai_content_score, ai_classification = await self.ai_service.assess_content_quality(crawl_result.content, crawl_result.url)
                    if ai_content_score is not None:
                        crawl_result.ai_content_score = ai_content_score
                    if ai_classification:
                        crawl_result.ai_content_classification = ai_classification
                        # Use AI classification to determine spam level
                        if ai_classification == "spam":
                            crawl_result.spam_level = SpamLevel.CONFIRMED_SPAM
                        elif ai_classification == "low_quality":
                            crawl_result.spam_level = SpamLevel.LIKELY_SPAM
                        elif ai_classification == "irrelevant":
                            crawl_result.spam_level = SpamLevel.SUSPICIOUS
                        else:
                            crawl_result.spam_level = SpamLevel.CLEAN
                    
                    # Perform NLP analysis
                    nlp_analysis = await self.ai_service.analyze_content_nlp(crawl_result.content)
                    if nlp_analysis:
                        crawl_result.nlp_entities = nlp_analysis.get("entities", [])
                        crawl_result.nlp_sentiment = nlp_analysis.get("sentiment")
                        crawl_result.nlp_topics = nlp_analysis.get("topics", [])

                # Generate SEO metrics
                seo_metrics = self._generate_seo_metrics(crawl_result)
                crawl_result.seo_metrics = seo_metrics

            self.logger.info(f"Successfully crawled {url}. Found {len(crawl_result.links_found)} links.")
            return crawl_result

        except PlaywrightTimeoutError as e:
            crawl_result.error_message = f"Playwright Timeout: {e}"
            crawl_result.status_code = 408
            self.logger.error(f"Playwright timeout while crawling {url}: {e}")
        except aiohttp.ClientError as e:
            crawl_result.error_message = f"Network Error: {e}"
            crawl_result.status_code = 0 # Indicate network error
            self.logger.error(f"Network error while crawling {url}: {e}")
        except Exception as e:
            crawl_result.error_message = f"Unexpected Error: {e}"
            crawl_result.status_code = 500
            self.logger.error(f"Unexpected error while crawling {url}: {e}", exc_info=True)
        
        return crawl_result

    async def _fetch_with_playwright(self, url: str) -> Tuple[str, str, int, Dict[str, str], List[str], List[str]]:
        """Fetches page content using Playwright for JavaScript rendering."""
        if not self.playwright_browser:
            raise RuntimeError("Playwright browser not initialized.")

        page: Optional[Page] = None
        try:
            page = await self.playwright_browser.new_page()
            
            # Set random user agent and other headers for stealth
            headers = user_agent_manager.get_random_headers()
            await page.set_extra_http_headers(headers)

            # Enable stealth mode if configured
            if self.config.stealth_mode:
                # Playwright doesn't have a built-in "stealth mode" like Puppeteer-extra.
                # This would involve manually setting various browser properties,
                # or using a dedicated Playwright stealth plugin if available.
                # For now, this is a placeholder.
                self.logger.debug("Playwright stealth mode enabled (placeholder).")

            # Use resilience manager for page navigation
            response = await self.resilience_manager.execute_with_resilience(
                lambda: page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout_seconds * 1000), # Use timeout_seconds
                url=url # Use the URL for circuit breaker naming
            )
            
            # Simulate human-like delay
            if self.config.human_like_delays:
                delay_range = config_loader.get("anti_detection.random_delay_range", [1.0, 3.0])
                await asyncio.sleep(random.uniform(delay_range[0], delay_range[1]))

            content = await page.content()
            final_url = page.url
            status_code = response.status if response else 200 # Default to 200 if no response object
            response_headers = response.headers if response else {}

            # Anomaly detection for Playwright
            anomaly_flags = []
            if self.config.anomaly_detection_enabled:
                if await self._is_captcha_page(page):
                    anomaly_flags.append("CAPTCHA_DETECTED")
                if "bot" in content.lower() or "robot" in content.lower(): # Simple content check
                    anomaly_flags.append("BOT_DETECTION_KEYWORDS")

            return content, final_url, status_code, response_headers, [], anomaly_flags # No validation issues from fetch itself

        except PlaywrightTimeoutError as e:
            self.logger.error(f"Playwright timeout for {url}: {e}")
            return "", url, 408, {}, [], ["PLAYWRIGHT_TIMEOUT"]
        except Exception as e:
            self.logger.error(f"Error fetching with Playwright for {url}: {e}", exc_info=True)
            return "", url, 500, {}, [], ["PLAYWRIGHT_ERROR"]
        finally:
            if page:
                await page.close()

    async def _is_captcha_page(self, page: Page) -> bool:
        """Checks if the current page is a CAPTCHA or block page."""
        # Look for common CAPTCHA elements or text
        content = await page.content()
        if "captcha" in content.lower() or "verify you are human" in content.lower() or "unusual traffic" in content.lower():
            return True
        # Add more sophisticated checks if needed (e.g., specific element selectors)
        return False

    async def _fetch_with_aiohttp(self, url: str) -> Tuple[str, str, int, Dict[str, str], ContentType, List[str], List[str]]:
        """Fetches page content using aiohttp for direct HTTP requests."""
        if self.session_manager is None:
            raise RuntimeError("SessionManager is not initialized.")

        headers = {}
        if self.config.request_header_randomization:
            headers.update(user_agent_manager.get_random_headers())
        elif self.config.user_agent_rotation:
            headers['User-Agent'] = user_agent_manager.get_random_user_agent()
        else:
            headers['User-Agent'] = self.config.user_agent

        validation_issues = []
        anomaly_flags = []
        content_type = ContentType.UNKNOWN

        try:
            # Use resilience manager for the actual HTTP request
            async with self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(url, headers=headers, timeout=self.config.timeout_seconds), # Use timeout_seconds
                url=url # Use the URL for circuit breaker naming
            ) as response:
                final_url = str(response.url)
                status_code = response.status
                response_headers = dict(response.headers)
                
                if 'Content-Type' in response_headers:
                    if 'text/html' in response_headers['Content-Type']:
                        content_type = ContentType.HTML
                    elif 'application/pdf' in response_headers['Content-Type']:
                        content_type = ContentType.PDF
                    elif 'image/' in response_headers['Content-Type']:
                        content_type = ContentType.IMAGE
                    else:
                        content_type = ContentType.OTHER

                if status_code >= 400:
                    self.logger.warning(f"HTTP Error {status_code} for {url}")
                    return "", final_url, status_code, response_headers, content_type, validation_issues, anomaly_flags

                # Check content size limit
                content_length = int(response_headers.get('Content-Length', 0))
                if self.config.max_file_size_mb and content_length > self.config.max_file_size_mb * 1024 * 1024:
                    self.logger.warning(f"Content for {url} exceeds max_file_size_mb. Skipping download.")
                    validation_issues.append("Content size exceeds limit.")
                    return "", final_url, 200, response_headers, content_type, validation_issues, anomaly_flags

                content = await response.text() # Use .text() for HTML, .read() for binary

                # Anomaly detection for aiohttp
                if self.config.anomaly_detection_enabled:
                    if "bot" in content.lower() or "robot" in content.lower():
                        anomaly_flags.append("BOT_DETECTION_KEYWORDS")
                    # Add more checks like unusual redirects, very fast response times, etc.

                return content, final_url, status_code, response_headers, content_type, validation_issues, anomaly_flags

        except aiohttp.ClientError as e:
            self.logger.error(f"Network error fetching {url} with aiohttp: {e}")
            return "", url, 0, {}, ContentType.UNKNOWN, ["NETWORK_ERROR"], ["NETWORK_ERROR"]
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout fetching {url} with aiohttp.")
            return "", url, 408, {}, ContentType.UNKNOWN, ["TIMEOUT_ERROR"], ["TIMEOUT_ERROR"]
        except Exception as e:
            self.logger.error(f"Unexpected error fetching {url} with aiohttp: {e}", exc_info=True)
            return "", url, 500, {}, ContentType.UNKNOWN, ["UNEXPECTED_ERROR"], ["UNEXPECTED_ERROR"]

    def _extract_links(self, html_content: str, base_url: str) -> List[Backlink]:
        """Extracts all internal and external links from HTML content."""
        links: List[Backlink] = []
        # Use a simple regex for demonstration. A robust solution would use BeautifulSoup or lxml.
        # This regex finds href attributes in <a> tags.
        link_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"')
        
        for match in link_pattern.finditer(html_content):
            href = match.group(1)
            if href:
                try:
                    # Resolve relative URLs
                    full_url = urljoin(base_url, href)
                    parsed_full_url = urlparse(full_url)
                    
                    # Basic validation
                    if not parsed_full_url.scheme or not parsed_full_url.netloc:
                        continue # Skip invalid URLs

                    # Determine link type (simplified)
                    link_type = LinkType.DOFOLLOW # Default
                    # Check for rel attributes in a case-insensitive manner
                    rel_attr_match = re.search(r'rel=["\']([^"\']*)["\']', match.group(0), re.IGNORECASE)
                    if rel_attr_match:
                        rel_attributes = [attr.strip() for attr in rel_attr_match.group(1).split(',')]
                        if "nofollow" in rel_attributes:
                            link_type = LinkType.NOFOLLOW
                        elif "sponsored" in rel_attributes:
                            link_type = LinkType.SPONSORED
                        elif "ugc" in rel_attributes:
                            link_type = LinkType.UGC

                    # Extract anchor text (simplified: just the URL for now)
                    anchor_text = full_url # Placeholder

                    links.append(
                        Backlink(
                            id=str(uuid.uuid4()),
                            source_url=base_url,
                            target_url=full_url,
                            anchor_text=anchor_text,
                            link_type=link_type,
                            context_text="", # Not extracting context with simple regex
                            is_image_link=False, # Not detecting image links with simple regex
                            discovered_date=datetime.now(),
                            spam_level=SpamLevel.CLEAN # Default
                        )
                    )
                except Exception as e:
                    self.logger.debug(f"Error parsing link {href} from {base_url}: {e}")
        return links

    def _generate_seo_metrics(self, crawl_result: CrawlResult) -> SEOMetrics:
        """Generates SEO metrics for the crawled page."""
        metrics = SEOMetrics(
            url=crawl_result.url,
            http_status=crawl_result.status_code,
            response_time_ms=0, # Placeholder, needs actual measurement
            page_size_bytes=len(crawl_result.content.encode('utf-8')) if crawl_result.content else 0,
            # Other metrics would come from parsing HTML (title, meta description, headings, etc.)
            # or from external tools like Lighthouse.
            audit_timestamp=datetime.now()
        )
        # Add validation issues to SEO metrics
        metrics.validation_issues.extend(crawl_result.validation_issues)
        metrics.calculate_seo_score() # Calculate overall score
        return metrics
