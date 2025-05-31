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


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import logging
from urllib.parse import urlparse
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import redis.asyncio as redis
import json
import uuid
import asyncio

from playwright.async_api import async_playwright, Browser

from Link_Profiler.services.crawl_service import CrawlService
from Link_Profiler.services.domain_service import DomainService, SimulatedDomainAPIClient, RealDomainAPIClient, AbstractDomainAPIClient
from Link_Profiler.services.backlink_service import BacklinkService, SimulatedBacklinkAPIClient, RealBacklinkAPIClient, GSCBacklinkAPIClient, OpenLinkProfilerAPIClient
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService
from Link_Profiler.services.expired_domain_finder_service import ExpiredDomainFinderService
from Link_Profiler.services.serp_service import SERPService, SimulatedSERPAPIClient, RealSERPAPIClient
from Link_Profiler.services.keyword_service import KeywordService, SimulatedKeywordAPIClient, RealKeywordAPIClient
from Link_Profiler.services.link_health_service import LinkHealthService
from Link_Profiler.services.ai_service import AIService
from Link_Profiler.services.alert_service import AlertService
from Link_Profiler.services.auth_service import AuthService
from Link_Profiler.services.report_service import ReportService # New: Import ReportService
from Link_Profiler.database.database import Database
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
from Link_Profiler.crawlers.serp_crawler import SERPCrawler
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.core.models import CrawlConfig, CrawlJob, LinkProfile, Backlink, serialize_model, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion, LinkIntersectResult, CompetitiveKeywordAnalysisResult, AlertRule, AlertSeverity, AlertChannel, User, Token
from Link_Profiler.monitoring.prometheus_metrics import (
    API_REQUESTS_TOTAL, API_REQUEST_DURATION_SECONDS, get_metrics_text,
    JOBS_CREATED_TOTAL, JOBS_IN_PROGRESS, JOBS_PENDING, JOBS_COMPLETED_SUCCESS_TOTAL, JOBS_FAILED_TOTAL
)
from Link_Profiler.api.queue_endpoints import add_queue_endpoints, submit_crawl_to_queue, QueueCrawlRequest
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.utils.logging_config import setup_logging, get_default_logging_config
from Link_Profiler.utils.data_exporter import export_to_csv
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.proxy_manager import proxy_manager
from Link_Profiler.utils.connection_manager import ConnectionManager, connection_manager

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
    backlink_service_instance = BacklinkService(api_client=GSCBacklinkAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)
elif config_loader.get("backlink_api.openlinkprofiler_api.enabled"):
    backlink_service_instance = BacklinkService(api_client=OpenLinkProfilerAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)
elif config_loader.get("backlink_api.real_api.enabled"):
    backlink_service_instance = BacklinkService(api_client=RealBacklinkAPIClient(api_key=config_loader.get("backlink_api.real_api.api_key")), redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)
else:
    backlink_service_instance = BacklinkService(api_client=SimulatedBacklinkAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)

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

# New: Initialize Alert Service
alert_service_instance = AlertService(db, connection_manager) # Pass connection_manager here

# New: Initialize Auth Service
auth_service_instance = AuthService(db)

# New: Initialize Report Service
report_service_instance = ReportService(db)

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

# OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for managing the lifespan of the FastAPI application.
    Ensures resources like aiohttp sessions are properly opened and closed.
    """
    context_managers = [
        domain_service_instance,
        backlink_service_instance,
        serp_service_instance,
        keyword_service_instance,
        link_health_service_instance,
        technical_auditor_instance,
        ai_service_instance,
        alert_service_instance, # New: Add AlertService to lifespan
        auth_service_instance, # New: Add AuthService to lifespan
        report_service_instance # New: Add ReportService to lifespan
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
        
        # New: Start alert rule refreshing in background
        asyncio.create_task(alert_service_instance.refresh_rules())

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

# --- Dependency for current user authentication ---
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        user = await auth_service_instance.get_current_user(token)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
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

class LinkIntersectRequest(BaseModel):
    primary_domain: str = Field(..., description="The primary domain for analysis (e.g., 'example.com').")
    competitor_domains: List[str] = Field(..., description="A list of competitor domains to compare against (e.g., ['competitor1.com', 'competitor2.com']).")

class LinkIntersectResponse(BaseModel):
    primary_domain: str
    competitor_domains: List[str]
    common_linking_domains: List[str]

    @classmethod
    def from_link_intersect_result(cls, result: LinkIntersectResult):
        return cls(**serialize_model(result))

class CompetitiveKeywordAnalysisRequest(BaseModel):
    primary_domain: str = Field(..., description="The primary domain for which to perform keyword analysis.")
    competitor_domains: List[str] = Field(..., description="A list of competitor domains to compare against.")

class CompetitiveKeywordAnalysisResponse(BaseModel):
    primary_domain: str
    competitor_domains: List[str]
    common_keywords: List[str]
    keyword_gaps: Dict[str, List[str]]
    primary_unique_keywords: List[str]

    @classmethod
    def from_competitive_keyword_analysis_result(cls, result: CompetitiveKeywordAnalysisResult):
        return cls(**serialize_model(result))

# New: Pydantic models for AlertRule management
class AlertRuleCreateRequest(BaseModel):
    name: str = Field(..., description="A unique name for the alert rule.")
    description: Optional[str] = Field(None, description="A brief description of the alert rule.")
    is_active: bool = Field(True, description="Whether the alert rule is active.")
    
    trigger_type: str = Field(..., description="Type of event that triggers the alert (e.g., 'job_status_change', 'metric_threshold', 'anomaly_detected').")
    job_type_filter: Optional[str] = Field(None, description="Optional: Apply rule only to specific job types (e.g., 'backlink_discovery').")
    target_url_pattern: Optional[str] = Field(None, description="Optional: Regex pattern for target URLs to apply the rule to.")
    
    metric_name: Optional[str] = Field(None, description="Optional: Name of the metric to monitor (for 'metric_threshold' trigger_type, e.g., 'seo_score', 'broken_links_count').")
    threshold_value: Optional[Union[int, float]] = Field(None, description="Optional: Threshold value for the metric.")
    comparison_operator: Optional[str] = Field(None, description="Optional: Comparison operator for the metric threshold (e.g., '>', '<', '>=', '<=', '==').")
    
    anomaly_type_filter: Optional[str] = Field(None, description="Optional: Filter for specific anomaly types (for 'anomaly_detected' trigger_type, e.g., 'captcha_spike').")
    
    severity: AlertSeverity = Field(AlertSeverity.WARNING, description="Severity level of the alert.")
    notification_channels: List[AlertChannel] = Field([AlertChannel.DASHBOARD], description="List of channels to send notifications to.")
    notification_recipients: List[str] = Field([], description="List of recipients (e.g., email addresses, Slack channel IDs).")

class AlertRuleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    trigger_type: str
    job_type_filter: Optional[str]
    target_url_pattern: Optional[str]
    metric_name: Optional[str]
    threshold_value: Optional[Union[int, float]]
    comparison_operator: Optional[str]
    anomaly_type_filter: Optional[str]
    severity: AlertSeverity
    notification_channels: List[AlertChannel]
    notification_recipients: List[str]
    created_at: datetime
    last_triggered_at: Optional[datetime]

    @classmethod
    def from_alert_rule(cls, rule: AlertRule):
        rule_dict = serialize_model(rule)
        # Ensure enums are converted to their values for Pydantic
        rule_dict['severity'] = rule.severity.value
        rule_dict['notification_channels'] = [c.value for c in rule.notification_channels]
        
        if isinstance(rule_dict.get('created_at'), str):
            try:
                rule_dict['created_at'] = datetime.fromisoformat(rule_dict['created_at'])
            except ValueError:
                 logger.warning(f"Could not parse created_at string: {rule_dict.get('created_at')}")
                 rule_dict['created_at'] = None
        if isinstance(rule_dict.get('last_triggered_at'), str):
            try:
                rule_dict['last_triggered_at'] = datetime.fromisoformat(rule_dict['last_triggered_at'])
            except ValueError:
                 logger.warning(f"Could not parse last_triggered_at string: {rule_dict.get('last_triggered_at')}")
                 rule_dict['last_triggered_at'] = None
        return cls(**rule_dict)

# New: Pydantic models for User Authentication
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    password: str = Field(..., min_length=8)

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        orm_mode = True # Enable ORM mode for easy conversion from User dataclass

    @classmethod
    def from_user(cls, user: User):
        user_dict = serialize_model(user)
        if isinstance(user_dict.get('created_at'), str):
            try:
                user_dict['created_at'] = datetime.fromisoformat(user_dict['created_at'])
            except ValueError:
                 logger.warning(f"Could not parse created_at string: {user_dict.get('created_at')}")
                 user_dict['created_at'] = None
        return cls(**user_dict)


# --- API Endpoints ---

@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user_endpoint(user_data: UserCreate):
    """
    Registers a new user.
    """
    try:
        user = await auth_service_instance.register_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        return UserResponse.from_user(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error during user registration: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during registration.")

@app.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates a user and returns an access token.
    """
    user = await auth_service_instance.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth_service_instance.access_token_expire_minutes)
    access_token = auth_service_instance.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Retrieves the current authenticated user's information.
    """
    return UserResponse.from_user(current_user)


@app.post("/crawl/start_backlink_discovery", response_model=Dict[str, str], status_code=202)
async def start_backlink_discovery(
    request: StartCrawlRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a new backlink discovery job to the queue.
    """
    logger.info(f"Received request to submit backlink discovery for {request.target_url} to queue by user: {current_user.username}.")
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a new link health audit job to the queue.
    """
    logger.info(f"Received request to submit link health audit for {len(request.source_urls)} URLs to queue by user: {current_user.username}.")
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a new technical audit job to the queue.
    """
    logger.info(f"Received request to submit technical audit for {len(request.urls_to_audit)} URLs to queue by user: {current_user.username}.")
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a new full SEO audit job to the queue.
    This job orchestrates technical and link health audits.
    """
    logger.info(f"Received request to submit full SEO audit for {len(request.urls_to_audit)} URLs to queue by user: {current_user.username}.")
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a new batch domain analysis job to the queue.
    """
    logger.info(f"Received request to submit domain analysis for {len(request.domain_names)} domains to queue by user: {current_user.username}.")
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a new Web3 content crawl job to the queue.
    """
    logger.info(f"Received request to submit Web3 crawl for identifier: {request.web3_content_identifier} to queue by user: {current_user.username}.")
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a new social media content crawl job to the queue.
    """
    logger.info(f"Received request to submit social media crawl for query: {request.social_media_query} to queue by user: {current_user.username}.")
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
async def get_crawl_status(job_id: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves the current status of a specific crawl job.
    """
    job = db.get_crawl_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found.")
    return CrawlJobResponse.from_crawl_job(job)

@app.get("/crawl/all_jobs", response_model=List[CrawlJobResponse])
async def get_all_crawl_jobs(current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves a list of all crawl jobs in the system.
    """
    logger.info(f"Received request for all crawl jobs by user: {current_user.username}.")
    jobs = db.get_all_crawl_jobs() # New method call
    return [CrawlJobResponse.from_crawl_job(job) for job in jobs]

@app.post("/crawl/pause/{job_id}", response_model=CrawlJobResponse)
async def pause_crawl_job(job_id: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Pauses an in-progress crawl job.
    """
    logger.info(f"Received request to pause job {job_id} by user: {current_user.username}.")
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
async def resume_crawl_job(job_id: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Resumes a paused crawl job.
    """
    logger.info(f"Received request to resume job {job_id} by user: {current_user.username}.")
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
async def stop_crawl_job(job_id: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Stops an active or paused crawl job.
    """
    logger.info(f"Received request to stop job {job_id} by user: {current_user.username}.")
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
async def get_link_profile(target_url: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves the link profile for a given target URL.
    """
    logger.info(f"Received request for link profile of {target_url} by user: {current_user.username}.")
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    profile = db.get_link_profile(target_url)
    if not profile:
        raise HTTPException(status_code=404, detail="Link profile not found for this URL. A crawl might not have been completed yet.")
    return LinkProfileResponse.from_link_profile(profile)

@app.get("/backlinks/{target_url:path}", response_model=List[BacklinkResponse])
async def get_backlinks(target_url: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves all raw backlinks found for a given target URL.
    """
    logger.info(f"Received request for backlinks of {target_url} by user: {current_user.username}.")
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    backlinks = db.get_backlinks_for_target(target_url) 
    
    if not backlinks:
        raise HTTPException(status_code=404, detail=f"No backlinks found for target URL {target_url}.")
    
    return [BacklinkResponse.from_backlink(bl) for bl in backlinks]

@app.get("/debug/all_backlinks", response_model=List[BacklinkResponse])
async def debug_get_all_backlinks(current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    DEBUG endpoint: Retrieves ALL raw backlinks from the database.
    """
    logger.info(f"DEBUG endpoint: Received request for all backlinks by user: {current_user.username}.")
    if not current_user.is_admin: # Example: restrict debug endpoint to admins
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    backlinks = db.get_all_backlinks()
    logger.info(f"DEBUG endpoint: Retrieved {len(backlinks)} backlinks from DB.")
    return [BacklinkResponse.from_backlink(bl) for bl in backlinks]

@app.get("/export/backlinks.csv", response_class=Response)
async def export_all_backlinks_csv(current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Exports all backlinks from the database to a CSV file.
    """
    logger.info(f"Received request to export all backlinks to CSV by user: {current_user.username}.")
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
async def export_all_link_profiles_csv(current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Exports all link profiles from the database to a CSV file.
    """
    logger.info(f"Received request to export all link profiles to CSV by user: {current_user.username}.")
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
async def export_all_crawl_jobs_csv(current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Exports all crawl jobs from the database to a CSV file.
    """
    logger.info(f"Received request to export all crawl jobs to CSV by user: {current_user.username}.")
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
async def check_domain_availability(domain_name: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Checks if a domain name is available for registration.
    """
    logger.info(f"Received request for domain availability of {domain_name} by user: {current_user.username}.")
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    is_available = await domain_service_instance.check_domain_availability(domain_name)
    return {"domain_name": domain_name, "is_available": is_available}

@app.get("/domain/whois/{domain_name}", response_model=Dict)
async def get_domain_whois(domain_name: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves WHOIS information for a given domain name.
    """
    logger.info(f"Received request for WHOIS of {domain_name} by user: {current_user.username}.")
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    whois_info = await domain_service_instance.get_whois_info(domain_name)
    if not whois_info:
        raise HTTPException(status_code=404, detail="WHOIS information not found for this domain.")
    return whois_info

@app.get("/domain/info/{domain_name}", response_model=DomainResponse)
async def get_domain_info(domain_name: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves comprehensive domain information, including simulated WHOIS and availability.
    """
    logger.info(f"Received request for domain info of {domain_name} by user: {current_user.username}.")
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    domain_obj = await domain_service_instance.get_domain_info(domain_name)
    if not domain_obj:
        raise HTTPException(status_code=404, detail="Domain information not found.")
    return DomainResponse.from_domain(domain_obj)

@app.get("/domain/analyze/{domain_name}", response_model=DomainAnalysisResponse)
async def analyze_domain(domain_name: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Analyzes a domain for its potential value, especially for expired domains.
    """
    logger.info(f"Received request for domain analysis of {domain_name} by user: {current_user.username}.")
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    analysis_result = await domain_analyzer_service.analyze_domain_for_expiration_value(domain_name)
    
    if not analysis_result:
        raise HTTPException(status_code=404, detail="Failed to perform domain analysis, domain info not found or error occurred.")
    
    return analysis_result

@app.post("/domain/find_expired_domains", response_model=FindExpiredDomainsResponse)
async def find_expired_domains(request: FindExpiredDomainsRequest, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Searches for valuable expired domains among a list of potential candidates.
    """
    logger.info(f"Received request to find expired domains by user: {current_user.username}.")
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
async def search_serp(request: SERPSearchRequest, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Submits a SERP search job to the queue.
    """
    logger.info(f"Received request to submit SERP search for keyword: {request.keyword} to queue by user: {current_user.username}.")
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
async def get_serp_results(keyword: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves stored SERP results for a specific keyword.
    """
    logger.info(f"Received request to get stored SERP results for keyword: {keyword} by user: {current_user.username}.")
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
async def suggest_keywords(request: KeywordSuggestRequest, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Submits a keyword suggestion job to the queue.
    """
    logger.info(f"Received request to submit keyword suggestions for seed: {request.seed_keyword} to queue by user: {current_user.username}.")
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
async def get_keyword_suggestions(seed_keyword: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves stored keyword suggestions for a specific seed keyword.
    """
    logger.info(f"Received request to get stored keyword suggestions for seed: {seed_keyword} by user: {current_user.username}.")
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

@app.post("/competitor/link_intersect", response_model=LinkIntersectResponse)
async def get_link_intersect_analysis(request: LinkIntersectRequest, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Performs a link intersect analysis to find common linking domains.
    Identifies source domains that link to the primary domain AND at least one of the competitor domains.
    """
    logger.info(f"Received request for link intersect analysis by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=400, detail="Primary domain and at least one competitor domain are required.")
    
    result = await backlink_service_instance.perform_link_intersect_analysis(
        primary_domain=request.primary_domain,
        competitor_domains=request.competitor_domains
    )
    
    return LinkIntersectResponse.from_link_intersect_result(result)

@app.post("/competitor/keyword_analysis", response_model=CompetitiveKeywordAnalysisResponse)
async def get_competitive_keyword_analysis(request: CompetitiveKeywordAnalysisRequest, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Performs a competitive keyword analysis to identify common keywords and keyword gaps.
    Compares keywords that the primary domain and competitor domains rank for.
    """
    logger.info(f"Received request for competitive keyword analysis by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=400, detail="Primary domain and at least one competitor domain are required.")
    
    result = await keyword_service_instance.perform_competitive_keyword_analysis(
        primary_domain=request.primary_domain,
        competitor_domains=request.competitor_domains
    )
    
    return CompetitiveKeywordAnalysisResponse.from_competitive_keyword_analysis_result(result)

# New: Alert Rule Endpoints
@app.post("/alerts/rules", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(request: AlertRuleCreateRequest, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Creates a new alert rule.
    """
    logger.info(f"Received request to create alert rule by user: {current_user.username}.")
    rule_id = str(uuid.uuid4())
    new_rule = AlertRule(id=rule_id, **request.dict())
    try:
        db.save_alert_rule(new_rule)
        # After saving, trigger a refresh of rules in the AlertService
        if alert_service_instance:
            await alert_service_instance.load_active_rules()
        logger.info(f"Created new alert rule: {new_rule.name} (ID: {new_rule.id})")
        return AlertRuleResponse.from_alert_rule(new_rule)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) # Conflict if name already exists
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create alert rule: {e}")

@app.get("/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(rule_id: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves a specific alert rule by its ID.
    """
    logger.info(f"Received request to get alert rule {rule_id} by user: {current_user.username}.")
    rule = db.get_alert_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found.")
    return AlertRuleResponse.from_alert_rule(rule)

@app.get("/alerts/rules", response_model=List[AlertRuleResponse])
async def list_alert_rules(active_only: bool = False, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Lists all alert rules, optionally filtering for active ones.
    """
    logger.info(f"Received request to list alert rules by user: {current_user.username}.")
    rules = db.get_all_alert_rules(active_only=active_only)
    return [AlertRuleResponse.from_alert_rule(rule) for rule in rules]

@app.put("/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(rule_id: str, request: AlertRuleCreateRequest, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Updates an existing alert rule.
    """
    logger.info(f"Received request to update alert rule {rule_id} by user: {current_user.username}.")
    existing_rule = db.get_alert_rule(rule_id)
    if not existing_rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found.")
    
    updated_rule = AlertRule(id=rule_id, **request.dict())
    try:
        db.save_alert_rule(updated_rule) # save_alert_rule handles update if ID exists
        # After saving, trigger a refresh of rules in the AlertService
        if alert_service_instance:
            await alert_service_instance.load_active_rules()
        logger.info(f"Updated alert rule: {updated_rule.name} (ID: {updated_rule.id})")
        return AlertRuleResponse.from_alert_rule(updated_rule)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating alert rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update alert rule: {e}")

@app.delete("/alerts/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(rule_id: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Deletes an alert rule by its ID.
    """
    logger.info(f"Received request to delete alert rule {rule_id} by user: {current_user.username}.")
    try:
        deleted = db.delete_alert_rule(rule_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found.")
        # After deleting, trigger a refresh of rules in the AlertService
        if alert_service_instance:
            await alert_service_instance.load_active_rules()
        logger.info(f"Deleted alert rule ID: {rule_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logger.error(f"Error deleting alert rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete alert rule: {e}")

# New: Report Generation Endpoint
@app.get("/reports/link_profile/{target_url:path}/pdf", response_class=Response)
async def get_link_profile_pdf_report(target_url: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Generates and returns a PDF report for a specific link profile.
    """
    logger.info(f"Received request for PDF report of link profile {target_url} by user: {current_user.username}.")
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    pdf_buffer = await report_service_instance.generate_link_profile_pdf_report(target_url)
    
    if pdf_buffer is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate PDF report.")
    
    # If ReportLab was not available, it returns a BytesIO with text content
    # We need to check if it's a real PDF or simulated text
    content_type = "application/pdf"
    if not report_service_instance.REPORTLAB_AVAILABLE: # Access the class variable
        content_type = "text/plain" # Indicate it's plain text if ReportLab is missing
        logger.warning("Returning simulated PDF as plain text due to missing ReportLab.")

    headers = {
        "Content-Disposition": f"attachment; filename=link_profile_report_{urlparse(target_url).netloc}.pdf",
        "Content-Type": content_type
    }
    return Response(content=pdf_buffer.getvalue(), headers=headers, media_type=content_type)


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
async def get_dead_letters(current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    DEBUG endpoint: Retrieves messages from the Redis dead-letter queue.
    """
    logger.info(f"DEBUG endpoint: Received request for dead letters by user: {current_user.username}.")
    if not current_user.is_admin: # Example: restrict debug endpoint to admins
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available, dead-letter queue cannot be accessed.")
    
    dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name")
    try:
        # Fetch all items from the dead-letter queue without removing them
        messages = await redis_client.lrange(dead_letter_queue_name, 0, -1)
        decoded_messages = [json.loads(msg.decode('utf-8')) for msg in messages]
        logger.info(f"Retrieved {len(decoded_messages)} messages from dead-letter queue.")
        return {"dead_letter_messages": decoded_messages}
    except Exception as e:
        logger.error(f"Error retrieving dead-letter messages: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve dead-letter messages: {e}")

@app.post("/debug/clear_dead_letters")
async def clear_dead_letters(current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    DEBUG endpoint: Clears all messages from the Redis dead-letter queue.
    """
    logger.info(f"DEBUG endpoint: Received request to clear dead letters by user: {current_user.username}.")
    if not current_user.is_admin: # Example: restrict debug endpoint to admins
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available, dead-letter queue cannot be cleared.")
    
    dead_letter_queue_name = config_loader.get("queue.dead_letter_queue_name")
    try:
        count = await redis_client.delete(dead_letter_queue_name)
        logger.info(f"Cleared {count} messages from dead-letter queue.")
        return {"status": "success", "message": f"Cleared {count} messages from dead-letter queue."}
    except Exception as e:
        logger.error(f"Error clearing dead-letter messages: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to clear dead-letter messages: {e}")

@app.post("/debug/reprocess_dead_letters", response_model=Dict[str, str])
async def reprocess_dead_letters(current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    DEBUG endpoint: Moves all messages from the dead-letter queue back to the main job queue for reprocessing.
    """
    logger.info(f"DEBUG endpoint: Received request to reprocess dead letters by user: {current_user.username}.")
    if not current_user.is_admin: # Example: restrict debug endpoint to admins
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available, dead-letter queue cannot be reprocessed.")
    
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to reprocess dead-letter messages: {e}")


# Add queue-related endpoints to the main app
add_queue_endpoints(app, db, alert_service_instance, connection_manager)
