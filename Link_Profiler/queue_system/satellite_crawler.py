"""
Lightweight Satellite Crawler - Consumes jobs from Redis queue
"""
import asyncio
import redis.asyncio as redis
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any # Added Any import
import socket
import sys
import os

from playwright.async_api import async_playwright, Browser # New: Import Playwright Browser

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Link_Profiler.crawlers.web_crawler import WebCrawler
from Link_Profiler.core.models import CrawlConfig, Backlink, CrawlJob, serialize_model, CrawlStatus
from Link_Profiler.services.crawl_service import CrawlService
from Link_Profiler.services.domain_service import DomainService, SimulatedDomainAPIClient, RealDomainAPIClient, AbstractDomainAPIClient
from Link_Profiler.services.backlink_service import BacklinkService, SimulatedBacklinkAPIClient, RealBacklinkAPIClient, GSCBacklinkAPIClient, OpenLinkProfilerAPIClient
from Link_Profiler.services.serp_service import SERPService, SimulatedSERPAPIClient, RealSERPAPIClient
from Link_Profiler.services.keyword_service import KeywordService, SimulatedKeywordAPIClient, RealKeywordAPIClient
from Link_Profiler.services.link_health_service import LinkHealthService
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService # Import DomainAnalyzerService
from Link_Profiler.services.ai_service import AIService # Import AIService
from Link_Profiler.database.database import Database
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
from Link_Profiler.crawlers.serp_crawler import SERPCrawler
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.config.config_loader import config_loader # New: Import config_loader


logger = logging.getLogger(__name__)

class SatelliteCrawler:
    """Lightweight satellite crawler that processes jobs from Redis queue"""
    
    def __init__(
        self, 
        redis_url: str = "redis://localhost:6379",
        crawler_id: Optional[str] = None,
        region: str = "default"
    ):
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        
        # Unique crawler identification
        self.crawler_id = crawler_id or f"crawler-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.region = region
        
        # Queue names (must match coordinator)
        self.job_queue = "crawl_jobs"
        self.result_queue = "crawl_results" 
        self.heartbeat_queue_sorted = "crawler_heartbeats_sorted" # Sorted set for heartbeats
        
        # Crawler state
        self.is_running = False
        self.current_job_id = None
        self.stats = {
            "jobs_processed": 0,
            "total_urls_crawled": 0,
            "total_links_found": 0,
            "start_time": datetime.now()
        }

        # Initialize services required by CrawlService
        self.db = Database() # Satellite needs its own DB connection
        self.clickhouse_loader: Optional[ClickHouseLoader] = None
        if config_loader.get("clickhouse.enabled", False):
            logger.info("ClickHouse integration enabled for satellite. Attempting to initialize ClickHouseLoader.")
            clickhouse_host = config_loader.get("clickhouse.host", "localhost")
            clickhouse_port = config_loader.get("clickhouse.port", 9000)
            clickhouse_user = config_loader.get("clickhouse.user", "default")
            clickhouse_password = config_loader.get("clickhouse.password", "")
            clickhouse_database = config_loader.get("clickhouse.database", "default")
            self.clickhouse_loader = ClickHouseLoader(
                host=clickhouse_host,
                port=clickhouse_port,
                user=clickhouse_user,
                password=clickhouse_password,
                database=clickhouse_database
            )
        else:
            logger.info("ClickHouse integration disabled for satellite.")

        # Initialize API clients and crawlers for CrawlService
        domain_service_instance = self._init_domain_service()
        backlink_service_instance = self._init_backlink_service()
        serp_crawler_instance = self._init_serp_crawler()
        serp_service_instance = SERPService(
            api_client=RealSERPAPIClient(api_key=config_loader.get("serp_api.real_api.api_key")) if config_loader.get("serp_api.real_api.enabled") else SimulatedSERPAPIClient(),
            serp_crawler=serp_crawler_instance
        )
        keyword_scraper_instance = self._init_keyword_scraper()
        keyword_service_instance = KeywordService(
            api_client=RealKeywordAPIClient(api_key=config_loader.get("keyword_api.real_api.api_key")) if config_loader.get("keyword_api.real_api.enabled") else SimulatedKeywordAPIClient(),
            keyword_scraper=keyword_scraper_instance
        )
        link_health_service_instance = LinkHealthService(self.db)
        technical_auditor_instance = TechnicalAuditor(
            lighthouse_path=config_loader.get("technical_auditor.lighthouse_path")
        )
        ai_service_instance = AIService() # New: Initialize AIService for satellite

        # Playwright browser instance for WebCrawler (if enabled)
        self.playwright_browser: Optional[Browser] = None

        # Initialize CrawlService instance that will execute jobs
        self.crawl_service = CrawlService(
            database=self.db,
            backlink_service=backlink_service_instance,
            domain_service=domain_service_instance,
            serp_service=serp_service_instance,
            keyword_service=keyword_service_instance,
            link_health_service=link_health_service_instance,
            clickhouse_loader=self.clickhouse_loader,
            redis_client=self.redis, # Pass the satellite's redis client for deduplication
            technical_auditor=technical_auditor_instance,
            domain_analyzer_service=domain_analyzer_service, # Pass domain_analyzer_service
            ai_service=ai_service_instance, # New: Pass AI Service
            playwright_browser=self.playwright_browser # Pass the Playwright browser instance
        )

        # List of context managers to enter/exit during satellite lifespan
        self._context_managers = [
            domain_service_instance,
            backlink_service_instance,
            serp_service_instance,
            keyword_service_instance,
            link_health_service_instance,
            technical_auditor_instance,
            ai_service_instance # New: Add AI Service to satellite lifespan
            # crawl_service is not an async context manager itself, its internal services are.
            # self.crawl_service # Removed from here as it doesn't have __aenter__/__aexit__
        ]
        if self.clickhouse_loader:
            self._context_managers.append(self.clickhouse_loader)
        if serp_crawler_instance:
            self._context_managers.append(serp_crawler_instance)
        if keyword_scraper_instance:
            self._context_managers.append(keyword_scraper_instance)

    def _init_domain_service(self):
        if config_loader.get("domain_api.abstract_api.enabled"):
            abstract_api_key = config_loader.get("domain_api.abstract_api.api_key")
            if not abstract_api_key:
                logger.error("AbstractAPI enabled but API key not found in config. Falling back to simulated Domain API.")
                return DomainService(api_client=SimulatedDomainAPIClient())
            else:
                logger.info("Using AbstractDomainAPIClient for domain lookups in satellite.")
                return DomainService(api_client=AbstractDomainAPIClient(api_key=abstract_api_key))
        elif config_loader.get("domain_api.real_api.enabled"):
            return DomainService(api_client=RealDomainAPIClient(api_key=config_loader.get("domain_api.real_api.api_key")))
        else:
            return DomainService(api_client=SimulatedDomainAPIClient())

    def _init_backlink_service(self):
        if config_loader.get("backlink_api.gsc_api.enabled"):
            return BacklinkService(api_client=GSCBacklinkAPIClient())
        elif config_loader.get("backlink_api.openlinkprofiler_api.enabled"):
            return BacklinkService(api_client=OpenLinkProfilerAPIClient())
        elif config_loader.get("backlink_api.real_api.enabled"):
            return BacklinkService(api_client=RealBacklinkAPIClient(api_key=config_loader.get("backlink_api.real_api.api_key")))
        else:
            return BacklinkService(api_client=SimulatedBacklinkAPIClient())

    def _init_serp_crawler(self):
        if config_loader.get("serp_crawler.playwright.enabled"):
            logger.info("Initialising Playwright SERPCrawler for satellite.")
            return SERPCrawler(
                headless=config_loader.get("serp_crawler.playwright.headless"),
                browser_type=config_loader.get("serp_crawler.playwright.browser_type")
            )
        return None

    def _init_keyword_scraper(self):
        if config_loader.get("keyword_scraper.enabled"):
            logger.info("Initialising KeywordScraper for satellite.")
            return KeywordScraper()
        return None

    async def __aenter__(self):
        """Enter all managed contexts."""
        self._entered_contexts = []
        for cm in self._context_managers:
            logger.info(f"Satellite startup: Entering {cm.__class__.__name__} context.")
            self._entered_contexts.append(await cm.__aenter__())
        
        # New: Conditionally launch Playwright browser for WebCrawler
        if config_loader.get("browser_crawler.enabled", False):
            browser_type = config_loader.get("browser_crawler.browser_type", "chromium")
            headless = config_loader.get("browser_crawler.headless", True)
            logger.info(f"Satellite startup: Launching Playwright browser for WebCrawler ({browser_type}, headless={headless})...")
            self.playwright_instance = await async_playwright().start()
            if browser_type == "chromium":
                self.playwright_browser = await self.playwright_instance.chromium.launch(headless=headless)
            elif browser_type == "firefox":
                self.playwright_browser = await self.playwright_instance.firefox.launch(headless=headless)
            elif browser_type == "webkit":
                self.playwright_browser = await self.playwright_instance.webkit.launch(headless=headless)
            else:
                raise ValueError(f"Unsupported browser type for WebCrawler: {browser_type}")
            
            # Pass this instance to crawl_service
            self.crawl_service.playwright_browser = self.playwright_browser
            logger.info("Playwright browser launched and assigned to CrawlService in satellite.")
        else:
            logger.info("Playwright browser for WebCrawler is disabled by configuration in satellite.")

        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit all managed contexts in reverse order."""
        for cm in reversed(self._entered_contexts):
            logger.info(f"Satellite shutdown: Exiting {cm.__class__.__name__} context.")
            await cm.__aexit__(exc_type, exc_val, exc_tb)
        
        # New: Close Playwright browser if it was launched
        if self.playwright_browser:
            logger.info("Satellite shutdown: Closing Playwright browser.")
            await self.playwright_browser.close()
            if hasattr(self, 'playwright_instance') and self.playwright_instance:
                await self.playwright_instance.stop()

        await self.redis.close()
    
    async def start(self):
        """Start the satellite crawler"""
        self.is_running = True
        logger.info(f"Starting satellite crawler {self.crawler_id} in region {self.region}")
        
        # Start background tasks
        heartbeat_task = asyncio.create_task(self._send_heartbeats())
        worker_task = asyncio.create_task(self._process_jobs())
        
        try:
            # Wait for both tasks
            await asyncio.gather(heartbeat_task, worker_task)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.is_running = False
            await self._cleanup()
    
    async def _process_jobs(self):
        """Main job processing loop"""
        while self.is_running:
            try:
                # Get highest priority job from queue
                # Use bzpopmax to get the highest score (priority) element
                job_data = await self.redis.bzpopmax(self.job_queue, timeout=5)
                
                if job_data:
                    _, job_json, priority = job_data
                    job_dict = json.loads(job_json)
                    
                    # Reconstruct CrawlJob dataclass from dict
                    job = CrawlJob.from_dict(job_dict)

                    logger.info(f"Received job {job.id} (type: {job.job_type}) with priority {priority}")
                    await self._execute_crawl_job(job)
                    
            except Exception as e:
                logger.error(f"Error processing job: {e}")
                await asyncio.sleep(1)
    
    async def _execute_crawl_job(self, job: CrawlJob):
        """Execute a single crawl job using the CrawlService"""
        self.current_job_id = job.id
        
        try:
            # Send job start notification
            await self._send_job_update(job.id, {
                "status": "started",
                "crawler_id": self.crawler_id,
                "start_time": datetime.now().isoformat()
            })
            
            # Extract job-specific parameters from job.config
            # These parameters are needed by crawl_service.execute_predefined_job
            initial_seed_urls = job.config.get("initial_seed_urls") # For backlink_discovery
            keyword = job.config.get("keyword") # For serp_analysis, keyword_research
            num_results = job.config.get("num_results") # For serp_analysis, keyword_research
            source_urls_to_audit = job.config.get("source_urls_to_audit") # For link_health_audit
            urls_to_audit_tech = job.config.get("urls_to_audit_tech") # For technical_audit
            domain_names_to_analyze = job.config.get("domain_names_to_analyze") # For domain_analysis
            min_value_score = job.config.get("min_value_score") # For domain_analysis
            limit = job.config.get("limit") # For domain_analysis
            urls_to_audit_full_seo = job.config.get("urls_to_audit_full_seo") # For full_seo_audit
            
            # Execute the job using the shared CrawlService instance
            await self.crawl_service.execute_predefined_job(
                job,
                initial_seed_urls=initial_seed_urls,
                keyword=keyword,
                num_results=num_results,
                source_urls_to_audit=source_urls_to_audit,
                urls_to_audit_tech=urls_to_audit_tech,
                domain_names_to_analyze=domain_names_to_analyze,
                min_value_score=min_value_score,
                limit=limit,
                urls_to_audit_full_seo=urls_to_audit_full_seo
            )
            
            # After execute_predefined_job completes, the job object's status and results
            # will be updated by CrawlService and persisted to the DB.
            # We just need to send a final notification to the coordinator.
            
            if job.status == CrawlStatus.COMPLETED:
                await self._send_job_result(job.id, {
                    "status": "completed",
                    "urls_crawled": job.urls_crawled,
                    "links_found": job.links_found,
                    "progress_percentage": 100.0,
                    "results": job.results, # Send back the full results dict
                    "completed_at": datetime.now().isoformat(),
                    "crawler_id": self.crawler_id
                })
                self.stats["jobs_processed"] += 1
                self.stats["total_urls_crawled"] += job.urls_crawled
                self.stats["total_links_found"] += job.links_found
                logger.info(f"Completed job {job.id}: {job.urls_crawled} URLs, {job.links_found} backlinks")
            elif job.status == CrawlStatus.FAILED:
                await self._send_job_result(job.id, {
                    "status": "failed",
                    "error_message": job.error_log[-1].message if job.error_log else "Job failed without specific error message.",
                    "failed_at": datetime.now().isoformat(),
                    "crawler_id": self.crawler_id,
                    "error_log": [serialize_model(err) for err in job.error_log] # Send full error log
                })
                logger.error(f"Job {job.id} failed during execution: {job.error_log[-1].message if job.error_log else 'Unknown error'}")
            
        except Exception as e:
            # This catches errors that prevent the job from even being passed to crawl_service or unexpected issues
            logger.error(f"Satellite failed to execute job {job.id}: {e}", exc_info=True)
            await self._send_job_result(job.id, {
                "status": "failed",
                "error_message": f"Satellite execution error: {str(e)}",
                "failed_at": datetime.now().isoformat(),
                "crawler_id": self.crawler_id
            })
        finally:
            self.current_job_id = None
    
    async def _send_job_update(self, job_id: str, update_data: Dict):
        """Send job progress update"""
        update_data.update({
            "job_id": job_id,
            "type": "progress_update",
            "timestamp": datetime.now().isoformat()
        })
        
        await self.redis.lpush(self.result_queue, json.dumps(update_data))
    
    async def _send_job_result(self, job_id: str, result_data: Dict):
        """Send final job result"""
        result_data.update({
            "job_id": job_id,
            "type": "job_result",
            "timestamp": datetime.now().isoformat()
        })
        
        await self.redis.lpush(self.result_queue, json.dumps(result_data))
    
    async def _send_heartbeats(self):
        """Send periodic heartbeats to coordinator"""
        while self.is_running:
            try:
                heartbeat = {
                    "crawler_id": self.crawler_id,
                    "region": self.region,
                    "timestamp": datetime.now().isoformat(),
                    "current_job": self.current_job_id,
                    "stats": self.stats
                }
                
                # Use ZADD to update heartbeat with current timestamp as score
                # This allows coordinator to easily get recent heartbeats
                await self.redis.zadd(
                    "crawler_heartbeats_sorted", 
                    {json.dumps(heartbeat): datetime.now().timestamp()}
                )
                
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup(self):
        """Cleanup resources on shutdown"""
        logger.info(f"Shutting down satellite crawler {self.crawler_id}")
        
        # Send final heartbeat
        final_heartbeat = {
            "crawler_id": self.crawler_id,
            "status": "shutting_down",
            "timestamp": datetime.now().isoformat(),
            "final_stats": self.stats
        }
        
        try:
            await self.redis.zadd(
                "crawler_heartbeats_sorted", 
                {json.dumps(final_heartbeat): datetime.now().timestamp()}
            )
        except Exception as e:
            logger.error(f"Error sending final heartbeat: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Performs a comprehensive health check of the satellite and its dependencies.
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "crawler_id": self.crawler_id,
            "region": self.region,
            "current_job_id": self.current_job_id,
            "dependencies": {}
        }

        # Check Redis connectivity
        try:
            await self.redis.ping()
            health_status["dependencies"]["redis"] = {"status": "connected"}
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["dependencies"]["redis"] = {"status": "disconnected", "error": str(e)}
            logger.error(f"Satellite health check: Redis connection failed: {e}")

        # Check PostgreSQL connectivity
        try:
            self.db.ping() # Assuming Database class has a ping method
            health_status["dependencies"]["postgresql"] = {"status": "connected"}
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["dependencies"]["postgresql"] = {"status": "disconnected", "error": str(e)}
            logger.error(f"Satellite health check: PostgreSQL connection failed: {e}")

        # Check if CrawlService's internal clients are active (Domain, Backlink, etc.)
        # This is a high-level check, not a deep ping to external APIs
        try:
            # Check if the main services within crawl_service are initialized
            if self.crawl_service.domain_service.api_client and \
               self.crawl_service.backlink_service.api_client and \
               self.crawl_service.serp_service.api_client and \
               self.crawl_service.keyword_service.api_client and \
               self.crawl_service.technical_auditor and \
               self.crawl_service.ai_service:
                health_status["dependencies"]["crawl_service_clients"] = {"status": "initialized"}
            else:
                health_status["status"] = "unhealthy"
                health_status["dependencies"]["crawl_service_clients"] = {"status": "not_initialized", "message": "One or more internal clients not ready."}
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["dependencies"]["crawl_service_clients"] = {"status": "failed_check", "error": str(e)}
            logger.error(f"Satellite health check: CrawlService internal clients check failed: {e}")

        # Check Playwright browser status if enabled
        if config_loader.get("browser_crawler.enabled", False):
            if self.playwright_browser and not self.playwright_browser.is_closed():
                health_status["dependencies"]["playwright_browser"] = {"status": "running"}
            else:
                health_status["status"] = "unhealthy"
                health_status["dependencies"]["playwright_browser"] = {"status": "not_running", "message": "Playwright browser is not active."}
        else:
            health_status["dependencies"]["playwright_browser"] = {"status": "disabled", "message": "Browser crawler is disabled."}

        return health_status


# CLI interface for easy deployment
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Satellite Crawler")
    parser.add_argument("--redis-url", default="redis://localhost:6379", help="Redis connection URL")
    parser.add_argument("--crawler-id", help="Unique crawler identifier")
    parser.add_argument("--region", default="default", help="Crawler region/zone")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    # Add a subparser for the health check command
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    run_parser = subparsers.add_parser("run", help="Run the satellite crawler (default command)")
    health_parser = subparsers.add_parser("health", help="Perform a health check of the satellite")

    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    crawler = SatelliteCrawler(
        redis_url=args.redis_url,
        crawler_id=args.crawler_id,
        region=args.region
    )

    if args.command == "health":
        health_report = await crawler.health_check()
        print(json.dumps(health_report, indent=2))
        if health_report["status"] == "unhealthy":
            sys.exit(1)
        sys.exit(0)
    else: # Default command is 'run'
        async with crawler as c:
            await c.start()

if __name__ == "__main__":
    asyncio.run(main())
