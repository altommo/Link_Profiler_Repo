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


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, WebSocket, WebSocketDisconnect, Depends, status, Query # Corrected: Import Query
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
import psutil # New: Import psutil for system stats

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
from Link_Profiler.services.report_service import ReportService
from Link_Profiler.services.competitive_analysis_service import CompetitiveAnalysisService # New: Import CompetitiveAnalysisService
from Link_Profiler.services.social_media_service import SocialMediaService # New: Import SocialMediaService
from Link_Profiler.services.web3_service import Web3Service # New: Import Web3Service
from Link_Profiler.services.link_building_service import LinkBuildingService # New: Import LinkBuildingService
from Link_Profiler.services.auth_service import AuthService # New: Import AuthService
from Link_Profiler.database.database import Database
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
from Link_Profiler.crawlers.serp_crawler import SERPCrawler
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.crawlers.social_media_crawler import SocialMediaCrawler # New: Import SocialMediaCrawler
from Link_Profiler.core.models import CrawlConfig, CrawlJob, LinkProfile, Backlink, serialize_model, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion, LinkIntersectResult, CompetitiveKeywordAnalysisResult, AlertRule, AlertSeverity, AlertChannel, User, Token, ContentGapAnalysisResult, DomainHistory, LinkProspect, OutreachCampaign, OutreachEvent, ReportJob
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

# New: Import API Clients
from Link_Profiler.clients.google_search_console_client import GSCClient
from Link_Profiler.clients.google_pagespeed_client import PageSpeedClient # New: Import PageSpeedClient
from Link_Profiler.clients.google_trends_client import GoogleTrendsClient # New: Import GoogleTrendsClient
from Link_Profiler.clients.whois_client import WHOISClient # New: Import WHOISClient
from Link_Profiler.clients.dns_client import DNSClient # New: Import DNSClient
from Link_Profiler.clients.reddit_client import RedditClient # New: Import RedditClient
from Link_Profiler.clients.youtube_client import YouTubeClient # New: Import YouTubeClient
from Link_Profiler.clients.news_api_client import NewsAPIClient # New: Import NewsAPIClient
# from Link_Profiler.clients.wayback_machine_client import WaybackClient
# from Link_Profiler.clients.common_crawl_client import CommonCrawlClient
# from Link_Profiler.clients.nominatim_client import NominatimClient
# from Link_Profiler.clients.security_trails_client import SecurityTrailsClient
# from Link_Profiler.clients.ssl_labs_client import SSLLabsClient


# Initialize and load config once using the absolute path
config_loader = ConfigLoader()
config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

# Setup logging using the loaded configuration
logging_config = config_loader.get("logging.config", get_default_logging_config(config_loader.get("logging.level", "INFO")))
setup_logging(logging_config)

logger = logging.getLogger(__name__) # Get logger after configuration

# --- Startup Configuration Diagnostics ---
def validate_critical_config():
    """Validate that critical configuration values are properly loaded."""
    critical_vars = {
        "LP_AUTH_SECRET_KEY": "auth.secret_key",
        "LP_DATABASE_URL": "database.url", 
        "LP_REDIS_URL": "redis.url"
    }
    
    for env_var, config_path in critical_vars.items():
        env_value = os.getenv(env_var)
        config_value = config_loader.get(config_path)
        
        # Check if env_value is set and it does not match the config_value
        # Also check if config_value is still the placeholder for secret key
        if env_value and (env_value != config_value or (config_path == "auth.secret_key" and config_value == "PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY")):
            logger.error(f"CRITICAL: Environment variable {env_var} not properly loaded or config still uses placeholder!")
            logger.error(f"  Environment: {env_var}={env_value[:20]}...")
            logger.error(f"  Config:      {config_path}={config_value[:20] if config_value else 'None'}...")
        elif not env_value and (config_path == "auth.secret_key" and config_value == "PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY"):
             logger.warning(f"WARNING: {env_var} is not set and config still uses placeholder. Authentication will fail.")
        elif not env_value and (config_path == "database.url" or config_path == "redis.url"):
             logger.warning(f"WARNING: {env_var} is not set. Using default/fallback for {config_path}.")

# Call validation after config loading
validate_critical_config()
# --- End Startup Configuration Diagnostics ---


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


# New: Initialize WHOISClient and DNSClient
whois_client_instance = WHOISClient()
dns_client_instance = DNSClient()

# Initialize DomainService globally, but manage its lifecycle with lifespan
# Determine which DomainAPIClient to use based on priority: AbstractAPI > Real (paid) > WHOIS-JSON > Simulated
# The DomainService constructor now handles the internal assignment of api_client
# based on the config, so we just pass the necessary dependencies.
domain_service_instance = DomainService(
    redis_client=redis_client, 
    cache_ttl=API_CACHE_TTL, 
    database=db, 
    whois_client=whois_client_instance, 
    dns_client=dns_client_instance
)

# New: Initialize GSCClient
gsc_client_instance = GSCClient()

# Initialize BacklinkService based on priority: GSC > OpenLinkProfiler > Real (paid) > Simulated
# Removed 'gsc_client' argument as BacklinkService internally handles GSCBacklinkAPIClient instantiation.
if config_loader.get("backlink_api.gsc_api.enabled"):
    backlink_service_instance = BacklinkService(redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)
elif config_loader.get("backlink_api.openlinkprofiler_api.enabled"):
    openlinkprofiler_base_url = config_loader.get("backlink_api.openlinkprofiler_api.base_url")
    if not openlinkprofiler_base_url:
        logger.warning("OpenLinkProfiler API enabled but base_url not found in config. Falling back to simulated Backlink API.")
        backlink_service_instance = BacklinkService(redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)
    else:
        backlink_service_instance = BacklinkService(api_client=OpenLinkProfilerAPIClient(base_url=openlinkprofiler_base_url), redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)
elif config_loader.get("backlink_api.real_api.enabled"):
    real_api_key = config_loader.get("backlink_api.real_api.api_key")
    real_api_base_url = config_loader.get("backlink_api.real_api.base_url")
    if not real_api_key or not real_api_base_url:
        logger.warning("Real Backlink API enabled but API key or base_url not found in config. Falling back to simulated Backlink API.")
        backlink_service_instance = BacklinkService(redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)
    else:
        backlink_service_instance = BacklinkService(api_client=RealBacklinkAPIClient(api_key=real_api_key, base_url=real_api_base_url), redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)
else:
    backlink_service_instance = BacklinkService(api_client=SimulatedBacklinkAPIClient(), redis_client=redis_client, cache_ttl=API_CACHE_TTL, database=db)

# New: Initialize PageSpeedClient
pagespeed_client_instance = PageSpeedClient()

# New: Initialize SERPService and SERPCrawler
serp_crawler_instance = None
if config_loader.get("serp_crawler.playwright.enabled"):
    logger.info("Initialising Playwright SERPCrawler.")
    serp_crawler_instance = SERPCrawler(
        headless=config_loader.get("serp_crawler.playwright.headless"),
        browser_type=config_loader.get("serp_crawler.playwright.browser_type")
    )
serp_service_instance = SERPService(
    api_client=RealSERPAPIClient(api_key=config_loader.get("serp_api.real_api.api_key"), base_url=config_loader.get("serp_api.real_api.base_url")) if config_loader.get("serp_api.real_api.enabled") else SimulatedSERPAPIClient(),
    serp_crawler=serp_crawler_instance,
    pagespeed_client=pagespeed_client_instance, # New: Pass pagespeed_client_instance
    redis_client=redis_client, # Pass redis_client for caching
    cache_ttl=API_CACHE_TTL # Pass cache_ttl
)

# New: Initialize GoogleTrendsClient
google_trends_client_instance = GoogleTrendsClient()

# New: Initialize KeywordService and KeywordScraper
keyword_scraper_instance = None
if config_loader.get("keyword_scraper.enabled"):
    logger.info("Initialising KeywordScraper.")
    keyword_scraper_instance = KeywordScraper()
keyword_service_instance = KeywordService(
    api_client=RealKeywordAPIClient(api_key=config_loader.get("keyword_api.real_api.api_key"), base_url=config_loader.get("keyword_api.real_api.base_url")) if config_loader.get("keyword_api.real_api.enabled") else SimulatedKeywordAPIClient(),
    keyword_scraper=keyword_scraper_instance,
    google_trends_client=google_trends_client_instance, # New: Pass google_trends_client_instance
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

# New: Initialize Competitive Analysis Service
competitive_analysis_service_instance = CompetitiveAnalysisService(db, backlink_service_instance, serp_service_instance)

# New: Initialize RedditClient, YouTubeClient, NewsAPIClient
reddit_client_instance = RedditClient()
youtube_client_instance = YouTubeClient()
news_api_client_instance = NewsAPIClient()

# New: Initialize Social Media Service and Crawler
social_media_crawler_instance = None
if config_loader.get("social_media_crawler.enabled"):
    logger.info("Initialising SocialMediaCrawler.")
    social_media_crawler_instance = SocialMediaCrawler()
social_media_service_instance = SocialMediaService(
    social_media_crawler=social_media_crawler_instance,
    redis_client=redis_client,
    cache_ttl=API_CACHE_TTL,
    reddit_client=reddit_client_instance, # New: Pass RedditClient
    youtube_client=youtube_client_instance, # New: Pass YouTubeClient
    news_api_client=news_api_client_instance # New: Pass NewsAPIClient
)

# New: Initialize Web3 Service
web3_service_instance = Web3Service(
    redis_client=redis_client,
    cache_ttl=API_CACHE_TTL
)

# New: Initialize Link Building Service
link_building_service_instance = LinkBuildingService(
    database=db,
    domain_service=domain_service_instance,
    backlink_service=backlink_service_instance,
    serp_service=serp_service_instance,
    keyword_service=keyword_service_instance,
    ai_service=ai_service_instance
)

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
    social_media_service=social_media_service_instance, # New: Pass SocialMediaService
    web3_service=web3_service_instance, # New: Pass Web3Service
    link_building_service=link_building_service_instance, # New: Pass LinkBuildingService
    report_service=report_service_instance, # New: Pass ReportService
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
        report_service_instance, # New: Add ReportService to lifespan
        competitive_analysis_service_instance, # New: Add CompetitiveAnalysisService to lifespan
        social_media_service_instance, # New: Add SocialMediaService
        web3_service_instance, # New: Add Web3Service
        link_building_service_instance, # New: Add LinkBuildingService
        gsc_client_instance, # New: Add GSCClient to lifespan
        pagespeed_client_instance, # New: Add PageSpeedClient to lifespan
        google_trends_client_instance, # New: Add GoogleTrendsClient to lifespan
        whois_client_instance, # New: Add WHOISClient to lifespan
        dns_client_instance, # New: Add DNSClient to lifespan
        reddit_client_instance, # New: Add RedditClient
        youtube_client_instance, # New: Add YouTubeClient
        news_api_client_instance # New: Add NewsAPIClient
    ]

    # Conditionally add ClickHouseLoader to context managers
    if clickhouse_loader_instance:
        context_managers.append(clickhouse_loader_instance)
    # Add Playwright and KeywordScraper contexts if they are enabled
    if serp_crawler_instance:
        context_managers.append(serp_crawler_instance)
    if keyword_scraper_instance:
        context_managers.append(keyword_scraper_instance)
    if social_media_crawler_instance: # New: Add SocialMediaCrawler
        context_managers.append(social_media_crawler_instance)

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
    except HTTPException: # Re-raise HTTPException from auth_service
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication.",
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

class ContentGapAnalysisRequest(BaseModel): # New Pydantic model for Content Gap Analysis job submission
    target_url: str = Field(..., description="The target URL for which to find content gaps.")
    competitor_urls: List[str] = Field(..., description="A list of competitor URLs to compare against.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration for fetching content.")

class TopicClusteringRequest(BaseModel): # New Pydantic model for Topic Clustering
    texts: List[str] = Field(..., description="A list of text documents to cluster.")
    num_clusters: int = Field(5, description="The desired number of topic clusters.")

class LinkVelocityRequest(BaseModel): # New Pydantic model for Link Velocity Request
    time_unit: str = Field("month", description="The unit of time ('day', 'week', 'month', 'quarter', 'year').")
    num_units: int = Field(6, description="The number of past units to retrieve data for.")

class DomainHistoryResponse(BaseModel): # New Pydantic model for DomainHistory
    domain_name: str
    snapshot_date: datetime
    authority_score: float
    trust_score: float
    spam_score: float
    total_backlinks: int
    referring_domains: int

    @classmethod
    def from_domain_history(cls, history: DomainHistory):
        history_dict = serialize_model(history)
        if isinstance(history_dict.get('snapshot_date'), str):
            try:
                history_dict['snapshot_date'] = datetime.fromisoformat(history_dict['snapshot_date'])
            except ValueError:
                logger.warning(f"Could not parse snapshot_date string: {history_dict.get('snapshot_date')}")
                history_dict['snapshot_date'] = None
        return cls(**history_dict)


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
                 logger.warning(f"Could_not parse started_date string: {job_dict.get('started_date')}")
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
        # Pydantic V2: 'orm_mode' has been renamed to 'from_attributes'
        from_attributes = True 

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

class ContentGapAnalysisResultResponse(BaseModel): # New Pydantic model for ContentGapAnalysisResult
    target_url: str
    competitor_urls: List[str]
    missing_topics: List[str]
    missing_keywords: List[str]
    content_format_gaps: List[str]
    actionable_insights: List[str]
    analysis_date: datetime

    @classmethod
    def from_content_gap_analysis_result(cls, result: ContentGapAnalysisResult):
        result_dict = serialize_model(result)
        if isinstance(result_dict.get('analysis_date'), str):
            try:
                result_dict['analysis_date'] = datetime.fromisoformat(result_dict['analysis_date'])
            except ValueError:
                logger.warning(f"Could not parse analysis_date string: {result_dict.get('analysis_date')}")
                result_dict['analysis_date'] = None
        return cls(**result_dict)

# New: Pydantic models for Link Building
class LinkProspectResponse(BaseModel):
    url: str
    domain: str
    score: float
    reasons: List[str]
    contact_info: Dict[str, str]
    last_outreach_date: Optional[datetime]
    status: str
    discovered_date: datetime

    @classmethod
    def from_link_prospect(cls, prospect: LinkProspect):
        prospect_dict = serialize_model(prospect)
        if isinstance(prospect_dict.get('last_outreach_date'), str):
            try:
                prospect_dict['last_outreach_date'] = datetime.fromisoformat(prospect_dict['last_outreach_date'])
            except ValueError:
                logger.warning(f"Could not parse last_outreach_date string: {prospect_dict.get('last_outreach_date')}")
                prospect_dict['last_outreach_date'] = None
        if isinstance(prospect_dict.get('discovered_date'), str):
            try:
                prospect_dict['discovered_date'] = datetime.fromisoformat(prospect_dict['discovered_date'])
            except ValueError:
                logger.warning(f"Could not parse discovered_date string: {prospect_dict.get('discovered_date')}")
                prospect_dict['discovered_date'] = None
        return cls(**prospect_dict)

class LinkProspectUpdateRequest(BaseModel):
    status: Optional[str] = None
    last_outreach_date: Optional[datetime] = None
    contact_info: Optional[Dict[str, str]] = None
    reasons: Optional[List[str]] = None
    score: Optional[float] = None

class ProspectIdentificationRequest(BaseModel):
    target_domain: str = Field(..., description="The primary domain for which to find link building prospects.")
    competitor_domains: List[str] = Field(..., description="A list of competitor domains to analyze for backlinks.")
    keywords: List[str] = Field(..., description="A list of keywords to search SERPs for relevant pages.")
    min_domain_authority: float = Field(20.0, description="Minimum domain authority for a prospect to be considered.")
    max_spam_score: float = Field(0.3, description="Maximum spam score for a prospect to be considered.")
    num_serp_results_to_check: int = Field(50, description="Number of SERP results to check for each keyword.")
    num_competitor_backlinks_to_check: int = Field(100, description="Number of competitor backlinks to check for intersect analysis.")

class OutreachCampaignCreateRequest(BaseModel):
    name: str = Field(..., description="Name of the outreach campaign.")
    target_domain: str = Field(..., description="The target domain for this campaign.")
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class OutreachCampaignResponse(BaseModel):
    id: str
    name: str
    target_domain: str
    status: str
    created_date: datetime
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_outreach_campaign(cls, campaign: OutreachCampaign):
        campaign_dict = serialize_model(campaign)
        if isinstance(campaign_dict.get('created_date'), str):
            campaign_dict['created_date'] = datetime.fromisoformat(campaign_dict['created_date'])
        if isinstance(campaign_dict.get('start_date'), str):
            campaign_dict['start_date'] = datetime.fromisoformat(campaign_dict['start_date'])
        if isinstance(campaign_dict.get('end_date'), str):
            campaign_dict['end_date'] = datetime.fromisoformat(campaign_dict['end_date'])
        return cls(**campaign_dict)

class OutreachEventCreateRequest(BaseModel):
    campaign_id: str
    prospect_url: str
    event_type: str = Field(..., description="Type of event (e.g., 'email_sent', 'reply_received', 'link_acquired').")
    notes: Optional[str] = None
    success: Optional[bool] = None

class OutreachEventResponse(BaseModel):
    id: str
    campaign_id: str
    prospect_url: str
    event_type: str
    event_date: datetime
    notes: Optional[str]
    success: Optional[bool]

    @classmethod
    def from_outreach_event(cls, event: OutreachEvent):
        event_dict = serialize_model(event)
        if isinstance(event_dict.get('event_date'), str):
            event_dict['event_date'] = datetime.fromisoformat(event_dict['event_date'])
        return cls(**event_dict)

# New: Pydantic models for AI features
class ContentGenerationRequest(BaseModel):
    topic: str = Field(..., description="The topic for which to generate content ideas.")
    num_ideas: int = Field(5, description="Number of content ideas to generate.")

class CompetitorStrategyAnalysisRequest(BaseModel):
    primary_domain: str = Field(..., description="The primary domain for analysis.")
    competitor_domains: List[str] = Field(..., description="List of competitor domains.")

class ReportScheduleRequest(BaseModel):
    report_type: str = Field(..., description="Type of report (e.g., 'link_profile_pdf', 'all_backlinks_excel').")
    target_identifier: str = Field(..., description="Identifier for the report target (e.g., URL, 'all').")
    format: str = Field(..., description="Format of the report (e.g., 'pdf', 'excel').")
    scheduled_at: Optional[datetime] = Field(None, description="Specific UTC datetime to run the report (ISO format).")
    cron_schedule: Optional[str] = Field(None, description="Cron string for recurring reports (e.g., '0 0 * * *').")
    config: Optional[Dict] = Field(None, description="Optional configuration for report generation.")

class ReportJobResponse(BaseModel):
    id: str
    report_type: str
    target_identifier: str
    format: str
    status: CrawlStatus
    created_date: datetime
    completed_date: Optional[datetime]
    file_path: Optional[str]
    error_message: Optional[str]

    @classmethod
    def from_report_job(cls, job: ReportJob):
        job_dict = serialize_model(job)
        job_dict['status'] = job.status.value
        if isinstance(job_dict.get('created_date'), str):
            job_dict['created_date'] = datetime.fromisoformat(job_dict['created_date'])
        if isinstance(job_dict.get('completed_date'), str):
            job_dict['completed_date'] = datetime.fromisoformat(job_dict['completed_date'])
        return cls(**job_dict)


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
    except HTTPException: # Re-raise HTTPException from auth_service
        raise
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
    logger.info(f"Received request to submit backlink discovery for {request.target_url} by user: {current_user.username}.")
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
    logger.info(f"Received request to submit link health audit for {len(request.source_urls)} URLs by user: {current_user.username}.")
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
    logger.info(f"Received request to submit technical audit for {len(request.urls_to_audit)} URLs by user: {current_user.username}.")
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
    logger.info(f"Received request to submit full SEO audit for {len(request.urls_to_audit)} URLs by user: {current_user.username}.")
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
    logger.info(f"Received request to submit domain analysis for {len(request.domain_names)} domains by user: {current_user.username}.")
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
    logger.info(f"Received request to submit Web3 crawl for identifier: {request.web3_content_identifier} by user: {current_user.username}.")
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
    logger.info(f"Received request to submit social media crawl for query: {request.social_media_query} by user: {current_user.username}.")
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

@app.post("/content/gap_analysis", response_model=Dict[str, str], status_code=202) # New endpoint
async def start_content_gap_analysis(
    request: ContentGapAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a new content gap analysis job to the queue.
    """
    logger.info(f"Received request to submit content gap analysis for {request.target_url} by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='content_gap_analysis').inc()

    if not request.target_url or not request.competitor_urls:
        raise HTTPException(status_code=400, detail="Target URL and at least one competitor URL must be provided for content gap analysis.")
    
    queue_request = QueueCrawlRequest(
        target_url=request.target_url,
        initial_seed_urls=[], # Not directly used for this job type's initial crawl
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["target_url_for_content_gap"] = request.target_url
    queue_request.config["competitor_urls_for_content_gap"] = request.competitor_urls
    queue_request.config["job_type"] = "content_gap_analysis" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.get("/content/gap_analysis/{target_url:path}", response_model=ContentGapAnalysisResultResponse) # New endpoint
async def get_content_gap_analysis_result(target_url: str, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Retrieves the content gap analysis result for a given target URL.
    """
    logger.info(f"Received request for content gap analysis result for {target_url} by user: {current_user.username}.")
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    result = db.get_content_gap_analysis_result(target_url)
    if not result:
        raise HTTPException(status_code=404, detail="Content gap analysis result not found for this URL. A job might not have been completed yet.")
    return ContentGapAnalysisResultResponse.from_content_gap_analysis_result(result)

@app.post("/content/topic_clustering", response_model=Dict[str, List[str]]) # New endpoint
async def perform_topic_clustering_endpoint(request: TopicClusteringRequest, current_user: User = Depends(get_current_user)): # Protected endpoint
    """
    Performs topic clustering on a list of provided texts using AI.
    """
    logger.info(f"Received request for topic clustering by user: {current_user.username}.")
    if not request.texts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one text document must be provided for topic clustering.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        clustered_topics = await ai_service_instance.perform_topic_clustering(
            texts=request.texts,
            num_clusters=request.num_clusters
        )
        return clustered_topics
    except Exception as e:
        logger.error(f"Error performing topic clustering: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform topic clustering: {e}")

@app.get("/link_profile/{target_domain}/link_velocity", response_model=Dict[str, int]) # Protected endpoint
async def get_link_velocity(target_domain: str, request_params: LinkVelocityRequest = Depends(), current_user: User = Depends(get_current_user)):
    """
    Retrieves the link velocity (new backlinks over time) for a given target domain.
    """
    logger.info(f"Received request for link velocity of {target_domain} by user: {current_user.username}.")
    if not target_domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target domain must be provided.")
    
    try:
        link_velocity_data = db.get_backlink_counts_over_time( # Corrected to use db directly
            target_domain=target_domain,
            time_unit=request_params.time_unit,
            num_units=request_params.num_units
        )
        if not link_velocity_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No link velocity data found for {target_domain} or parameters are invalid.")
        return link_velocity_data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving link velocity for {target_domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve link velocity: {e}")

@app.get("/domain/{domain_name}/history", response_model=List[DomainHistoryResponse]) # Protected endpoint
async def get_domain_history_endpoint(
    domain_name: str, 
    num_snapshots: int = Query(12, gt=0, description="Number of historical snapshots to retrieve."), # Fixed: Use Query
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Retrieves the historical progression of a domain's authority metrics.
    """
    logger.info(f"Received request for domain history of {domain_name} by user: {current_user.username}.")
    if not domain_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain name must be provided.")
    
    try:
        history_data = domain_service_instance.get_domain_authority_progression( # Corrected to use domain_service_instance
            domain_name=domain_name,
            num_snapshots=num_snapshots
        )
        if not history_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No historical data found for {domain_name}.")
        return [DomainHistoryResponse.from_domain_history(h) for h in history_data]
    except Exception as e:
        logger.error(f"Error retrieving domain history for {domain_name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve domain history: {e}")

@app.get("/serp/history", response_model=List[SERPResultResponse]) # New endpoint
async def get_serp_position_history_endpoint(
    target_url: str = Query(..., description="The URL for which to track SERP history."),
    keyword: str = Query(..., description="The keyword for which to track SERP history."),
    num_snapshots: int = Query(12, gt=0, description="The maximum number of recent historical snapshots to retrieve."),
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Retrieves the historical SERP positions for a specific URL and keyword.
    """
    logger.info(f"Received request for SERP history for URL '{target_url}' and keyword '{keyword}' by user: {current_user.username}.")
    if not target_url or not keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL and keyword must be provided.")
    
    try:
        history_data = db.get_serp_position_history(target_url, keyword, num_snapshots)
        if not history_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No SERP history found for URL '{target_url}' and keyword '{keyword}'.")
        return [SERPResultResponse.from_serp_result(sr) for sr in history_data]
    except Exception as e:
        logger.error(f"Error retrieving SERP position history for '{target_url}' and '{keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve SERP position history: {e}")

@app.post("/keyword/semantic_suggestions", response_model=List[str]) # New endpoint
async def get_semantic_keyword_suggestions_endpoint(
    primary_keyword: str = Query(..., description="The primary keyword to get semantic suggestions for."), # Changed to Query
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Generates a list of semantically related keywords using AI.
    """
    logger.info(f"Received request for semantic keyword suggestions for '{primary_keyword}' by user: {current_user.username}.")
    if not primary_keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary keyword must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        suggestions = await ai_service_instance.suggest_semantic_keywords(primary_keyword)
        if not suggestions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No semantic keyword suggestions found for '{primary_keyword}'.")
        return suggestions
    except Exception as e:
        logger.error(f"Error generating semantic keyword suggestions for '{primary_keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate semantic keyword suggestions: {e}")

@app.post("/competitor/link_intersect", response_model=LinkIntersectResponse) # New endpoint
async def get_link_intersect(request: LinkIntersectRequest, current_user: User = Depends(get_current_user)):
    """
    Performs a link intersect analysis to find common linking domains between a primary domain and competitors.
    """
    logger.info(f"Received request for link intersect analysis for {request.primary_domain} by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary domain and at least one competitor domain must be provided.")
    
    try:
        result = await competitive_analysis_service_instance.perform_link_intersect_analysis(
            primary_domain=request.primary_domain,
            competitor_domains=request.competitor_domains
        )
        return LinkIntersectResponse.from_link_intersect_result(result)
    except Exception as e:
        logger.error(f"Error performing link intersect analysis: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform link intersect analysis: {e}")

@app.post("/competitor/keyword_analysis", response_model=CompetitiveKeywordAnalysisResponse) # New endpoint
async def get_competitive_keyword_analysis(request: CompetitiveKeywordAnalysisRequest, current_user: User = Depends(get_current_user)):
    """
    Performs a competitive keyword analysis, identifying common keywords, keyword gaps, and unique keywords.
    """
    logger.info(f"Received request for competitive keyword analysis for {request.primary_domain} by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary domain and at least one competitor domain must be provided.")
    
    try:
        result = await competitive_analysis_service_instance.perform_competitive_keyword_analysis(
            primary_domain=request.primary_domain,
            competitor_domains=request.competitor_domains
        )
        return CompetitiveKeywordAnalysisResponse.from_competitive_keyword_analysis_result(result)
    except Exception as e:
        logger.error(f"Error performing competitive keyword analysis: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform competitive keyword analysis: {e}")

@app.post("/link_building/prospects/identify", response_model=Dict[str, str], status_code=202) # New endpoint
async def identify_link_prospects_job(
    request: ProspectIdentificationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Submits a job to identify and score link building prospects.
    """
    logger.info(f"Received request to identify link prospects for {request.target_domain} by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='prospect_identification').inc()

    queue_request = QueueCrawlRequest(
        target_url=request.target_domain,
        initial_seed_urls=[], # Not directly used for this job type
        config=request.dict(), # Pass all request fields as config
        priority=5
    )
    queue_request.config["job_type"] = "prospect_identification" # Explicitly set job type in config for queue processing

    return await submit_crawl_to_queue(queue_request)

@app.get("/link_building/prospects", response_model=List[LinkProspectResponse]) # New endpoint
async def get_all_link_prospects_endpoint(
    status_filter: Optional[str] = Query(None, description="Filter prospects by status (e.g., 'identified', 'contacted', 'acquired')."),
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Retrieves all identified link building prospects, optionally filtered by status.
    """
    logger.info(f"Received request for all link prospects (status: {status_filter}) by user: {current_user.username}.")
    try:
        prospects = await link_building_service_instance.get_all_prospects(status_filter=status_filter)
        return [LinkProspectResponse.from_link_prospect(p) for p in prospects]
    except Exception as e:
        logger.error(f"Error retrieving link prospects: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve link prospects: {e}")

@app.put("/link_building/prospects/{prospect_url:path}", response_model=LinkProspectResponse) # New endpoint
async def update_link_prospect_endpoint(
    prospect_url: str,
    request: LinkProspectUpdateRequest,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Updates the status or other details of a specific link prospect.
    """
    logger.info(f"Received request to update link prospect {prospect_url} by user: {current_user.username}.")
    try:
        updated_prospect = await link_building_service_instance.update_prospect_status(
            url=prospect_url,
            new_status=request.status,
            last_outreach_date=request.last_outreach_date
        )
        if not updated_prospect:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link prospect not found.")
        
        # Manually update other fields if provided
        if request.contact_info is not None:
            updated_prospect.contact_info = request.contact_info
        if request.reasons is not None:
            updated_prospect.reasons = request.reasons
        if request.score is not None:
            updated_prospect.score = request.score
        
        db.save_link_prospect(updated_prospect) # Save the full updated object
        return LinkProspectResponse.from_link_prospect(updated_prospect)
    except Exception as e:
        logger.error(f"Error updating link prospect {prospect_url}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update link prospect: {e}")

@app.post("/link_building/campaigns", response_model=OutreachCampaignResponse, status_code=status.HTTP_201_CREATED) # New endpoint
async def create_outreach_campaign_endpoint(
    request: OutreachCampaignCreateRequest,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Creates a new link building outreach campaign.
    """
    logger.info(f"Received request to create outreach campaign '{request.name}' by user: {current_user.username}.")
    try:
        campaign = OutreachCampaign(
            id=str(uuid.uuid4()),
            name=request.name,
            target_domain=request.target_domain,
            description=request.description,
            start_date=request.start_date,
            end_date=request.end_date
        )
        db.save_outreach_campaign(campaign)
        return OutreachCampaignResponse.from_outreach_campaign(campaign)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating outreach campaign: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create outreach campaign: {e}")

@app.get("/link_building/campaigns", response_model=List[OutreachCampaignResponse]) # New endpoint
async def get_all_outreach_campaigns_endpoint(
    status_filter: Optional[str] = Query(None, description="Filter campaigns by status (e.g., 'active', 'completed')."),
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Retrieves all outreach campaigns, optionally filtered by status.
    """
    logger.info(f"Received request for all outreach campaigns (status: {status_filter}) by user: {current_user.username}.")
    try:
        campaigns = db.get_all_outreach_campaigns(status_filter=status_filter)
        return [OutreachCampaignResponse.from_outreach_campaign(c) for c in campaigns]
    except Exception as e:
        logger.error(f"Error retrieving outreach campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach campaign: {e}")

@app.get("/link_building/campaigns/{campaign_id}", response_model=OutreachCampaignResponse) # New endpoint
async def get_outreach_campaign_by_id_endpoint(
    campaign_id: str,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Retrieves a specific outreach campaign by its ID.
    """
    logger.info(f"Received request for outreach campaign {campaign_id} by user: {current_user.username}.")
    try:
        campaign = db.get_outreach_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach campaign not found.")
        return OutreachCampaignResponse.from_outreach_campaign(campaign)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving outreach campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach campaign: {e}")

@app.post("/link_building/events", response_model=OutreachEventResponse, status_code=status.HTTP_201_CREATED) # New endpoint
async def create_outreach_event_endpoint(
    request: OutreachEventCreateRequest,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Records a new outreach event for a prospect within a campaign.
    """
    logger.info(f"Received request to record outreach event for prospect {request.prospect_url} in campaign {request.campaign_id} by user: {current_user.username}.")
    try:
        # Basic validation: check if campaign and prospect exist
        campaign = db.get_outreach_campaign(request.campaign_id)
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Outreach campaign {request.campaign_id} not found.")
        prospect = db.get_link_prospect(request.prospect_url)
        if not prospect:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Link prospect {request.prospect_url} not found.")

        event = OutreachEvent(
            id=str(uuid.uuid4()),
            campaign_id=request.campaign_id,
            prospect_url=request.prospect_url,
            event_type=request.event_type,
            notes=request.notes,
            success=request.success
        )
        db.save_outreach_event(event)
        
        # Optionally update prospect status based on event type
        if request.event_type == "link_acquired":
            await link_building_service_instance.update_prospect_status(request.prospect_url, "acquired")
        elif request.event_type == "email_sent":
            await link_building_service_instance.update_prospect_status(request.prospect_url, "contacted", event.event_date)
        elif request.event_type == "rejected":
            await link_building_service_instance.update_prospect_status(request.prospect_url, "rejected")

        return OutreachEventResponse.from_outreach_event(event)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating outreach event: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create outreach event: {e}")

@app.get("/link_building/prospects/{prospect_url:path}/events", response_model=List[OutreachEventResponse]) # New endpoint
async def get_outreach_events_for_prospect_endpoint(
    prospect_url: str,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Retrieves all outreach events for a specific link prospect.
    """
    logger.info(f"Received request for outreach events for prospect {prospect_url} by user: {current_user.username}.")
    try:
        events = db.get_outreach_events_for_prospect(prospect_url)
        return [OutreachEventResponse.from_outreach_event(e) for e in events]
    except Exception as e:
        logger.error(f"Error retrieving outreach events for prospect {prospect_url}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach events: {e}")

@app.post("/ai/content_ideas", response_model=List[str]) # New endpoint
async def generate_content_ideas_endpoint(
    request: ContentGenerationRequest,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Generates content ideas for a given topic using AI.
    """
    logger.info(f"Received request for content ideas for topic '{request.topic}' by user: {current_user.username}.")
    if not request.topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topic must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        ideas = await ai_service_instance.generate_content_ideas(request.topic, request.num_ideas)
        if not ideas:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No content ideas generated for '{request.topic}'.")
        return ideas
    except Exception as e:
        logger.error(f"Error generating content ideas for '{request.topic}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate content ideas: {e}")

@app.post("/ai/competitor_strategy", response_model=Dict[str, Any]) # New endpoint
async def analyze_competitor_strategy_endpoint(
    request: CompetitorStrategyAnalysisRequest,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Analyzes competitor strategies using AI.
    """
    logger.info(f"Received request for AI competitor strategy analysis for {request.primary_domain} by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary domain and competitor domains must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        analysis_result = await ai_service_instance.analyze_competitors(request.primary_domain, request.competitor_domains)
        if not analysis_result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not perform competitor strategy analysis for {request.primary_domain}.")
        return analysis_result
    except Exception as e:
        logger.error(f"Error performing AI competitor strategy analysis for {request.primary_domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform AI competitor strategy analysis: {e}")

@app.post("/reports/schedule", response_model=Dict[str, str], status_code=202) # New endpoint
async def schedule_report_generation_job(
    request: ReportScheduleRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user) # Protected endpoint
):
    """
    Schedules a report generation job to run at a specific time or on a recurring basis.
    """
    logger.info(f"Received request to schedule report '{request.report_type}' for '{request.target_identifier}' by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='report_generation').inc()

    if not request.scheduled_at and not request.cron_schedule:
        raise HTTPException(status_code=400, detail="Either 'scheduled_at' or 'cron_schedule' must be provided for scheduling.")
    
    if request.cron_schedule and not request.scheduled_at:
        raise HTTPException(status_code=400, detail="For recurring reports, 'scheduled_at' must be provided for the initial run time.")

    queue_request = QueueCrawlRequest(
        target_url=request.target_identifier, # Re-use target_url for report target
        initial_seed_urls=[], # Not applicable
        config=request.config if request.config else {},
        priority=5,
        scheduled_at=request.scheduled_at,
        cron_schedule=request.cron_schedule
    )
    queue_request.config["job_type"] = "report_generation" # Explicitly set job type
    queue_request.config["report_job_type"] = request.report_type
    queue_request.config["report_target_identifier"] = request.target_identifier
    queue_request.config["report_format"] = request.format

    return await submit_crawl_to_queue(queue_request)

@app.get("/reports/{job_id}", response_model=ReportJobResponse) # New endpoint
async def get_report_job_status(job_id: str, current_user: User = Depends(get_current_user)):
    """
    Retrieves the status of a scheduled or generated report job.
    """
    logger.info(f"Received request for report job status {job_id} by user: {current_user.username}.")
    try:
        report_job = db.get_report_job(job_id)
        if not report_job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report job not found.")
        return ReportJobResponse.from_report_job(report_job)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving report job status {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve report job status: {e}")

@app.get("/reports/{job_id}/download") # New endpoint
async def download_report_file(job_id: str, current_user: User = Depends(get_current_user)):
    """
    Downloads the generated report file for a completed report job.
    """
    logger.info(f"Received request to download report for job {job_id} by user: {current_user.username}.")
    try:
        report_job = db.get_report_job(job_id)
        if not report_job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report job not found.")
        if report_job.status != CrawlStatus.COMPLETED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report job is not yet completed.")
        if not report_job.file_path or not os.path.exists(report_job.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found on server.")
        
        file_content = await asyncio.to_thread(lambda: open(report_job.file_path, "rb").read())
        filename = os.path.basename(report_job.file_path)
        media_type = "application/pdf" if report_job.format == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" # For .xlsx
        
        return Response(content=file_content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading report for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to download report: {e}")


@app.get("/health")
async def health_check():
    """
    Performs a comprehensive health check of the API and its dependencies.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dependencies": {},
        "environment_variables": { # New: Report environment variable status
            "LP_AUTH_SECRET_KEY": "SET" if os.getenv("LP_AUTH_SECRET_KEY") else "MISSING",
            "LP_DATABASE_URL": "SET" if os.getenv("LP_DATABASE_URL") else "MISSING", 
            "LP_REDIS_URL": "SET" if os.getenv("LP_REDIS_URL") else "MISSING"
        }
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

    # Auth Service
    try:
        # Check if secret key is configured, which is a basic health check for auth
        auth_service_instance._check_secret_key()
        health_status["dependencies"]["auth_service"] = {"status": "enabled"}
    except HTTPException as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["auth_service"] = {"status": "disabled", "error": e.detail}
        logger.error(f"Health check: Auth Service failed: {e.detail}")
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["auth_service"] = {"status": "failed_init", "error": str(e)}
        logger.error(f"Health check: Auth Service failed: {e}")


    status_code = 200 if health_status["status"] == "healthy" else 503
    return Response(content=json.dumps(health_status, indent=2), media_type="application/json", status_code=status_code)


@app.get("/metrics", response_class=Response)
async def prometheus_metrics():
    """
    Exposes Prometheus metrics.
    """
    return Response(content=get_metrics_text(), media_type="text/plain; version=0.0.4; charset=utf-8")

@app.get("/status")
async def get_system_status():
    """
    Provides detailed system status information.
    """
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0", # Placeholder for application version
        "uptime_seconds": time.time() - psutil.boot_time(),
        "python_version": sys.version,
        "system_info": {
            "hostname": os.uname().nodename,
            "platform": sys.platform,
            "architecture": os.uname().machine,
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_percent": psutil.cpu_percent(interval=None), # Non-blocking call
            "memory_total_bytes": psutil.virtual_memory().total,
            "memory_available_bytes": psutil.virtual_memory().available,
            "memory_percent": psutil.virtual_memory().percent,
            "disk_total_bytes": psutil.disk_usage('/').total,
            "disk_used_bytes": psutil.disk_usage('/').used,
            "disk_free_bytes": psutil.disk_usage('/').free,
            "disk_percent": psutil.disk_usage('/').percent,
            "network_io": psutil.net_io_counters()._asdict()
        }
    }

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

# New: WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates on job status and alerts.
    """
    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive. Clients can send messages, but we don't expect them.
            # If a message is received, it can be processed or ignored.
            # A simple ping-pong or timeout mechanism could be added for robustness.
            await websocket.receive_text() # This will block until a message is received or connection closes
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error for {websocket.client.host}:{websocket.client.port}: {e}", exc_info=True)
        connection_manager.disconnect(websocket)
