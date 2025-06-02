import logging
import asyncio
import os
import redis.asyncio as redis
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import CrawlJob, CrawlStatus, LinkProfile, CrawlResult, CrawlError, LinkType, SpamLevel, URL, Domain, SEOMetrics, SERPResult, KeywordSuggestion, ContentGapAnalysisResult, DomainHistory, LinkProspect, OutreachCampaign, OutreachEvent, ReportJob, CrawlConfig, serialize_model
from Link_Profiler.crawlers.web_crawler import WebCrawler
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.crawlers.serp_crawler import SERPCrawler
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper
from Link_Profiler.crawlers.social_media_crawler import SocialMediaCrawler
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService
from Link_Profiler.services.ai_service import AIService
from Link_Profiler.services.link_health_service import LinkHealthService
from Link_Profiler.services.serp_service import SERPService
from Link_Profiler.services.keyword_service import KeywordService
from Link_Profiler.services.social_media_service import SocialMediaService
from Link_Profiler.services.web3_service import Web3Service
from Link_Profiler.services.link_building_service import LinkBuildingService
from Link_Profiler.services.report_service import ReportService
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
from Link_Profiler.config.config_loader import ConfigLoader, config_loader
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.proxy_manager import proxy_manager
from Link_Profiler.utils.content_validator import ContentValidator
from Link_Profiler.utils.anomaly_detector import AnomalyDetector
from Link_Profiler.utils.api_rate_limiter import APIRateLimiter

# New import for Playwright browser management
from playwright.async_api import async_playwright, Browser


logger = logging.getLogger(__name__)

class SatelliteCrawler:
    """
    Satellite Crawler responsible for fetching and processing crawl jobs from Redis.
    """
    def __init__(self, redis_url: str, crawler_id: str = None, region: str = "default", database_url: Optional[str] = None):
        self.redis_url = redis_url
        self.crawler_id = crawler_id if crawler_id else f"satellite-{uuid.uuid4().hex[:8]}"
        self.region = region
        self.logger = logging.getLogger(f"{__name__}.{self.crawler_id}")
        
        self.redis_client: Optional[redis.Redis] = None
        self.db: Optional[Database] = None
        self.clickhouse_loader: Optional[ClickHouseLoader] = None
        self.web_crawler: Optional[WebCrawler] = None
        self.technical_auditor: Optional[TechnicalAuditor] = None
        self.serp_crawler: Optional[SERPCrawler] = None
        self.keyword_scraper: Optional[KeywordScraper] = None
        self.social_media_crawler: Optional[SocialMediaCrawler] = None
        self.playwright_instance = None # To hold the Playwright context manager
        self.playwright_browser: Optional[Browser] = None # To hold the launched browser instance

        # Retrieve configurations
        self.job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs")
        self.result_queue_name = config_loader.get("queue.result_queue_name", "crawl_results")
        self.dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name", "dead_letter_queue")
        self.heartbeat_interval = config_loader.get("queue.heartbeat_interval", 30)
        self.stale_timeout = config_loader.get("queue.stale_timeout", 60)
        self.max_retries = config_loader.get("queue.max_retries", 3)
        self.retry_delay = config_loader.get("queue.retry_delay", 5)
        self.clickhouse_enabled = config_loader.get("clickhouse.enabled", False)

        # Database initialization
        # Prioritize passed database_url, then config, then hardcoded fallback
        resolved_database_url = database_url or config_loader.get("database.url", "postgresql://linkprofiler:secure_password_123@localhost:5432/link_profiler_db")
        self.db = Database(db_url=resolved_database_url)
        self.logger.info(f"SatelliteCrawler: Initialized Database with URL: {resolved_database_url.split('@')[-1]}") # Log without password

        # Initialize ClickHouse Loader if enabled
        if self.clickhouse_enabled:
            self.clickhouse_loader = ClickHouseLoader(
                host=config_loader.get("clickhouse.host"),
                port=config_loader.get("clickhouse.port"),
                user=config_loader.get("clickhouse.user"),
                password=config_loader.get("clickhouse.password"),
                database=config_loader.get("clickhouse.database")
            )
            self.logger.info("SatelliteCrawler: ClickHouseLoader initialized.")
        else:
            self.logger.info("SatelliteCrawler: ClickHouse integration disabled.")

        # Initialize services that the crawler might interact with
        # These are passed to WebCrawler, so they need to be initialized first
        self.domain_analyzer_service = DomainAnalyzerService(self.db, None, None) # Needs proper init later
        self.ai_service = AIService() # Needs proper init later
        self.link_health_service = LinkHealthService(self.db)
        self.serp_service = SERPService(None, None, None, None) # Needs proper init later
        self.keyword_service = KeywordService(None, None, None, None) # Needs proper init later
        self.social_media_service = SocialMediaService(None, None, None, None, None, None) # Needs proper init later
        self.web3_service = Web3Service(None, None) # Needs proper init later
        self.link_building_service = LinkBuildingService(self.db, None, None, None, None, None) # Needs proper init later
        self.report_service = ReportService(self.db)

        # Initialize web_crawler here, but pass playwright_browser as None initially
        # It will be set in __aenter__ if browser_crawler is enabled
        self.web_crawler = WebCrawler(
            database=self.db,
            redis_client=self.redis_client, # Will be set in __aenter__
            clickhouse_loader=self.clickhouse_loader,
            config=config_loader.get("crawler", {}), # Pass the raw dict, with default empty dict
            anti_detection_config=config_loader.get("anti_detection", {}), # Default empty dict
            proxy_config=config_loader.get("proxy", {}), # Default empty dict
            quality_assurance_config=config_loader.get("quality_assurance", {}), # Default empty dict
            domain_analyzer_service=self.domain_analyzer_service,
            ai_service=self.ai_service,
            link_health_service=self.link_health_service,
            serp_service=self.serp_service,
            keyword_service=self.keyword_service,
            social_media_service=self.social_media_service,
            web3_service=self.web3_service,
            link_building_service=self.link_building_service,
            report_service=self.report_service,
            playwright_browser=None # Initialise as None, set in __aenter__
        )
        self.technical_auditor = TechnicalAuditor(
            lighthouse_path=config_loader.get("technical_auditor.lighthouse_path")
        )
        self.serp_crawler = SERPCrawler(
            headless=config_loader.get("serp_crawler.playwright.headless", True), # Added default
            browser_type=config_loader.get("serp_crawler.playwright.browser_type", "chromium") # Added default
        )
        self.keyword_scraper = KeywordScraper()
        self.social_media_crawler = SocialMediaCrawler()

        self.running_jobs: Dict[str, asyncio.Task] = {}
        self.last_heartbeat_time = datetime.now()

    async def __aenter__(self):
        self.logger.info(f"SatelliteCrawler {self.crawler_id} entering context.")
        self.redis_client = redis.Redis(connection_pool=redis.ConnectionPool.from_url(self.redis_url))
        await self.redis_client.ping()
        self.logger.info(f"SatelliteCrawler {self.crawler_id} connected to Redis.")

        # --- Start: Uniqueness check for crawler_id ---
        original_crawler_id = self.crawler_id
        # Check if the provided/generated crawler_id is already active
        # An ID is considered active if its last heartbeat is within the stale_timeout
        
        # Get the current timestamp
        now_timestamp = datetime.now().timestamp()
        # Calculate the cutoff for stale heartbeats
        stale_cutoff = (datetime.now() - timedelta(seconds=self.stale_timeout)).timestamp()

        # Check if this crawler_id exists in the sorted set with a recent score
        # zscore returns the score (timestamp) of the member
        existing_score = await self.redis_client.zscore("crawler_heartbeats_sorted", self.crawler_id)

        if existing_score is not None and existing_score >= stale_cutoff:
            # The crawler_id is already present and its heartbeat is fresh
            self.logger.warning(f"Crawler ID '{self.crawler_id}' is already active. Generating a new unique ID.")
            # Append a short unique suffix
            self.crawler_id = f"{original_crawler_id}-{uuid.uuid4().hex[:4]}"
            self.logger = logging.getLogger(f"{__name__}.{self.crawler_id}") # Update logger name
            self.logger.info(f"New unique Crawler ID generated: '{self.crawler_id}'")
        # --- End: Uniqueness check for crawler_id ---

        # Initialize database connection (ping to ensure it's up)
        self.db.ping()
        self.logger.info(f"SatelliteCrawler {self.crawler_id} connected to PostgreSQL.")

        if self.clickhouse_loader:
            await self.clickhouse_loader.__aenter__()
            self.logger.info(f"SatelliteCrawler {self.crawler_id} connected to ClickHouse.")

        # Initialize services that are asynchronous context managers
        await self.ai_service.__aenter__()
        await self.serp_service.__aenter__()
        await self.keyword_service.__aenter__()
        await self.social_media_service.__aenter__()
        await self.web3_service.__aenter__()
        await self.web_crawler.__aenter__() # This one is a context manager
        await self.serp_crawler.__aenter__() # This one is a context manager

        # Conditionally launch Playwright browser for WebCrawler
        if config_loader.get("browser_crawler.enabled", False):
            browser_type = config_loader.get("browser_crawler.browser_type", "chromium")
            headless = config_loader.get("browser_crawler.headless", True)
            self.logger.info(f"Satellite startup: Launching Playwright browser ({browser_type}, headless={headless})...")
            self.playwright_instance = await async_playwright().start() # Store playwright_instance
            if browser_type == "chromium":
                self.playwright_browser = await self.playwright_instance.chromium.launch(headless=headless)
            elif browser_type == "firefox":
                self.playwright_browser = await self.playwright_instance.firefox.launch(headless=headless)
            elif browser_type == "webkit":
                self.playwright_browser = await self.playwright_instance.webkit.launch(headless=headless)
            else:
                raise ValueError(f"Unsupported browser type for WebCrawler: {browser_type}")
            
            # Assign the launched browser to the web_crawler instance
            self.web_crawler.playwright_browser = self.playwright_browser
            self.logger.info("Playwright browser launched and assigned to WebCrawler.")
        else:
            self.logger.info("Playwright browser for WebCrawler is disabled by configuration.")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logger.info(f"SatelliteCrawler {self.crawler_id} exiting context.")
        
        # Cancel all running jobs
        for job_id, task in list(self.running_jobs.items()):
            if not task.done():
                self.logger.info(f"Cancelling running job {job_id}...")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    self.logger.info(f"Job {job_id} cancelled.")
                except Exception as e:
                    self.logger.error(f"Error during cancellation of job {job_id}: {e}")

        # Close connections and exit contexts in reverse order for async context managers
        await self.serp_crawler.__aexit__(exc_type, exc_val, exc_tb)
        await self.web_crawler.__aexit__(exc_type, exc_val, exc_tb)
        await self.web3_service.__aexit__(exc_type, exc_val, exc_tb)
        await self.social_media_service.__aexit__(exc_type, exc_val, exc_tb)
        await self.keyword_service.__aexit__(exc_type, exc_val, exc_tb)
        await self.serp_service.__aexit__(exc_type, exc_val, exc_tb)
        await self.ai_service.__aexit__(exc_type, exc_val, exc_tb)

        if self.clickhouse_loader:
            await self.clickhouse_loader.__aexit__(exc_type, exc_val, exc_tb)

        if self.redis_client:
            await self.redis_client.close()
            self.logger.info(f"SatelliteCrawler {self.crawler_id} disconnected from Redis.")
        
        # Close Playwright browser if it was launched
        if self.playwright_browser:
            self.logger.info("Satellite shutdown: Closing Playwright browser.")
            await self.playwright_browser.close()
            if self.playwright_instance: # Also stop the playwright_instance itself
                await self.playwright_instance.stop()


    async def _send_heartbeat(self):
        """Sends a periodic heartbeat to Redis."""
        try:
            heartbeat_data = {
                "crawler_id": self.crawler_id,
                "region": self.region,
                "status": "active",
                "running_jobs": len(self.running_jobs),
                "timestamp": datetime.now().isoformat()
            }
            
            # Store detailed heartbeat data in a separate key with an expiry
            # The expiry should be longer than the stale_timeout to allow for recovery
            await self.redis_client.set(
                f"crawler_details:{self.crawler_id}", 
                json.dumps(heartbeat_data), 
                ex=self.stale_timeout * 2
            )

            # Use a sorted set to track active crawlers and their last heartbeat time
            # The member is the crawler_id, and the score is the timestamp.
            # This ensures only one entry per crawler_id in the sorted set.
            await self.redis_client.zadd(
                "crawler_heartbeats_sorted", 
                {self.crawler_id: datetime.now().timestamp()}
            )
            
            self.last_heartbeat_time = datetime.now()
            self.logger.debug(f"Heartbeat sent for {self.crawler_id}. Running jobs: {len(self.running_jobs)}")
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat for {self.crawler_id}: {e}")

    async def _process_job(self, job_data: Dict):
        """Processes a single job."""
        job_id = job_data.get("id")
        job_type = job_data.get("job_type")
        target_url = job_data.get("target_url")
        initial_seed_urls = job_data.get("initial_seed_urls", [])
        config_dict = job_data.get("config", {})
        
        self.logger.info(f"Processing job {job_id} (Type: {job_type}, Target: {target_url})")
        
        job = CrawlJob.from_dict(job_data)
        job.status = CrawlStatus.IN_PROGRESS
        job.started_date = datetime.now()
        self.db.update_crawl_job(job)
        self.running_jobs[job_id] = asyncio.current_task() # Store the task for cancellation

        try:
            result_data = {}
            if job_type == "backlink_discovery":
                # Pass job_id to web_crawler.start_crawl
                crawl_result_generator = self.web_crawler.start_crawl(target_url, initial_seed_urls, job_id)
                # Consume the generator to get the final crawl result summary
                # Assuming start_crawl yields results and the last one is the summary or we aggregate
                final_crawl_result = None
                async for crawl_res in crawl_result_generator:
                    # Process intermediate crawl_res if needed, e.g., save backlinks
                    # For now, just keep the last one as the "final" summary
                    final_crawl_result = crawl_res 
                
                if final_crawl_result:
                    result_data = serialize_model(final_crawl_result)
                    job.urls_crawled = final_crawl_result.pages_crawled
                    job.links_found = final_crawl_result.total_links_found
                    job.errors_count = len(final_crawl_result.errors)
                    job.error_log.extend(final_crawl_result.errors)
                    job.status = CrawlStatus.COMPLETED
                    self.logger.info(f"Job {job_id} (backlink_discovery) completed successfully.")
                else:
                    job.status = CrawlStatus.FAILED
                    job.error_log.append(CrawlError(
                        timestamp=datetime.now(),
                        url=target_url,
                        error_type="NoCrawlResult",
                        message="WebCrawler did not return a final crawl result."
                    ))
                    self.logger.error(f"Job {job_id} (backlink_discovery) failed: No final crawl result.")

            elif job_type == "link_health_audit":
                source_urls_to_audit = config_dict.get("source_urls_to_audit", [])
                audit_results = await self.link_health_service.audit_links_batch(source_urls_to_audit)
                result_data = {"audit_results": [serialize_model(res) for res in audit_results]}
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Job {job_id} (link_health_audit) completed successfully.")
            elif job_type == "technical_audit":
                urls_to_audit = config_dict.get("urls_to_audit_tech", [])
                audit_results = await self.technical_auditor.run_batch_audit(urls_to_audit)
                result_data = {"technical_audit_results": audit_results}
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Job {job_id} (technical_audit) completed successfully.")
            elif job_type == "full_seo_audit":
                urls_to_audit = config_dict.get("urls_to_audit_full_seo", [])
                # Orchestrate calls to technical_auditor and link_health_service
                tech_audit_results = await self.technical_auditor.run_batch_audit(urls_to_audit)
                link_audit_results = await self.link_health_service.audit_links_batch(urls_to_audit)
                result_data = {
                    "technical_audit_results": tech_audit_results,
                    "link_health_audit_results": [serialize_model(res) for res in link_audit_results]
                }
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Job {job_id} (full_seo_audit) completed successfully.")
            elif job_type == "domain_analysis":
                domain_names = config_dict.get("domain_names_to_analyze", [])
                min_value_score = config_dict.get("min_value_score")
                limit = config_dict.get("limit")
                analysis_results = await self.domain_analyzer_service.analyze_domains_batch(
                    domain_names=domain_names,
                    min_value_score=min_value_score,
                    limit=limit
                )
                result_data = {"domain_analysis_results": [serialize_model(res) for res in analysis_results]}
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Job {job_id} (domain_analysis) completed successfully.")
            elif job_type == "web3_crawl":
                web3_identifier = config_dict.get("web3_content_identifier")
                web3_data = await self.web3_service.crawl_web3_content(web3_identifier)
                result_data = {"web3_data": web3_data}
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Job {job_id} (web3_crawl) completed successfully.")
            elif job_type == "social_media_crawl":
                social_query = config_dict.get("social_media_query")
                platforms = config_dict.get("platforms")
                social_data = await self.social_media_service.crawl_social_media(social_query, platforms)
                result_data = {"social_media_data": social_data}
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Job {job_id} (social_media_crawl) completed successfully.")
            elif job_type == "content_gap_analysis":
                target_url_cga = config_dict.get("target_url_for_content_gap")
                competitor_urls_cga = config_dict.get("competitor_urls_for_content_gap")
                cga_result = await self.ai_service.perform_content_gap_analysis(target_url_cga, competitor_urls_cga)
                result_data = serialize_model(cga_result)
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Job {job_id} (content_gap_analysis) completed successfully.")
            elif job_type == "prospect_identification":
                # Extract parameters from config_dict
                target_domain = config_dict.get("target_domain")
                competitor_domains = config_dict.get("competitor_domains", [])
                keywords = config_dict.get("keywords", [])
                min_domain_authority = config_dict.get("min_domain_authority")
                max_spam_score = config_dict.get("max_spam_score")
                num_serp_results_to_check = config_dict.get("num_serp_results_to_check")
                num_competitor_backlinks_to_check = config_dict.get("num_competitor_backlinks_to_check")

                prospects = await self.link_building_service.identify_link_prospects(
                    target_domain=target_domain,
                    competitor_domains=competitor_domains,
                    keywords=keywords,
                    min_domain_authority=min_domain_authority,
                    max_spam_score=max_spam_score,
                    num_serp_results_to_check=num_serp_results_to_check,
                    num_competitor_backlinks_to_check=num_competitor_backlinks_to_check
                )
                result_data = {"link_prospects": [serialize_model(p) for p in prospects]}
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Job {job_id} (prospect_identification) completed successfully.")
            elif job_type == "report_generation":
                report_type = config_dict.get("report_job_type")
                report_target_identifier = config_dict.get("report_target_identifier")
                report_format = config_dict.get("report_format")
                report_config = config_dict.get("config", {}) # Additional config for report generation

                file_path = await self.report_service.generate_report(
                    report_type=report_type,
                    target_identifier=report_target_identifier,
                    output_format=report_format,
                    report_config=report_config
                )
                result_data = {"report_file_path": file_path}
                job.status = CrawlStatus.COMPLETED
                job.results = result_data # Store file path in job results
                job.file_path = file_path # Also store in dedicated field
                self.logger.info(f"Job {job_id} (report_generation) completed successfully. File: {file_path}")
            else:
                raise ValueError(f"Unknown job type: {job_type}")

            job.results = result_data
            job.completed_date = datetime.now()
            # Removed direct assignment to job.duration_seconds
            # job.duration_seconds = (job.completed_date - job.started_date).total_seconds()
            self.db.update_crawl_job(job)
            self.logger.info(f"Job {job_id} finished. Status: {job.status.value}")

        except asyncio.CancelledError:
            self.logger.warning(f"Job {job_id} was cancelled.")
            job.status = CrawlStatus.CANCELLED
            job.completed_date = datetime.now()
            # Removed direct assignment to job.duration_seconds
            # job.duration_seconds = (job.completed_date - job.started_date).total_seconds() if job.started_date else 0
            job.error_log.append(CrawlError(
                timestamp=datetime.now(),
                url=target_url,
                error_type="CancelledError",
                message="Job was cancelled by system shutdown or manual intervention."
            ))
            self.db.update_crawl_job(job)
        except Exception as e:
            self.logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            job.status = CrawlStatus.FAILED
            job.completed_date = datetime.now()
            # Removed direct assignment to job.duration_seconds
            # job.duration_seconds = (job.completed_date - job.started_date).total_seconds() if job.started_date else 0
            job.errors_count += 1
            job.error_log.append(CrawlError(
                timestamp=datetime.now(),
                url=target_url,
                error_type=e.__class__.__name__,
                message=str(e)
            ))
            self.db.update_crawl_job(job)
            # Optionally push to dead-letter queue
            job_data["dead_letter_reason"] = str(e)
            job_data["dead_letter_timestamp"] = datetime.now().isoformat()
            await self.redis_client.rpush(self.dead_letter_queue_name, json.dumps(job_data))
            self.logger.warning(f"Job {job_id} moved to dead-letter queue.")
        finally:
            self.running_jobs.pop(job_id, None) # Remove job from running list

    async def _fetch_and_process_jobs(self):
        """Continuously fetches and processes jobs from the queue."""
        while True:
            try:
                # Check for pause flag
                if await self.redis_client.exists("processing_paused"):
                    self.logger.info("Job processing is paused. Waiting...")
                    await asyncio.sleep(self.heartbeat_interval)
                    continue

                # Fetch job from sorted set (lowest score/priority first)
                # Use ZPOPMAX to get highest priority (lowest score)
                # Or ZPOPMIN to get lowest priority (lowest score)
                # Assuming lower score means higher priority for ZADD
                job_raw = await self.redis_client.zpopmin(self.job_queue_name, count=1)
                
                if job_raw:
                    job_data_str = job_raw[0][0].decode('utf-8')
                    job_data = json.loads(job_data_str)
                    job_id = job_data.get("id")
                    
                    # Check if job is scheduled for future
                    scheduled_at_str = job_data.get("scheduled_at")
                    if scheduled_at_str:
                        scheduled_at = datetime.fromisoformat(scheduled_at_str)
                        if scheduled_at > datetime.now():
                            # Re-add to queue with original score and wait
                            await self.redis_client.zadd(self.job_queue_name, {job_data_str: scheduled_at.timestamp()})
                            self.logger.debug(f"Job {job_id} is scheduled for future. Re-queued and waiting.")
                            await asyncio.sleep(1) # Small sleep to avoid busy-waiting
                            continue

                    # Check for max retries
                    current_retries = job_data.get("retries", 0)
                    if current_retries >= self.max_retries:
                        self.logger.warning(f"Job {job_id} exceeded max retries ({self.max_retries}). Moving to dead-letter queue.")
                        job_data["dead_letter_reason"] = "Exceeded max retries"
                        job_data["dead_letter_timestamp"] = datetime.now().isoformat()
                        await self.redis_client.rpush(self.dead_letter_queue_name, json.dumps(job_data))
                        continue

                    # Process the job in a separate task
                    asyncio.create_task(self._process_job(job_data))
                else:
                    self.logger.debug("No jobs in queue. Waiting...")
                    await asyncio.sleep(1) # Short sleep to avoid busy-waiting
            except Exception as e:
                self.logger.error(f"Error fetching or processing job: {e}", exc_info=True)
                await asyncio.sleep(5) # Longer sleep on error

    async def start(self):
        """Starts the satellite crawler's main loop."""
        self.logger.info(f"SatelliteCrawler {self.crawler_id} starting main loop.")
        
        # Start heartbeat task
        asyncio.create_task(self._heartbeat_loop())
        
        # Start job fetching and processing loop
        await self._fetch_and_process_jobs()

    async def _heartbeat_loop(self):
        """Runs the heartbeat in a continuous loop."""
        while True:
            await self._send_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)
