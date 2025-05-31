"""
API Endpoints for the Link Profiler System
File: Link_Profiler/main.py (formerly Link_Profiler/api/main.py)
"""

import os
import sys
import time

# --- Robust Project Root Discovery ---
# Assuming this file is at Link_Profiler/Link_Profiler/main.py
# The project root (containing setup.py) is one level up from the 'Link_Profiler' package directory.
# So, it's os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if project_root and project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"PROJECT_ROOT (discovered and added to sys.path): {project_root}")
else:
    print(f"PROJECT_ROOT (discovery failed or already in sys.path): {project_root}")

# --- End Robust Project Root Discovery ---


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import logging
from urllib.parse import urlparse
from datetime import datetime
from contextlib import asynccontextmanager
import redis.asyncio as redis
import json # Added import for json

from playwright.async_api import async_playwright, Browser # New: Import Playwright Browser

from Link_Profiler.services.crawl_service import CrawlService
from Link_Profiler.services.domain_service import DomainService, SimulatedDomainAPIClient, RealDomainAPIClient, AbstractDomainAPIClient
from Link_Profiler.services.backlink_service import BacklinkService, SimulatedBacklinkAPIClient, RealBacklinkAPIClient, GSCBacklinkAPIClient, OpenLinkProfilerAPIClient
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService
from Link_Profiler.services.expired_domain_finder_service import ExpiredDomainFinderService # Corrected import
from Link_Profiler.services.serp_service import SERPService, SimulatedSERPAPIClient, RealSERPAPIClient
from Link_Profiler.services.keyword_service import KeywordService, SimulatedKeywordAPIClient, RealKeywordAPIClient
from Link_Profiler.services.link_health_service import LinkHealthService
from Link_Profiler.services.ai_service import AIService # New: Import AIService
from Link_Profiler.database.database import Database
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
from Link_Profiler.crawlers.serp_crawler import SERPCrawler
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.core.models import CrawlConfig, CrawlJob, LinkProfile, Backlink, serialize_model, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion
from Link_Profiler.monitoring.prometheus_metrics import (
    API_REQUESTS_TOTAL, API_REQUEST_DURATION_SECONDS, get_metrics_text,
    JOBS_CREATED_TOTAL, JOBS_IN_PROGRESS, JOBS_PENDING, JOBS_COMPLETED_SUCCESS_TOTAL, JOBS_FAILED_TOTAL
)
from Link_Profiler.api.queue_endpoints import add_queue_endpoints, submit_crawl_to_queue, QueueCrawlRequest # Import the function to add queue endpoints and submit_crawl_to_queue
from Link_Profiler.config.config_loader import ConfigLoader # Import the ConfigLoader class
from Link_Profiler.utils.logging_config import setup_logging, get_default_logging_config # New: Import logging setup
from Link_Profiler.utils.data_exporter import export_to_csv # New: Import data_exporter
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import user_agent_manager
from Link_Profiler.utils.proxy_manager import proxy_manager # New: Import proxy_manager

# Initialize and load config once using the absolute path
config_loader = ConfigLoader()
config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

# Setup logging using the loaded configuration
logging_config = config_loader.get("logging.config", get_default_logging_config(config_loader.get("logging.level", "INFO")))
setup_logging(logging_config)

logger = logging.getLogger(__name__) # Get logger after configuration

# Retrieve configurations using the config_loader
REDIS_URL = config_loader.get("redis.url")
DATABASE_URL = config_loader.get("database.url")
DEAD_LETTER_QUEUE_NAME = config_loader.get("queue.dead_letter_queue_name")
CLICKHOUSE_ENABLED = config_loader.get("clickhouse.enabled")
CLICKHOUSE_HOST = config_loader.get("clickhouse.host")
CLICKHOUSE_PORT = config_loader.get("clickhouse.port")
CLICKHOUSE_USER = config_loader.get("clickhouse.user")
CLICKHOUSE_PASSWORD = config_loader.get("clickhouse.password")
API_HOST = config_loader.get("api.host")
API_PORT = config_loader.get("api.port")
MONITOR_PORT = config_loader.get("monitoring.monitor_port")
LOG_LEVEL = config_loader.get("logging.level")
API_CACHE_ENABLED = config_loader.get("api_cache.enabled")
API_CACHE_TTL = config_loader.get("api_cache.ttl")

# Initialize database
db = Database(db_url=DATABASE_URL)

# Initialize Redis connection pool and client
redis_pool = redis.ConnectionPool.from_url(REDIS_URL)
redis_client: Optional[redis.Redis] = redis.Redis(connection_pool=redis_pool) # Make redis_client optional


# Initialize ClickHouse Loader conditionally
clickhouse_loader_instance: Optional[ClickHouseLoader] = None
if CLICKHOUSE_ENABLED:
    logger.info("ClickHouse integration enabled. Attempting to initialize ClickHouseLoader.")
    clickhouse_loader_instance = ClickHouseLoader(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=config_loader.get("clickhouse.database")
    )
else:
    logger.info("ClickHouse integration disabled (USE_CLICKHOUSE is not 'true').")


# Initialize DomainService globally, but manage its lifecycle with lifespan
# Determine which DomainAPIClient to use based on priority: AbstractAPI > Real (paid) > Simulated
if config_loader.get("domain_api.abstract_api.enabled"):
    abstract_api_key = config_loader.get("domain_api.abstract_api.api_key")
    if not abstract_api_key:
        logger.error("ABSTRACT_API_KEY environment variable not set. Falling back to simulated Domain API.")
        domain_service_instance = DomainService(api_client=SimulatedDomainAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL)
    else:
        domain_service_instance = DomainService(api_client=AbstractDomainAPIClient(api_key=abstract_api_key), redis_client=redis_client, cache_ttl=API_CACHE_TTL)
elif config_loader.get("domain_api.real_api.enabled"):
    domain_service_instance = DomainService(api_client=RealDomainAPIClient(api_key=config_loader.get("domain_api.real_api.api_key")), redis_client=redis_client, cache_ttl=API_CACHE_TTL)
else:
    domain_service_instance = DomainService(api_client=SimulatedDomainAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL)

# Initialize BacklinkService based on priority: GSC > OpenLinkProfiler > Real (paid) > Simulated
if config_loader.get("backlink_api.gsc_api.enabled"):
    backlink_service_instance = BacklinkService(api_client=GSCBacklinkAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL)
elif config_loader.get("backlink_api.openlinkprofiler_api.enabled"):
    backlink_service_instance = BacklinkService(api_client=OpenLinkProfilerAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL)
elif config_loader.get("backlink_api.real_api.enabled"):
    backlink_service_instance = BacklinkService(api_client=RealBacklinkAPIClient(api_key=config_loader.get("backlink_api.real_api.api_key")), redis_client=redis_client, cache_ttl=API_CACHE_TTL)
else:
    backlink_service_instance = BacklinkService(api_client=SimulatedBacklinkAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL)

# New: Initialize SERPService and SERPCrawler
serp_crawler_instance = None
if config_loader.get("serp_crawler.playwright.enabled"):
    logger.info("Initialising Playwright SERPCrawler.")
    serp_crawler_instance = SERPCrawler(
        headless=config_loader.get("serp_crawler.playwright.headless"),
        browser_type=config_loader.get("serp_crawler.playwright.browser_type")
    )
serp_service_instance = SERPService(
    api_client=RealSERPAPIClient(api_key=config_loader.get("serp_api.real_api.api_key")) if config_loader.get("serp_api.real_api.enabled") else SimulatedSERPAPIClient(),
    serp_crawler=serp_crawler_instance,
    redis_client=redis_client, # Pass redis_client for caching
    cache_ttl=API_CACHE_TTL # Pass cache_ttl
)

# New: Initialize KeywordService and KeywordScraper
keyword_scraper_instance = None
if config_loader.get("keyword_scraper.enabled"):
    logger.info("Initialising KeywordScraper.")
    keyword_scraper_instance = KeywordScraper()
keyword_service_instance = KeywordService(
    api_client=RealKeywordAPIClient(api_key=config_loader.get("keyword_api.real_api.api_key")) if config_loader.get("keyword_api.real_api.enabled") else SimulatedKeywordAPIClient(),
    keyword_scraper=keyword_scraper_instance,
    redis_client=redis_client, # Pass redis_client for caching
    cache_ttl=API_CACHE_TTL # Pass cache_ttl
)

# New: Initialize LinkHealthService
link_health_service_instance = LinkHealthService(db)

# New: Initialize TechnicalAuditor
technical_auditor_instance = TechnicalAuditor(
    lighthouse_path=config_loader.get("technical_auditor.lighthouse_path") # Allow custom path for Lighthouse CLI
)

# New: Initialize AI Service
ai_service_instance = AIService()

# Initialize DomainAnalyzerService (depends on DomainService)
domain_analyzer_service = DomainAnalyzerService(db, domain_service_instance, ai_service_instance)

# Global Playwright Browser instance for WebCrawler (if enabled)
playwright_browser_instance: Optional[Browser] = None

# Initialize CrawlService (will be used by SatelliteCrawler, not directly by API endpoints for job creation)
# This instance is primarily for the lifespan management of its internal services.
crawl_service_for_lifespan = CrawlService(
    db, 
    backlink_service=backlink_service_instance, 
    domain_service=domain_service_instance,
    serp_service=serp_service_instance,
    keyword_service=keyword_service_instance,
    link_health_service=link_health_service_instance,
    clickhouse_loader=clickhouse_loader_instance, # Pass the potentially None instance
    redis_client=redis_client, # Pass the potentially None instance
    technical_auditor=technical_auditor_instance,
    domain_analyzer_service=domain_analyzer_service, # Pass the domain_analyzer_service
    ai_service=ai_service_instance, # New: Pass AI Service
    playwright_browser=playwright_browser_instance # Pass the global Playwright browser instance
) 
expired_domain_finder_service = ExpiredDomainFinderService(db, domain_service_instance, domain_analyzer_service) # Corrected class name


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for managing the lifespan of the FastAPI application.
    Ensures resources like aiohttp sessions are properly opened and closed.
    """
    # Use a list to hold context managers to ensure they are entered and exited in order
    # and that all are exited even if one fails.
    context_managers = [
        domain_service_instance,
        backlink_service_instance,
        serp_service_instance,
        keyword_service_instance,
        link_health_service_instance,
        technical_auditor_instance,
        ai_service_instance # New: Add AI Service to lifespan
        # Removed crawl_service_for_lifespan as it is not an async context manager itself.
        # Its internal dependencies are already managed here.
    ]

    # Conditionally add ClickHouseLoader to context managers
    if clickhouse_loader_instance:
        context_managers.append(clickhouse_loader_instance)
    # Add Playwright and KeywordScraper contexts if they are enabled
    if serp_crawler_instance:
        context_managers.append(serp_crawler_instance)
    if keyword_scraper_instance:
        context_managers.append(keyword_scraper_instance)

    # New: Conditionally launch global Playwright browser for WebCrawler
    global playwright_browser_instance
    if config_loader.get("browser_crawler.enabled", False):
        browser_type = config_loader.get("browser_crawler.browser_type", "chromium")
        headless = config_loader.get("browser_crawler.headless", True)
        logger.info(f"Application startup: Launching global Playwright browser ({browser_type}, headless={headless})...")
        playwright_instance = await async_playwright().start()
        if browser_type == "chromium":
            playwright_browser_instance = await playwright_instance.chromium.launch(headless=headless)
        elif browser_type == "firefox":
            playwright_browser_instance = await playwright_instance.firefox.launch(headless=headless)
        elif browser_type == "webkit":
            playwright_browser_instance = await playwright_instance.webkit.launch(headless=headless)
        else:
            raise ValueError(f"Unsupported browser type for global browser crawler: {browser_type}")
        
        # Pass this instance to crawl_service_for_lifespan
        crawl_service_for_lifespan.playwright_browser = playwright_browser_instance
        logger.info("Global Playwright browser launched and assigned to CrawlService.")
    else:
        logger.info("Global Playwright browser for WebCrawler is disabled by configuration.")


    # Manually manage the context managers to ensure proper nesting and single yield
    # This pattern ensures all __aenter__ are called before yield, and __aexit__ in reverse order.
    entered_contexts = []
    try:
        for cm in context_managers:
            logger.info(f"Application startup: Entering {cm.__class__.__name__} context.")
            # Call __aenter__ and store the result (which is usually 'self' for context managers)
            entered_contexts.append(await cm.__aenter__())
        
        logger.info("Application startup: Pinging Redis.")
        global redis_client # Declare intent to modify global variable
        if redis_client: # Only try to ping if client was initialized
            try:
                await redis_client.ping()
                logger.info("Redis connection successful.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                redis_client = None # Set to None if connection fails
        else:
            logger.warning("Redis client not initialized. Skipping Redis ping.")
        
        yield # This is the single yield point for the lifespan

    finally:
        # Exit contexts in reverse order of entry
        for cm in reversed(entered_contexts):
            logger.info(f"Application shutdown: Exiting {cm.__class__.__name__} context.")
            # Pass None, None, None for exc_type, exc_val, exc_tb as we're handling exceptions outside
            await cm.__aexit__(None, None, None)
        
        # New: Close global Playwright browser if it was launched
        if playwright_browser_instance:
            logger.info("Application shutdown: Closing global Playwright browser.")
            await playwright_browser_instance.close()
            # Also stop the playwright_instance itself
            if 'playwright_instance' in locals() and playwright_instance:
                await playwright_instance.stop()

        if redis_pool: # Only try to disconnect if pool was created
            logger.info("Application shutdown: Closing Redis connection pool.")
            await redis_pool.disconnect()


app = FastAPI(
    title="Link Profiler API",
    description="API for discovering backlinks and generating link profiles.",
    version="0.1.0",
    lifespan=lifespan # Register the lifespan context manager
)

# --- Middleware for Prometheus Metrics ---
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    
    response = await call_next(request)
    
    process_time = time.perf_counter() - start_time
    endpoint = request.url.path
    method = request.method
    status_code = response.status_code

    API_REQUESTS_TOTAL.labels(endpoint=endpoint, method=method, status_code=status_code).inc()
    API_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint, method=method).observe(process_time)
    
    response.headers["X-Process-Time"] = str(process_time)
    return response

# --- Pydantic Models for API Request/Response ---

class CrawlConfigRequest(BaseModel):
    max_depth: int = Field(3, description="Maximum depth to crawl from seed URLs.")
    max_pages: int = Field(1000, description="Maximum number of pages to crawl.")
    delay_seconds: float = Field(1.0, description="Delay between requests to the same domain in seconds.")
    timeout_seconds: int = Field(30, description="Timeout for HTTP requests in seconds.")
    user_agent: str = Field("LinkProfiler/1.0", description="User-Agent string for the crawler.")
    respect_robots_txt: bool = Field(True, description="Whether to respect robots.txt rules.")
    follow_redirects: bool = Field(True, description="Whether to follow HTTP redirects.")
    extract_images: bool = Field(True, description="Whether to extract image links.")
    extract_pdfs: bool = Field(False, description="Whether to extract links from PDF documents.")
    max_file_size_mb: int = Field(10, description="Maximum file size to download in MB.")
    allowed_domains: Optional[List[str]] = Field(None, description="List of domains explicitly allowed to crawl. If empty, all domains are allowed unless blocked.")
    blocked_domains: Optional[List[str]] = Field(None, description="List of domains explicitly blocked from crawling.")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom HTTP headers to send with requests.")
    max_retries: int = Field(3, description="Maximum number of retries for failed URL fetches.")
    retry_delay_seconds: float = Field(5.0, description="Delay between retries in seconds.")
    user_agent_rotation: bool = Field(False, description="Whether to rotate user agents from a pool.")
    request_header_randomization: bool = Field(False, description="Whether to randomize other request headers (Accept, Accept-Language, etc.).")
    human_like_delays: bool = Field(False, description="Whether to add small random delays to mimic human browsing behavior.")
    stealth_mode: bool = Field(True, description="Whether to enable Playwright stealth mode for browser-based crawling.")
    browser_fingerprint_randomization: bool = Field(False, description="Whether to randomize browser fingerprint properties (e.g., device scale, mobile, touch, screen dimensions, timezone, locale, color scheme) for Playwright.")
    ml_rate_optimization: bool = Field(False, description="Whether to enable machine learning-based rate optimization for adaptive delays.")
    captcha_solving_enabled: bool = Field(False, description="Whether to enable CAPTCHA solving for browser-based crawls.")
    anomaly_detection_enabled: bool = Field(False, description="Whether to enable real-time anomaly detection.")
    use_proxies: bool = Field(False, description="Whether to use proxies for crawling.")
    proxy_list: Optional[List[Dict[str, str]]] = Field(None, description="List of proxy configurations (e.g., [{'url': 'http://user:pass@ip:port', 'region': 'us-east'}]).")
    proxy_region: Optional[str] = Field(None, description="Desired proxy region for this crawl job. If not specified, any available proxy will be used.")
    render_javascript: bool = Field(False, description="Whether to use a headless browser to render JavaScript content for crawling.")
    browser_type: Optional[str] = Field("chromium", description="Browser type for headless rendering (chromium, firefox, webkit). Only applicable if render_javascript is true.")
    headless_browser: bool = Field(True, description="Whether the browser should run in headless mode. Only applicable if render_javascript is true.")
    extract_image_text: bool = Field(False, description="Whether to perform OCR on images to extract text.")
    crawl_web3_content: bool = Field(False, description="Whether to crawl Web3 content (e.g., IPFS, blockchain data).")
    crawl_social_media: bool = Field(False, description="Whether to crawl social media content.")


class StartCrawlRequest(BaseModel):
    target_url: str = Field(..., description="The URL for which to find backlinks (e.g., 'https://example.com').")
    initial_seed_urls: List[str] = Field(..., description="A list of URLs to start crawling from to discover backlinks.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration.")

class LinkHealthAuditRequest(BaseModel):
    source_urls: List[str] = Field(..., description="A list of source URLs whose outgoing links should be audited for brokenness.")

class TechnicalAuditRequest(BaseModel):
    urls_to_audit: List[str] = Field(..., description="A list of URLs to perform a technical audit on using Lighthouse.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration for the audit (e.g., user agent).")

class DomainAnalysisJobRequest(BaseModel): # New Pydantic model for domain analysis job submission
    domain_names: List[str] = Field(..., description="A list of domain names to analyze.")
    min_value_score: Optional[float] = Field(None, description="Minimum value score for a domain to be considered valuable.")
    limit: Optional[int] = Field(None, description="Maximum number of valuable domains to return.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration for the analysis (e.g., user agent).")

class FullSEOAduitRequest(BaseModel): # New Pydantic model for full SEO audit job submission
    urls_to_audit: List[str] = Field(..., description="A list of URLs to perform a full SEO audit on.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration for the audit (e.g., user agent).")

class Web3CrawlRequest(BaseModel): # New Pydantic model for Web3 crawl job submission
    web3_content_identifier: str = Field(..., description="The identifier for Web3 content (e.g., IPFS hash, blockchain address).")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration.")

class SocialMediaCrawlRequest(BaseModel): # New Pydantic model for Social Media crawl job submission
    social_media_query: str = Field(..., description="The query for social media content (e.g., hashtag, username, profile URL).")
    platforms: Optional[List[str]] = Field(None, description="Specific social media platforms to crawl (e.g., 'twitter', 'facebook'). If None, all configured platforms will be used.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration.")


class CrawlErrorResponse(BaseModel):
    timestamp: datetime
    url: str
    error_type: str
    message: str
    details: Optional[str]

    @classmethod
    def from_crawl_error(cls, error: CrawlError):
        return cls(**serialize_model(error))


class CrawlJobResponse(BaseModel):
    id: str

    target_url: str
    job_type: str
    status: CrawlStatus # Keep as Enum type hint
    created_date: datetime
    started_date: Optional[datetime]
    completed_date: Optional[datetime]
    progress_percentage: float
    urls_crawled: int
    links_found: int
    errors_count: int
    error_log: List[CrawlErrorResponse]
    results: Dict = Field(default_factory=dict)

    @classmethod
    def from_crawl_job(cls, job: CrawlJob):
        # Convert CrawlJob dataclass to a dictionary
        job_dict = serialize_model(job)
        
        # Explicitly convert Enum to its value string for Pydantic
        job_dict['status'] = job.status.value 

        if isinstance(job_dict.get('created_date'), str):
            try:
                job_dict['created_date'] = datetime.fromisoformat(job_dict['created_date'])
            except ValueError:
                 logger.warning(f"Could not parse created_date string: {job_dict.get('created_date')}")
                 job_dict['created_date'] = None

        if isinstance(job_dict.get('started_date'), str):
             try:
                job_dict['started_date'] = datetime.fromisoformat(job_dict['started_date'])
             except ValueError:
                 logger.warning(f"Could not parse started_date string: {job_dict.get('started_date')}")
                 job_dict['started_date'] = None

        if isinstance(job_dict.get('completed_date'), str):
             try:
                job_dict['completed_date'] = datetime.fromisoformat(job_dict['completed_date'])
             except ValueError:
                 logger.warning(f"Could not parse completed_date string: {job_dict.get('completed_date')}")
                 job_dict['completed_date'] = None

        job_dict['error_log'] = [CrawlErrorResponse.from_crawl_error(err) for err in job.error_log]

        return cls(**job_dict)

class LinkProfileResponse(BaseModel):
    target_url: str
    target_domain: str
    total_backlinks: int
    unique_domains: int
    dofollow_links: int
    nofollow_links: int
    authority_score: float
    trust_score: float
    spam_score: float
    anchor_text_distribution: Dict[str, int]
    referring_domains: List[str] # Convert set to list for JSON serialization
    analysis_date: datetime

    @classmethod
    def from_link_profile(cls, profile: LinkProfile):
        profile_dict = serialize_model(profile)
        profile_dict['referring_domains'] = list(profile.referring_domains) # Ensure it's a list
        if isinstance(profile_dict.get('analysis_date'), str):
            try:
                profile_dict['analysis_date'] = datetime.fromisoformat(profile_dict['analysis_date'])
            except ValueError:
                 logger.warning(f"Could not parse analysis_date string: {profile_dict.get('analysis_date')}")
                 profile_dict['analysis_date'] = None
        return cls(**profile_dict)

class BacklinkResponse(BaseModel):
    source_url: str
    target_url: str
    source_domain: str
    target_domain: str
    anchor_text: str
    link_type: LinkType 
    rel_attributes: List[str] = Field(default_factory=list)
    context_text: str
    is_image_link: bool
    alt_text: Optional[str]
    discovered_date: datetime
    authority_passed: float
    spam_level: SpamLevel 
    http_status: Optional[int] = None
    crawl_timestamp: Optional[datetime] = None
    source_domain_metrics: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_backlink(cls, backlink: Backlink):
        backlink_dict = serialize_model(backlink)
        
        backlink_dict['link_type'] = LinkType(backlink.link_type.value)
        backlink_dict['spam_level'] = SpamLevel(backlink.spam_level.value)
        
        if isinstance(backlink_dict.get('discovered_date'), str):
            try:
                backlink_dict['discovered_date'] = datetime.fromisoformat(backlink_dict['discovered_date'])
            except ValueError:
                 logger.warning(f"Could not parse discovered_date string: {backlink_dict.get('discovered_date')}")
                 backlink_dict['discovered_date'] = None
        if isinstance(backlink_dict.get('crawl_timestamp'), str):
            try:
                backlink_dict['crawl_timestamp'] = datetime.fromisoformat(backlink_dict['crawl_timestamp'])
            except ValueError:
                 logger.warning(f"Could not parse crawl_timestamp string: {backlink_dict.get('crawl_timestamp')}")
                 backlink_dict['crawl_timestamp'] = None
        return cls(**backlink_dict)

class DomainResponse(BaseModel):
    name: str
    authority_score: float
    trust_score: float
    spam_score: float
    age_days: Optional[int]
    country: Optional[str]
    ip_address: Optional[str]
    whois_data: Dict
    total_pages: int

    total_backlinks: int
    referring_domains: int
    first_seen: Optional[datetime]
    last_crawled: Optional[datetime]

    @classmethod
    def from_domain(cls, domain: Domain):
        domain_dict = serialize_model(domain)
        if isinstance(domain_dict.get('first_seen'), str):
            try:
                domain_dict['first_seen'] = datetime.fromisoformat(domain_dict['first_seen'])
            except ValueError:
                 logger.warning(f"Could not parse first_seen string: {domain_dict.get('first_seen')}")
                 domain_dict['first_seen'] = None
        if isinstance(domain_dict.get('last_crawled'), str):
            try:
                domain_dict['last_crawled'] = datetime.fromisoformat(domain_dict['last_crawled'])
            except ValueError:
                 logger.warning(f"Could not parse last_crawled string: {domain_dict.get('last_crawled')}")
                 domain_dict['last_crawled'] = None
        return cls(**domain_dict)

class DomainAnalysisResponse(BaseModel):
    domain_name: str

    value_score: float
    is_valuable: bool
    reasons: List[str]
    details: Dict[str, Any]

class FindExpiredDomainsRequest(BaseModel):
    potential_domains: List[str] = Field(..., description="A list of domain names to check for expiration and value.")
    min_value_score: float = Field(50.0, description="Minimum value score a domain must have to be considered valuable.")
    limit: Optional[int] = Field(None, description="Maximum number of valuable domains to return.")

class FindExpiredDomainsResponse(BaseModel):
    found_domains: List[DomainAnalysisResponse]
    total_candidates_processed: int
    valuable_domains_found: int

class SERPSearchRequest(BaseModel):
    keyword: str = Field(..., description="The search term to get SERP results for.")
    num_results: int = Field(10, description="Number of SERP results to fetch.")
    search_engine: str = Field("google", description="The search engine to use (e.g., 'google', 'bing').")

class SERPResultResponse(BaseModel):
    keyword: str
    position: int
    result_url: str
    title_text: str
    snippet_text: Optional[str] = None
    rich_features: List[str] = Field(default_factory=list)
    page_load_time: Optional[float] = None
    crawl_timestamp: datetime

    @classmethod
    def from_serp_result(cls, result: SERPResult):
        result_dict = serialize_model(result)
        if isinstance(result_dict.get('crawl_timestamp'), str):
            try:
                result_dict['crawl_timestamp'] = datetime.fromisoformat(result_dict['crawl_timestamp'])
            except ValueError:
                logger.warning(f"Could not parse crawl_timestamp string: {result_dict.get('crawl_timestamp')}")
                result_dict['crawl_timestamp'] = None
        return cls(**result_dict)

class KeywordSuggestRequest(BaseModel):
    seed_keyword: str = Field(..., description="The initial keyword to get suggestions for.")
    num_suggestions: int = Field(10, description="Number of keyword suggestions to fetch.")

class KeywordSuggestionResponse(BaseModel):
    seed_keyword: str
    suggested_keyword: str
    search_volume_monthly: Optional[int] = None
    cpc_estimate: Optional[float] = None
    keyword_trend: List[float] = Field(default_factory=list)
    competition_level: Optional[str] = None
    data_timestamp: datetime

    @classmethod

    def from_keyword_suggestion(cls, suggestion: KeywordSuggestion):
        suggestion_dict = serialize_model(suggestion)
        if isinstance(suggestion_dict.get('data_timestamp'), str):
            try:
                suggestion_dict['data_timestamp'] = datetime.fromisoformat(suggestion_dict['data_timestamp'])
            except ValueError:
                logger.warning(f"Could not parse data_timestamp string: {suggestion_dict.get('data_timestamp')}")
                suggestion_dict['data_timestamp'] = None
        return cls(**suggestion_dict)


# --- API Endpoints ---

@app.post("/crawl/start_backlink_discovery", response_model=Dict[str, str], status_code=202)
async def start_backlink_discovery(
    request: StartCrawlRequest, 
    background_tasks: BackgroundTasks
):
    """
    Submits a new backlink discovery job to the queue.
    """
    logger.info(f"Received request to submit backlink discovery for {request.target_url} to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='backlink_discovery').inc()
    
    # Convert StartCrawlRequest to QueueCrawlRequest
    queue_request = QueueCrawlRequest(
        target_url=request.target_url,
        initial_seed_urls=request.initial_seed_urls,
        config=request.config.dict() if request.config else {},
        priority=5 # Default priority
    )
    
    return await submit_crawl_to_queue(queue_request)

@app.post("/audit/link_health", response_model=Dict[str, str], status_code=202)
async def start_link_health_audit(
    request: LinkHealthAuditRequest,
    background_tasks: BackgroundTasks
):
    """
    Submits a new link health audit job to the queue.
    """
    logger.info(f"Received request to submit link health audit for {len(request.source_urls)} URLs to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='link_health_audit').inc()

    if not request.source_urls:
        raise HTTPException(status_code=400, detail="At least one source URL must be provided for link health audit.")
    
    # For link health audit, target_url can be the first source_url or a generic placeholder
    target_url = request.source_urls[0] if request.source_urls else "N/A"

    queue_request = QueueCrawlRequest(
        target_url=target_url,
        initial_seed_urls=request.source_urls, # Re-using initial_seed_urls for source_urls_to_audit
        config={"job_specific_param": "source_urls_to_audit"}, # Add a flag for job type
        priority=5
    )
    queue_request.config["source_urls_to_audit"] = request.source_urls # Pass actual list
    queue_request.config["job_type"] = "link_health_audit" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.post("/audit/technical_audit", response_model=Dict[str, str], status_code=202)
async def start_technical_audit(
    request: TechnicalAuditRequest,
    background_tasks: BackgroundTasks
):
    """
    Submits a new technical audit job to the queue.
    """
    logger.info(f"Received request to submit technical audit for {len(request.urls_to_audit)} URLs to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='technical_audit').inc()

    if not request.urls_to_audit:
        raise HTTPException(status_code=400, detail="At least one URL must be provided for technical audit.")
    
    # For technical audit, target_url can be the first url_to_audit or a generic placeholder
    target_url = request.urls_to_audit[0] if request.urls_to_audit else "N/A"

    queue_request = QueueCrawlRequest(
        target_url=target_url,
        initial_seed_urls=request.urls_to_audit, # Re-using initial_seed_urls for urls_to_audit_tech
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["urls_to_audit_tech"] = request.urls_to_audit # Pass actual list
    queue_request.config["job_type"] = "technical_audit" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.post("/audit/full_seo_audit", response_model=Dict[str, str], status_code=202) # New endpoint
async def start_full_seo_audit(
    request: FullSEOAduitRequest,
    background_tasks: BackgroundTasks
):
    """
    Submits a new full SEO audit job to the queue.
    This job orchestrates technical and link health audits.
    """
    logger.info(f"Received request to submit full SEO audit for {len(request.urls_to_audit)} URLs to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='full_seo_audit').inc()

    if not request.urls_to_audit:
        raise HTTPException(status_code=400, detail="At least one URL must be provided for full SEO audit.")
    
    target_url = request.urls_to_audit[0] if request.urls_to_audit else "N/A"

    queue_request = QueueCrawlRequest(
        target_url=target_url,
        initial_seed_urls=request.urls_to_audit, # Re-using for urls_to_audit_full_seo
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["urls_to_audit_full_seo"] = request.urls_to_audit # Pass actual list
    queue_request.config["job_type"] = "full_seo_audit" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.post("/domain/analyze_batch", response_model=Dict[str, str], status_code=202) # New endpoint
async def start_domain_analysis_job(
    request: DomainAnalysisJobRequest,
    background_tasks: BackgroundTasks
):
    """
    Submits a new batch domain analysis job to the queue.
    """
    logger.info(f"Received request to submit domain analysis for {len(request.domain_names)} domains to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='domain_analysis').inc()

    if not request.domain_names:
        raise HTTPException(status_code=400, detail="At least one domain name must be provided for analysis.")
    
    # For domain analysis, target_url can be the first domain name or a generic placeholder
    target_url = request.domain_names[0] if request.domain_names else "N/A"

    queue_request = QueueCrawlRequest(
        target_url=target_url,
        initial_seed_urls=[], # Not applicable for this job type
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["domain_names_to_analyze"] = request.domain_names
    queue_request.config["min_value_score"] = request.min_value_score
    queue_request.config["limit"] = request.limit
    queue_request.config["job_type"] = "domain_analysis" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.post("/web3/crawl", response_model=Dict[str, str], status_code=202) # New endpoint
async def start_web3_crawl(
    request: Web3CrawlRequest,
    background_tasks: BackgroundTasks
):
    """
    Submits a new Web3 content crawl job to the queue.
    """
    logger.info(f"Received request to submit Web3 crawl for identifier: {request.web3_content_identifier} to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='web3_crawl').inc()

    queue_request = QueueCrawlRequest(
        target_url=request.web3_content_identifier, # Target URL can be the Web3 identifier
        initial_seed_urls=[], # Not applicable for Web3 crawl
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["web3_content_identifier"] = request.web3_content_identifier
    queue_request.config["job_type"] = "web3_crawl" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.post("/social_media/crawl", response_model=Dict[str, str], status_code=202) # New endpoint
async def start_social_media_crawl(
    request: SocialMediaCrawlRequest,
    background_tasks: BackgroundTasks
):
    """
    Submits a new social media content crawl job to the queue.
    """
    logger.info(f"Received request to submit social media crawl for query: {request.social_media_query} to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='social_media_crawl').inc()

    queue_request = QueueCrawlRequest(
        target_url=request.social_media_query, # Target URL can be the social media query
        initial_seed_urls=[], # Not applicable for social media crawl
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["social_media_query"] = request.social_media_query
    queue_request.config["platforms"] = request.platforms
    queue_request.config["job_type"] = "social_media_crawl" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)


@app.get("/crawl/status/{job_id}", response_model=CrawlJobResponse)
async def get_crawl_status(job_id: str):
    """
    Retrieves the current status of a specific crawl job.
    """
    job = db.get_crawl_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found.")
    return CrawlJobResponse.from_crawl_job(job)

@app.get("/crawl/all_jobs", response_model=List[CrawlJobResponse])
async def get_all_crawl_jobs():
    """
    Retrieves a list of all crawl jobs in the system.
    """
    logger.info("Received request for all crawl jobs.")
    jobs = db.get_all_crawl_jobs() # New method call
    return [CrawlJobResponse.from_crawl_job(job) for job in jobs]

@app.post("/crawl/pause/{job_id}", response_model=CrawlJobResponse)
async def pause_crawl_job(job_id: str):
    """
    Pauses an in-progress crawl job.
    """
    try:
        job = await crawl_service_for_lifespan.pause_crawl_job(job_id) # Use the lifespan-managed instance
        # Prometheus: Update gauge for job status
        if job.job_type:
            JOBS_IN_PROGRESS.labels(job_type=job.job_type).dec()
            JOBS_PENDING.labels(job_type=job.job_type).inc() # Treat paused as pending for simplicity
        return CrawlJobResponse.from_crawl_job(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error pausing crawl job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to pause job: {e}")

@app.post("/crawl/resume/{job_id}", response_model=CrawlJobResponse)
async def resume_crawl_job(job_id: str):
    """
    Resumes a paused crawl job.
    """
    try:
        job = await crawl_service_for_lifespan.resume_crawl_job(job_id) # Use the lifespan-managed instance
        # Prometheus: Update gauge for job status
        if job.job_type:
            JOBS_PENDING.labels(job_type=job.job_type).dec()
            JOBS_IN_PROGRESS.labels(job_type=job.job_type).inc()
        return CrawlJobResponse.from_crawl_job(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error resuming crawl job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to resume job: {e}")

@app.post("/crawl/stop/{job_id}", response_model=CrawlJobResponse)
async def stop_crawl_job(job_id: str):
    """
    Stops an active or paused crawl job.
    """
    try:
        job = await crawl_service_for_lifespan.stop_crawl_job(job_id) # Use the lifespan-managed instance
        # Prometheus: Update gauge for job status
        if job.job_type:
            if job.status == CrawlStatus.STOPPED: # Only decrement if it was actually in progress/paused
                if job.job_type:
                    JOBS_IN_PROGRESS.labels(job_type=job.job_type).dec()
                    # If it was pending/paused, decrement that too
                    # This assumes a job is either IN_PROGRESS or PENDING before being STOPPED
                    # A more robust solution would check the previous state.
                    # For simplicity, we'll just decrement IN_PROGRESS and increment FAILED.
                    JOBS_FAILED_TOTAL.labels(job_type=job.job_type).inc() # Treat stopped as a form of failure for metrics
        return CrawlJobResponse.from_crawl_job(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error stopping crawl job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop job: {e}")

@app.get("/link_profile/{target_url:path}", response_model=LinkProfileResponse)
async def get_link_profile(target_url: str):
    """
    Retrieves the link profile for a given target URL.
    """
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    profile = db.get_link_profile(target_url)
    if not profile:
        raise HTTPException(status_code=404, detail="Link profile not found for this URL. A crawl might not have been completed yet.")
    return LinkProfileResponse.from_link_profile(profile)

@app.get("/backlinks/{target_url:path}", response_model=List[BacklinkResponse])
async def get_backlinks(target_url: str):
    """
    Retrieves all raw backlinks found for a given target URL.
    """
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    backlinks = db.get_backlinks_for_target(target_url) 
    
    if not backlinks:
        raise HTTPException(status_code=404, detail=f"No backlinks found for target URL {target_url}.")
    
    return [BacklinkResponse.from_backlink(bl) for bl in backlinks]

@app.get("/debug/all_backlinks", response_model=List[BacklinkResponse])
async def debug_get_all_backlinks():
    """
    DEBUG endpoint: Retrieves ALL raw backlinks from the database.
    """
    logger.info("DEBUG endpoint: Received request for all backlinks.")
    backlinks = db.get_all_backlinks()
    logger.info(f"DEBUG endpoint: Retrieved {len(backlinks)} backlinks from DB.")
    return [BacklinkResponse.from_backlink(bl) for bl in backlinks]

@app.get("/export/backlinks.csv", response_class=Response)
async def export_all_backlinks_csv():
    """
    Exports all backlinks from the database to a CSV file.
    """
    logger.info("Received request to export all backlinks to CSV.")
    backlinks = db.get_all_backlinks()
    
    if not backlinks:
        raise HTTPException(status_code=404, detail="No backlinks found to export.")
    
    # Convert list of Backlink objects to list of dictionaries
    backlink_dicts = [serialize_model(bl) for bl in backlinks]
    
    # Define fieldnames explicitly to ensure order and include all relevant fields
    fieldnames = [
        "id", "source_url", "target_url", "source_domain", "target_domain",
        "anchor_text", "link_type", "rel_attributes", "context_text",
        "position_on_page", "is_image_link", "alt_text", "discovered_date",
        "last_seen_date", "authority_passed", "is_active", "spam_level",
        "http_status", "crawl_timestamp", "source_domain_metrics"
    ]
    
    csv_output = await export_to_csv(backlink_dicts, fieldnames=fieldnames)
    
    headers = {
        "Content-Disposition": "attachment; filename=all_backlinks.csv",
        "Content-Type": "text/csv"
    }
    return Response(content=csv_output.getvalue(), headers=headers, media_type="text/csv")

@app.get("/export/link_profiles.csv", response_class=Response)
async def export_all_link_profiles_csv():
    """
    Exports all link profiles from the database to a CSV file.
    """
    logger.info("Received request to export all link profiles to CSV.")
    link_profiles = db.get_all_link_profiles() # Assuming a get_all_link_profiles method exists
    
    if not link_profiles:
        raise HTTPException(status_code=404, detail="No link profiles found to export.")
    
    link_profile_dicts = [serialize_model(lp) for lp in link_profiles]
    
    fieldnames = [
        "target_url", "target_domain", "total_backlinks", "unique_domains",
        "dofollow_links", "nofollow_links", "authority_score", "trust_score",
        "spam_score", "anchor_text_distribution", "referring_domains",
        "analysis_date"
    ]
    
    csv_output = await export_to_csv(link_profile_dicts, fieldnames=fieldnames)
    
    headers = {
        "Content-Disposition": "attachment; filename=all_link_profiles.csv",
        "Content-Type": "text/csv"
    }
    return Response(content=csv_output.getvalue(), headers=headers, media_type="text/csv")

@app.get("/export/crawl_jobs.csv", response_class=Response)
async def export_all_crawl_jobs_csv():
    """
    Exports all crawl jobs from the database to a CSV file.
    """
    logger.info("Received request to export all crawl jobs to CSV.")
    crawl_jobs = db.get_all_crawl_jobs()
    
    if not crawl_jobs:
        raise HTTPException(status_code=404, detail="No crawl jobs found to export.")
    
    crawl_job_dicts = [serialize_model(job) for job in crawl_jobs]
    
    fieldnames = [
        "id", "target_url", "job_type", "status", "priority", "created_date",
        "started_date", "completed_date", "progress_percentage", "urls_discovered",
        "urls_crawled", "links_found", "errors_count", "config", "results", "error_log"
    ]
    
    csv_output = await export_to_csv(crawl_job_dicts, fieldnames=fieldnames)
    
    headers = {
        "Content-Disposition": "attachment; filename=all_crawl_jobs.csv",
        "Content-Type": "text/csv"
    }
    return Response(content=csv_output.getvalue(), headers=headers, media_type="text/csv")


@app.get("/domain/availability/{domain_name}", response_model=Dict[str, Union[str, bool]])
async def check_domain_availability(domain_name: str):
    """
    Checks if a domain name is available for registration.
    """
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    is_available = await domain_service_instance.check_domain_availability(domain_name)
    return {"domain_name": domain_name, "is_available": is_available}

@app.get("/domain/whois/{domain_name}", response_model=Dict)
async def get_domain_whois(domain_name: str):
    """
    Retrieves WHOIS information for a given domain name.
    """
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    whois_info = await domain_service_instance.get_whois_info(domain_name)
    if not whois_info:
        raise HTTPException(status_code=404, detail="WHOIS information not found for this domain.")
    return whois_info

@app.get("/domain/info/{domain_name}", response_model=DomainResponse)
async def get_domain_info(domain_name: str):
    """
    Retrieves comprehensive domain information, including simulated WHOIS and availability.
    """
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    domain_obj = await domain_service_instance.get_domain_info(domain_name)
    if not domain_obj:
        raise HTTPException(status_code=404, detail="Domain information not found.")
    return DomainResponse.from_domain(domain_obj)

@app.get("/domain/analyze/{domain_name}", response_model=DomainAnalysisResponse)
async def analyze_domain(domain_name: str):
    """
    Analyzes a domain for its potential value, especially for expired domains.
    """
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    analysis_result = await domain_analyzer_service.analyze_domain_for_expiration_value(domain_name)
    
    if not analysis_result:
        raise HTTPException(status_code=404, detail="Failed to perform domain analysis, domain info not found or error occurred.")
    
    return analysis_result

@app.post("/domain/find_expired_domains", response_model=FindExpiredDomainsResponse)
async def find_expired_domains(request: FindExpiredDomainsRequest):
    """
    Searches for valuable expired domains among a list of potential candidates.
    """
    if not request.potential_domains:
        raise HTTPException(status_code=400, detail="No potential domains provided.")
    
    found_domains = await expired_domain_finder_service.find_valuable_expired_domains(
        potential_domains=request.potential_domains,
        min_value_score=request.min_value_score,
        limit=request.limit
    )
    
    return FindExpiredDomainsResponse(
        found_domains=found_domains,
        total_candidates_processed=len(request.potential_domains),
        valuable_domains_found=len(found_domains)
    )

@app.post("/serp/search", response_model=Dict[str, str], status_code=202)
async def search_serp(request: SERPSearchRequest):
    """
    Submits a SERP search job to the queue.
    """
    logger.info(f"Received request to submit SERP search for keyword: {request.keyword} to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='serp_analysis').inc()

    queue_request = QueueCrawlRequest(
        target_url=request.keyword, # Target URL can be the keyword for this job type
        initial_seed_urls=[], # Not applicable for SERP search
        config={"keyword": request.keyword, "num_results": request.num_results, "search_engine": request.search_engine},
        priority=5
    )
    queue_request.config["job_type"] = "serp_analysis" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.get("/serp/results/{keyword}", response_model=List[SERPResultResponse])
async def get_serp_results(keyword: str):
    """
    Retrieves stored SERP results for a specific keyword.
    """
    logger.info(f"Received request to get stored SERP results for keyword: {keyword}")
    try:
        serp_results = db.get_serp_results_for_keyword(keyword)
        if not serp_results:
            raise HTTPException(status_code=404, detail=f"No SERP results found for keyword '{keyword}'.")
        return [SERPResultResponse.from_serp_result(res) for res in serp_results]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving stored SERP results for '{keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve SERP results: {e}")

@app.post("/keyword/suggest", response_model=Dict[str, str], status_code=202)
async def suggest_keywords(request: KeywordSuggestRequest):
    """
    Submits a keyword suggestion job to the queue.
    """
    logger.info(f"Received request to submit keyword suggestions for seed: {request.seed_keyword} to queue.")
    JOBS_CREATED_TOTAL.labels(job_type='keyword_research').inc()

    queue_request = QueueCrawlRequest(
        target_url=request.seed_keyword, # Target URL can be the seed_keyword for keyword jobs
        initial_seed_urls=[], # Not applicable
        config={"seed_keyword": request.seed_keyword, "num_suggestions": request.num_suggestions},
        priority=5
    )
    queue_request.config["job_type"] = "keyword_research" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.get("/keyword/suggestions/{seed_keyword}", response_model=List[KeywordSuggestionResponse])
async def get_keyword_suggestions(seed_keyword: str):
    """
    Retrieves stored keyword suggestions for a specific seed keyword.
    """
    logger.info(f"Received request to get stored keyword suggestions for seed: {seed_keyword}")
    try:
        suggestions = db.get_keyword_suggestions_for_seed(seed_keyword)
        if not suggestions:
            raise HTTPException(status_code=404, detail=f"No keyword suggestions found for seed '{seed_keyword}'.")
        return [KeywordSuggestionResponse.from_keyword_suggestion(sug) for sug in suggestions]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving stored keyword suggestions for '{seed_keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve keyword suggestions: {e}")

@app.get("/health")
async def health_check():
    """
    Performs a comprehensive health check of the API and its dependencies.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dependencies": {}
    }

    # Check Redis connectivity
    try:
        if redis_client:
            await redis_client.ping()
            health_status["dependencies"]["redis"] = {"status": "connected"}
        else:
            health_status["dependencies"]["redis"] = {"status": "disabled", "message": "Redis client not initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["redis"] = {"status": "disconnected", "error": str(e)}
        logger.error(f"Health check: Redis connection failed: {e}")

    # Check PostgreSQL connectivity
    try:
        db.ping() # Assuming Database class has a ping method
        health_status["dependencies"]["postgresql"] = {"status": "connected"}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["postgresql"] = {"status": "disconnected", "error": str(e)}
        logger.error(f"Health check: PostgreSQL connection failed: {e}")

    # Check external API services (Domain, Backlink, SERP, Keyword, AI)
    # This is a high-level check, not a deep ping to external APIs
    
    # Domain Service
    try:
        async with domain_service_instance as ds:
            # Attempt a lightweight operation or just check if client is active
            if ds.api_client:
                health_status["dependencies"]["domain_service"] = {"status": "ready", "client": ds.api_client.__class__.__name__}
            else:
                health_status["dependencies"]["domain_service"] = {"status": "not_ready", "message": "API client not initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["domain_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: Domain Service failed: {e}")

    # Backlink Service
    try:
        async with backlink_service_instance as bs:
            if bs.api_client:
                health_status["dependencies"]["backlink_service"] = {"status": "ready", "client": bs.api_client.__class__.__name__}
            else:
                health_status["dependencies"]["backlink_service"] = {"status": "not_ready", "message": "API client not initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["backlink_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: Backlink Service failed: {e}")

    # SERP Service
    try:
        async with serp_service_instance as ss:
            if ss.api_client or ss.serp_crawler:
                health_status["dependencies"]["serp_service"] = {"status": "ready", "client": ss.api_client.__class__.__name__}
            else:
                health_status["dependencies"]["serp_service"] = {"status": "not_ready", "message": "No client or crawler initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["serp_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: SERP Service failed: {e}")

    # Keyword Service
    try:
        async with keyword_service_instance as ks:
            if ks.api_client or ks.keyword_scraper:
                health_status["dependencies"]["keyword_service"] = {"status": "ready", "client": ks.api_client.__class__.__name__}
            else:
                health_status["dependencies"]["keyword_service"] = {"status": "not_ready", "message": "No client or scraper initialized."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["keyword_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: Keyword Service failed: {e}")

    # AI Service
    try:
        async with ai_service_instance as ais:
            if ais.enabled:
                health_status["dependencies"]["ai_service"] = {"status": "enabled", "client": ais.openrouter_client.__class__.__name__}
            else:
                health_status["dependencies"]["ai_service"] = {"status": "disabled", "message": "AI service is disabled by config or missing API key."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["ai_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: AI Service failed: {e}")

    # ClickHouse Loader
    try:
        if clickhouse_loader_instance:
            # Ping ClickHouse if enabled
            await clickhouse_loader_instance.__aenter__() # Temporarily enter context to ping
            if clickhouse_loader_instance.client:
                health_status["dependencies"]["clickhouse_loader"] = {"status": "connected"}
            else:
                health_status["dependencies"]["clickhouse_loader"] = {"status": "disconnected", "message": "Client not active after init."}
            await clickhouse_loader_instance.__aexit__(None, None, None) # Exit context
        else:
            health_status["dependencies"]["clickhouse_loader"] = {"status": "disabled", "message": "ClickHouse integration is disabled."}
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["clickhouse_loader"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: ClickHouse Loader failed: {e}")


    status_code = 200 if health_status["status"] == "healthy" else 503
    return Response(content=json.dumps(health_status, indent=2), media_type="application/json", status_code=status_code)


@app.get("/metrics", response_class=Response)
async def prometheus_metrics():
    """
    Exposes Prometheus metrics.
    """
    return Response(content=get_metrics_text(), media_type="text/plain; version=0.0.4; charset=utf-8")

@app.get("/debug/dead_letters")
async def get_dead_letters():
    """
    DEBUG endpoint: Retrieves messages from the Redis dead-letter queue.
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis is not available, dead-letter queue cannot be accessed.")
    
    dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name")
    try:
        # Fetch all items from the dead-letter queue without removing them
        messages = await redis_client.lrange(dead_letter_queue_name, 0, -1)
        decoded_messages = [json.loads(msg.decode('utf-8')) for msg in messages]
        logger.info(f"Retrieved {len(decoded_messages)} messages from dead-letter queue.")
        return {"dead_letter_messages": decoded_messages}
    except Exception as e:
        logger.error(f"Error retrieving dead-letter messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve dead-letter messages: {e}")

@app.post("/debug/clear_dead_letters")
async def clear_dead_letters():
    """
    DEBUG endpoint: Clears all messages from the Redis dead-letter queue.
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis is not available, dead-letter queue cannot be cleared.")
    
    dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name")
    try:
        count = await redis_client.delete(dead_letter_queue_name)
        logger.info(f"Cleared {count} messages from dead-letter queue.")
        return {"status": "success", "message": f"Cleared {count} messages from dead-letter queue."}
    except Exception as e:
        logger.error(f"Error clearing dead-letter messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear dead-letter messages: {e}")

@app.post("/debug/reprocess_dead_letters", response_model=Dict[str, str])
async def reprocess_dead_letters():
    """
    DEBUG endpoint: Moves all messages from the dead-letter queue back to the main job queue for reprocessing.
    """
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis is not available, dead-letter queue cannot be reprocessed.")
    
    dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name")
    job_queue_name = config_loader.get("queue.job_queue_name", "crawl_jobs") # Assuming default job queue name
    
    try:
        messages = await redis_client.lrange(dead_letter_queue_name, 0, -1)
        if not messages:
            return {"status": "success", "message": "Dead-letter queue is empty. Nothing to reprocess."}
        
        requeued_count = 0
        for msg in messages:
            try:
                job_data = json.loads(msg.decode('utf-8'))
                # Remove dead_letter_reason and timestamp before re-queuing
                job_data.pop('dead_letter_reason', None)
                job_data.pop('dead_letter_timestamp', None)
                
                # Optionally reset status to PENDING if it was FAILED
                if job_data.get('status') == CrawlStatus.FAILED.value:
                    job_data['status'] = CrawlStatus.PENDING.value
                    job_data['errors_count'] = 0
                    job_data['error_log'] = []
                
                # Re-add to the sorted set job queue with its original priority
                # Assuming job_data contains 'priority' and 'id'
                priority = job_data.get('priority', 5)
                await redis_client.zadd(job_queue_name, {json.dumps(job_data): priority})
                requeued_count += 1
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode dead-letter message during reprocess: {msg.decode('utf-8')[:100]}... Error: {e}")
            except Exception as e:
                logger.error(f"Error re-queuing dead-letter message {msg.decode('utf-8')[:100]}... Error: {e}")
        
        # Clear the dead-letter queue after successful re-queuing
        await redis_client.delete(dead_letter_queue_name)
        
        logger.info(f"Reprocessed {requeued_count} messages from dead-letter queue to {job_queue_name}.")
        return {"status": "success", "message": f"Reprocessed {requeued_count} messages from dead-letter queue."}
    except Exception as e:
        logger.error(f"Error reprocessing dead-letter messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reprocess dead-letter messages: {e}")


# Add queue-related endpoints to the main app
add_queue_endpoints(app, db) # Pass the db instance to add_queue_endpoints
