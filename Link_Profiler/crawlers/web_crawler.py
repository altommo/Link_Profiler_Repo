"""
Web Crawler - Core web crawling logic.
File: Link_Profiler/crawlers/web_crawler.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from urllib.parse import urlparse, urljoin
import aiohttp
from datetime import datetime

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.core.models import CrawlConfig, CrawlResult, Backlink, LinkType, ContentType, CrawlStatus, CrawlError, SEOMetrics # Added CrawlError, SEOMetrics
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.crawlers.robots_parser import RobotsParser
from Link_Profiler.crawlers.link_extractor import LinkExtractor
from Link_Profiler.utils.content_validator import ContentValidator
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.services.ai_service import AIService # For AI-powered content analysis
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # For resilience
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue, CrawlTask, Priority # For smart queue

logger = logging.getLogger(__name__)

class EnhancedWebCrawler:
    """
    An enhanced web crawler that uses a smart queue, handles robots.txt,
    extracts links, validates content, and can perform technical audits.
    """
    def __init__(self, config: CrawlConfig, crawl_queue: SmartCrawlQueue,
                 session_manager: SessionManager, ai_service: AIService,
                 resilience_manager: DistributedResilienceManager,
                 browser: Optional[Any] = None): # browser is playwright.Browser
        
        self.config = config
        self.crawl_queue = crawl_queue
        self.session_manager = session_manager
        self.ai_service = ai_service
        self.resilience_manager = resilience_manager
        self.browser = browser # Playwright browser instance for JS rendering

        self.robots_parser = RobotsParser(session_manager=self.session_manager)
        self.link_extractor = LinkExtractor()
        self.content_validator = ContentValidator()
        self.technical_auditor = TechnicalAuditor(
            lighthouse_path=config_loader.get("technical_auditor.lighthouse_path")
        )

        self.crawled_urls: Dict[str, CrawlResult] = {} # Store results of crawled URLs
        self.visited_urls: set = set() # Keep track of URLs already added to queue or processed
        self.logger = logging.getLogger(__name__ + ".EnhancedWebCrawler")

        self.job_id: Optional[str] = None # Current job ID being processed by this crawler instance

    async def __aenter__(self):
        """Initializes resources for the crawler."""
        await self.robots_parser.__aenter__()
        # No explicit __aenter__ for link_extractor, content_validator, technical_auditor
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleans up resources for the crawler."""
        await self.robots_parser.__aexit__(exc_type, exc_val, exc_tb)
        # No explicit __aexit__ for other components

    async def crawl_url(self, url: str, job_id: str, depth: int = 0, metadata: Dict[str, Any] = None) -> Optional[CrawlResult]:
        """
        Crawls a single URL, extracts information, and returns a CrawlResult.
        """
        if url in self.visited_urls:
            self.logger.debug(f"Skipping already visited URL: {url}")
            return None

        self.visited_urls.add(url)
        self.job_id = job_id # Set current job ID for this crawler instance

        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        # 1. Check robots.txt
        if self.config.respect_robots_txt and not await self.robots_parser.can_fetch(url, self.config.user_agent):
            self.logger.info(f"Blocked by robots.txt: {url}")
            return CrawlResult(url=url, status_code=403, content_type=ContentType.OTHER, error_message="Blocked by robots.txt")

        # 2. Check circuit breaker
        breaker = self.resilience_manager.get_circuit_breaker(f"crawler_url_fetch:{domain}")
        if not await breaker.can_execute():
            self.logger.warning(f"Circuit breaker open for {domain}. Skipping URL: {url}")
            return CrawlResult(url=url, status_code=503, content_type=ContentType.OTHER, error_message="Circuit breaker open")

        html_content = None
        status_code = None
        content_type = ContentType.OTHER
        error_message = None
        load_time_ms = None
        
        try:
            start_time = datetime.now()
            if self.config.render_javascript and self.browser:
                # Use Playwright for JS rendering
                self.logger.info(f"Rendering JavaScript for {url} using Playwright.")
                page = await self.browser.new_page()
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=self.config.request_timeout * 1000)
                    html_content = await page.content()
                    status_code = response.status if response else 200 # Default to 200 if no response object
                    content_type = ContentType.HTML
                except Exception as e:
                    self.logger.error(f"Playwright rendering failed for {url}: {e}")
                    error_message = f"Playwright rendering failed: {e}"
                    status_code = 500
                finally:
                    await page.close()
            else:
                # Use aiohttp for direct HTTP fetch
                self.logger.info(f"Fetching {url} using aiohttp.")
                async with self.session_manager.get(url, timeout=self.config.request_timeout) as response:
                    status_code = response.status
                    content_type_header = response.headers.get('Content-Type', '').lower()
                    
                    if 'text/html' in content_type_header:
                        content_type = ContentType.HTML
                        html_content = await response.text()
                    elif 'application/pdf' in content_type_header and self.config.extract_pdfs:
                        content_type = ContentType.PDF
                        # Handle PDF content (e.g., save to disk, extract text)
                        self.logger.info(f"PDF content found for {url}. Extraction not fully implemented.")
                    elif 'image/' in content_type_header and self.config.extract_images:
                        content_type = ContentType.IMAGE
                        # Handle image content
                        self.logger.info(f"Image content found for {url}. Extraction not fully implemented.")
                    else:
                        self.logger.info(f"Unsupported content type {content_type_header} for {url}.")
                        content_type = ContentType.OTHER
            
            load_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            breaker.record_success()

        except aiohttp.ClientError as e:
            self.logger.warning(f"HTTP client error for {url}: {e}")
            error_message = str(e)
            status_code = getattr(e, 'status', 500)
            breaker.record_failure()
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout fetching {url}")
            error_message = "Timeout"
            status_code = 408
            breaker.record_failure()
        except Exception as e:
            self.logger.error(f"Unexpected error fetching {url}: {e}", exc_info=True)
            error_message = str(e)
            status_code = 500
            breaker.record_failure()

        crawl_result = CrawlResult(
            url=url,
            status_code=status_code,
            content_type=content_type,
            html_content=html_content,
            load_time_ms=load_time_ms,
            error_message=error_message,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )

        if html_content and content_type == ContentType.HTML:
            # 3. Extract links
            extracted_links = await self.link_extractor.extract_links(url, html_content)
            crawl_result.links_found = extracted_links
            self.logger.info(f"Extracted {len(extracted_links)} links from {url}.")

            # 4. Validate content quality
            content_quality_analysis = self.content_validator.validate_content_quality(html_content, url)
            crawl_result.metadata["content_quality"] = content_quality_analysis
            if content_quality_analysis.get("bot_detection_indicators"):
                self.logger.warning(f"Bot detection indicators found for {url}: {content_quality_analysis['bot_detection_indicators']}")
                breaker.record_failure() # Consider this a failure for circuit breaker

            # 5. Perform technical audit (if configured)
            if self.config.enable_javascript and self.browser: # Technical audit often requires a browser
                try:
                    lighthouse_report = await self.technical_auditor.run_lighthouse_audit(url, self.config) # Pass config
                    crawl_result.metadata["lighthouse_report"] = lighthouse_report
                    self.logger.info(f"Lighthouse audit completed for {url}.")
                except Exception as e:
                    self.logger.error(f"Lighthouse audit failed for {url}: {e}")

            # 6. AI-powered content analysis
            if self.ai_service.enabled:
                try:
                    # Example: Score content for a generic keyword
                    ai_content_score_data = await self.ai_service.score_content(html_content[:4000], "web content")
                    if ai_content_score_data:
                        # Update SEOMetrics with AI insights
                        if crawl_result.seo_metrics is None:
                            crawl_result.seo_metrics = SEOMetrics(url=url)
                        crawl_result.seo_metrics.ai_content_score = ai_content_score_data.get('seo_score')
                        crawl_result.seo_metrics.ai_readability_score = ai_content_score_data.get('readability_score')
                        crawl_result.seo_metrics.ai_semantic_keywords = ai_content_score_data.get('semantic_keywords', [])
                        crawl_result.seo_metrics.ai_suggestions = ai_content_score_data.get('improvement_suggestions', [])
                        
                        # Classify content
                        ai_classification = await self.ai_service.classify_content(html_content[:2000], "web content")
                        if ai_classification:
                            crawl_result.seo_metrics.ai_content_classification = ai_classification

                    self.logger.debug(f"AI content score for {url}: {ai_content_score_data.get('seo_score')}")
                except Exception as e:
                    self.logger.error(f"AI content analysis failed for {url}: {e}")

        self.crawled_urls[url] = crawl_result
        return crawl_result

    async def crawl_for_backlinks(self, target_url: str, initial_seed_urls: List[str]) -> AsyncGenerator[CrawlResult, None]:
        """
        Initiates a crawl to discover backlinks to a target URL.
        Uses the smart queue for managing tasks.
        """
        self.logger.info(f"Starting backlink discovery crawl for target: {target_url}")
        self.logger.info(f"Initial seed URLs: {initial_seed_urls}")

        # Add initial seed URLs to the smart queue
        for seed_url in initial_seed_urls:
            if seed_url not in self.visited_urls:
                await self.crawl_queue.add_task(CrawlTask(job_id=self.job_id, url=seed_url, priority=Priority.HIGH, depth=0))
                self.visited_urls.add(seed_url) # Mark as visited to avoid re-adding

        while True:
            task = await self.crawl_queue.get_next_task()
            if not task:
                self.logger.info("No more tasks in queue. Waiting for new tasks or finishing.")
                # Implement a graceful shutdown or wait mechanism if no tasks are available
                # For now, a simple sleep to prevent tight loop
                await asyncio.sleep(5)
                # Check again if new tasks appeared or if the crawl should terminate
                if not self.crawl_queue.get_queue_stats()['total_tasks_in_queue'] > 0 and \
                   self.crawl_queue.get_queue_stats()['active_crawls'] == 0:
                    self.logger.info("Crawl queue empty and no active crawls. Terminating backlink discovery.")
                    break # Exit loop if no more tasks and no active crawls
                continue

            if task.depth >= self.config.max_depth:
                self.logger.debug(f"Max depth reached for {task.url}. Skipping.")
                self.crawl_queue.mark_task_completed(task, success=True)
                continue

            if len(self.crawled_urls) >= self.config.max_pages:
                self.logger.info(f"Max pages ({self.config.max_pages}) reached. Terminating crawl.")
                self.crawl_queue.mark_task_completed(task, success=True) # Mark current task as completed
                break # Exit loop

            self.logger.info(f"Crawling: {task.url} (Depth: {task.depth}, Retries: {task.retries})")
            crawl_result = await self.crawl_url(task.url, task.job_id, task.depth, task.metadata)

            if crawl_result:
                self.crawl_queue.mark_task_completed(task, success=True) # Mark task as completed
                
                # Process extracted links
                for link in crawl_result.links_found:
                    # Check if the link points to the target URL
                    if link.target_url == target_url:
                        self.logger.info(f"Found backlink: {link.source_url} -> {link.target_url}")
                        yield crawl_result # Yield the result containing the backlink
                    
                    # Add internal links to the queue for further crawling
                    # Ensure we don't crawl external links unless explicitly allowed
                    link_domain = urlparse(link.source_url).netloc
                    if link_domain == urlparse(task.url).netloc and link.source_url not in self.visited_urls:
                        await self.crawl_queue.add_task(CrawlTask(
                            job_id=task.job_id,
                            url=link.source_url,
                            priority=Priority.MEDIUM,
                            depth=task.depth + 1
                        ))
                        self.visited_urls.add(link.source_url)
            else:
                self.crawl_queue.mark_task_completed(task, success=False) # Mark task as failed
                self.logger.warning(f"Failed to crawl {task.url}. Result was None.")

        self.logger.info(f"Backlink discovery crawl for {target_url} finished.")
