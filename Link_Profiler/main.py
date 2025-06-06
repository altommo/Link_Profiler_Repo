"""
API Endpoints for the Link Profiler System
File: Link_Profiler/main.py (formerly Link_Profiler/api/main.py)
"""

import os
import sys
import time
import logging # Import logging early
from typing import List, Optional, Dict, Any, Union, Annotated # Import Optional here

# --- Load environment variables from .env file ---
from dotenv import load_dotenv
load_dotenv()
# --- End .env loading ---

# --- Robust Project Root Discovery ---
# Assuming this file is at Link_Profiler/Link_Profiler/main.py
# The project root (containing setup.py) is one level up from the 'Link_Profiler' package directory.
# So, it's os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if project_root and project_root not in sys.path:
    sys.sys.path.insert(0, project_root)
    print(f"PROJECT_ROOT (discovered and added to sys.path): {project_root}")
else:
    print(f"PROJECT_ROOT (discovery failed or already in sys.path): {project_root}")

# --- End Robust Project Root Discovery ---

# Import core components needed for early initialization
from Link_Profiler.config.config_loader import ConfigLoader, config_loader # Import both class and singleton
from Link_Profiler.database.database import Database, db # Import both class and singleton
from Link_Profiler.services.auth_service import AuthService, auth_service_instance # Import both class and singleton
from Link_Profiler.utils.logging_config import LoggingConfig # Import LoggingConfig class
from Link_Profiler.utils.connection_manager import ConnectionManager, connection_manager

# Setup logging using the loaded configuration
# Use LoggingConfig.setup_logging directly
LoggingConfig.setup_logging(
    level=config_loader.get("logging.level", "INFO"),
    log_file=config_loader.get("logging.file", None), # Assuming a log file path can be configured
    json_format=config_loader.get("logging.json_format", False) # Assuming json_format can be configured
)

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
            logger.error(f"  Config:      {config_value[:20] if config_value else 'None'}...")
        elif not env_value and (config_path == "auth.secret_key" and config_value == "PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY"):
             logger.warning(f"WARNING: {env_var} is not set and config still uses placeholder. Authentication will fail.")
        elif not env_value and (config_path == "database.url" or config_path == "redis.url"):
             logger.warning(f"WARNING: {env_var} is not set. Using default/fallback for {config_path}.")
             if config_path == "database.url":
                 logger.warning("Please ensure LP_DATABASE_URL is set in your environment for production.")
             if config_path == "redis.url":
                 logger.warning("Please ensure LP_REDIS_URL is set in your environment for production.")

# Call validation after config loading
validate_critical_config()
# --- End Startup Configuration Diagnostics ---


# Retrieve configurations using the config_loader
# The default for redis.url is now handled in config.yaml
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

# Initialize Redis connection pool and client (moved up to ensure it's defined before lifespan)
import redis.asyncio as redis
redis_pool = redis.ConnectionPool.from_url(REDIS_URL)
redis_client: Optional[redis.Redis] = redis.Redis(connection_pool=redis_pool) # Make redis_client optional

# New: Initialize SessionManager
from Link_Profiler.utils.session_manager import session_manager # Use the singleton instance

# Now import other FastAPI and application modules
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, WebSocket, WebSocketDisconnect, Depends, status, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import urlparse
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import json
import uuid
import asyncio
import psutil
import psycopg2

from playwright.async_api import async_playwright, Browser
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm # Added missing imports
from fastapi.middleware.cors import CORSMiddleware # Import CORSMiddleware

from Link_Profiler.services.crawl_service import CrawlService
from Link_Profiler.services.domain_service import DomainService # Removed specific APIClient imports
from Link_Profiler.services.backlink_service import BacklinkService # Removed specific APIClient imports
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService
from Link_Profiler.services.expired_domain_finder_service import ExpiredDomainFinderService
from Link_Profiler.services.serp_service import SERPService # Removed specific APIClient imports
from Link_Profiler.services.keyword_service import KeywordService # Removed specific APIClient imports
from Link_Profiler.services.link_health_service import LinkHealthService
from Link_Profiler.services.ai_service import AIService
from Link_Profiler.services.alert_service import AlertService
from Link_Profiler.services.report_service import ReportService
from Link_Profiler.services.competitive_analysis_service import CompetitiveAnalysisService
from Link_Profiler.services.social_media_service import SocialMediaService
from Link_Profiler.services.web3_service import Web3Service
from Link_Profiler.services.link_building_service import LinkBuildingService
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
from Link_Profiler.crawlers.serp_crawler import SERPCrawler
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.crawlers.social_media_crawler import SocialMediaCrawler
from Link_Profiler.core.models import CrawlConfig, CrawlJob, LinkProfile, Backlink, serialize_model, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion, LinkIntersectResult, CompetitiveKeywordAnalysisResult, AlertRule, AlertSeverity, AlertChannel, User, ContentGapAnalysisResult, DomainHistory, LinkProspect, OutreachCampaign, OutreachEvent, ReportJob
from Link_Profiler.monitoring.prometheus_metrics import (
    API_REQUESTS_TOTAL, API_REQUEST_DURATION_SECONDS, get_metrics_text, # Re-added for middleware
    JOBS_CREATED_TOTAL, JOBS_IN_PROGRESS, JOBS_PENDING, JOBS_COMPLETED_SUCCESS_TOTAL, JOBS_FAILED_TOTAL
)
# Removed submit_crawl_to_queue, get_coordinator, set_coordinator_dependencies from job_submission_service
# as they are now in queue_endpoints.py
from Link_Profiler.api.queue_endpoints import set_coordinator_dependencies, get_coordinator # Import from queue_endpoints
from Link_Profiler.api.ai import set_global_ai_service_instance # Import for setting AI service instance
from Link_Profiler.api.dependencies import set_auth_service_instance, get_current_user # Import for setting auth service instance and get_current_user

# New: Import WebCrawler and SmartCrawlQueue
from Link_Profiler.crawlers.web_crawler import EnhancedWebCrawler # Changed to EnhancedWebCrawler
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue, Priority

# New: Import DistributedResilienceManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager


# New: Import API Clients
from Link_Profiler.clients.google_search_console_client import GoogleSearchConsoleClient # Renamed GSCClient to GoogleSearchConsoleClient
from Link_Profiler.clients.google_pagespeed_client import PageSpeedClient
from Link_Profiler.clients.google_trends_client import GoogleTrendsClient
from Link_Profiler.clients.whois_client import WHOISClient
from Link_Profiler.clients.dns_client import DNSClient
from Link_Profiler.clients.reddit_client import RedditClient
from Link_Profiler.clients.youtube_client import YouTubeClient
from Link_Profiler.clients.news_api_client import NewsAPIClient
# from Link_Profiler.clients.wayback_machine_client import WaybackClient
# from Link_Profiler.clients.common_crawl_client import CommonCrawlClient
# from Link_Profiler.clients.nominatim_client import NominatimClient
# from Link_Profiler.clients.security_trails_client import SecurityTrailsClient
# from Link_Profiler.clients.ssl_labs_client import SSLLabsClient

# Import api_cache singleton
from Link_Profiler.utils.api_cache import api_cache

# Import schemas
from Link_Profiler.api.schemas import (
    UserCreate, UserResponse, Token, CrawlJobResponse, LinkProfileResponse, DomainResponse, 
    ReportJobResponse, QueueStatsResponse, SERPResultResponse, KeywordSuggestionResponse, 
    LinkIntersectResponse, CompetitiveKeywordAnalysisResponse, AlertRuleResponse, 
    ContentGapAnalysisResultResponse, LinkProspectResponse, OutreachCampaignResponse, 
    OutreachEventResponse, SEOMetricsResponse, QueueCrawlRequest # Added QueueCrawlRequest
)

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
whois_client_instance = WHOISClient(session_manager=session_manager)
dns_client_instance = DNSClient(session_manager=session_manager)

# Initialize DomainService globally, but manage its lifecycle with lifespan
# Determine which DomainAPIClient to use based on priority: AbstractAPI > Real (paid) > WHOIS-JSON > Simulated
# The DomainService constructor now handles the internal assignment of api_client
# based on the config, so we just pass the necessary dependencies.
domain_service_instance = DomainService(
    session_manager=session_manager # Pass session manager
)

# New: Initialize GSCClient
gsc_client_instance = GoogleSearchConsoleClient(session_manager=session_manager)

# New: Instantiate DistributedResilienceManager early as it's a dependency for others
distributed_resilience_manager = DistributedResilienceManager(redis_client=redis_client)

# Initialize BacklinkService based on priority: GSC > OpenLinkProfiler > Real (paid) > Simulated
# Removed 'gsc_client' argument as BacklinkService internally handles GSCBacklinkAPIClient instantiation.
backlink_service_instance = BacklinkService(
    session_manager=session_manager, # Pass session manager
    resilience_manager=distributed_resilience_manager # Pass resilience manager
)

# New: Initialize PageSpeedClient
pagespeed_client_instance = PageSpeedClient(session_manager=session_manager)

# New: Initialize SERPService and SERPCrawler
serp_crawler_instance = None
if config_loader.get("serp_crawler.playwright.enabled"):
    logger.info("Initialising Playwright SERPCrawler.")
    serp_crawler_instance = SERPCrawler(
        headless=config_loader.get("serp_crawler.playwright.headless"),
        browser_type=config_loader.get("serp_crawler.playwright.browser_type")
    )
serp_service_instance = SERPService(
    serp_crawler=serp_crawler_instance,
    pagespeed_client=pagespeed_client_instance, # New: Pass pagespeed_client_instance
    session_manager=session_manager # Pass session manager
)

# New: Initialize GoogleTrendsClient
google_trends_client_instance = GoogleTrendsClient(session_manager=session_manager)

# New: Initialize KeywordService and KeywordScraper
keyword_scraper_instance = None
if config_loader.get("keyword_scraper.enabled"): # Assuming a config for keyword_scraper.enabled
    logger.info("Initialising KeywordScraper.")
    keyword_scraper_instance = KeywordScraper(session_manager=session_manager)
keyword_service_instance = KeywordService(
    keyword_scraper=keyword_scraper_instance,
    google_trends_client=google_trends_client_instance, # New: Pass google_trends_client_instance
    session_manager=session_manager # Pass session manager
)

# New: Initialize LinkHealthService
link_health_service_instance = LinkHealthService(db, session_manager=session_manager) # Pass session_manager

# New: Initialize TechnicalAuditor
technical_auditor_instance = TechnicalAuditor(
    lighthouse_path=config_loader.get("technical_auditor.lighthouse_path") # Allow custom path for Lighthouse CLI
)

# New: Initialize AI Service
ai_service_instance = AIService(database=db, session_manager=session_manager) # Pass database and session_manager

# New: Initialize Alert Service
alert_service_instance = AlertService(db, connection_manager)

# New: Initialize Report Service
report_service_instance = ReportService(db)

# New: Initialize Competitive Analysis Service
competitive_analysis_service_instance = CompetitiveAnalysisService(db, backlink_service_instance, serp_service_instance)

# New: Initialize RedditClient, YouTubeClient, NewsAPIClient
reddit_client_instance = RedditClient(session_manager=session_manager)
youtube_client_instance = YouTubeClient(session_manager=session_manager)
news_api_client_instance = NewsAPIClient(session_manager=session_manager)

# New: Initialize Social Media Service and Crawler
social_media_crawler_instance = None
if config_loader.get("social_media_crawler.enabled"):
    logger.info("Initialising SocialMediaCrawler.")
    social_media_crawler_instance = SocialMediaCrawler(session_manager=session_manager)
social_media_service_instance = SocialMediaService(
    database=db, # Pass database
    social_media_crawler=social_media_crawler_instance,
    reddit_client=reddit_client_instance, # New: Pass RedditClient
    youtube_client=youtube_client_instance, # New: Pass YouTubeClient
    news_api_client=news_api_client_instance, # New: Pass NewsAPIClient
    session_manager=session_manager # Re-add session_manager
)

# New: Initialize Web3 Service
web3_service_instance = Web3Service(
    database=db, # Pass database, removed session_manager as per issue
    session_manager=session_manager # Pass session_manager
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
    playwright_browser=playwright_browser_instance, # Pass the global Playwright browser instance
    resilience_manager=distributed_resilience_manager # Pass resilience manager
) 
expired_domain_finder_service = ExpiredDomainFinderService(db, domain_service_instance, domain_analyzer_service) # Corrected class name

# --- New: Instantiate SmartCrawlQueue and WebCrawler ---
# Load crawler-specific configuration
crawler_config_data = config_loader.get("crawler", {})
# Ensure ml_rate_optimization is set based on rate_limiting config
crawler_config_data['ml_rate_limiter_enabled'] = config_loader.get("rate_limiting.ml_enhanced", False) # Corrected key
# Pass relevant anti_detection settings to CrawlConfig
crawler_config_data['user_agent_rotation'] = config_loader.get("anti_detection.user_agent_rotation", False)
crawler_config_data['request_header_randomization'] = config_loader.get("anti_detection.request_header_randomization", False)
crawler_config_data['human_like_delays'] = config_loader.get("anti_detection.human_like_delays", False)
crawler_config_data['stealth_mode'] = config_loader.get("anti_detection.stealth_mode", False)
crawler_config_data['browser_fingerprint_randomization'] = config_loader.get("anti_detection.browser_fingerprint_randomization", False)
crawler_config_data['captcha_solving_enabled'] = config_loader.get("anti_detection.captcha_solving_enabled", False)
crawler_config_data['anomaly_detection_enabled'] = config_loader.get("anti_detection.anomaly_detection_enabled", False)
crawler_config_data['use_proxies'] = config_loader.get("proxy.use_proxies", False)
crawler_config_data['proxy_list'] = config_loader.get("proxy.proxy_list", [])
crawler_config_data['render_javascript'] = config_loader.get("browser_crawler.enabled", False)
crawler_config_data['browser_type'] = config_loader.get("browser_crawler.browser_type", "chromium")
crawler_config_data['headless_browser'] = config_loader.get("browser_crawler.headless", True)

main_crawl_config = CrawlConfig(**crawler_config_data)

# Create SmartCrawlQueue instance
smart_crawl_queue = SmartCrawlQueue(redis_client=redis_client)

# Create WebCrawler instance, passing the SmartCrawlQueue
main_web_crawler = EnhancedWebCrawler(
    config=main_crawl_config, 
    crawl_queue=smart_crawl_queue, 
    ai_service=ai_service_instance, 
    browser=playwright_browser_instance, 
    resilience_manager=distributed_resilience_manager, 
    session_manager=session_manager
) # Changed to EnhancedWebCrawler
# --- End New Instantiation ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for managing the lifespan of the FastAPI application.
    Ensures resources like aiohttp sessions are properly opened and closed.
    """
    # Use the shared ConnectionManager instance for WebSocket communication

    context_managers = [
        session_manager, # New: Add SessionManager to lifespan
        domain_service_instance,
        api_cache, # Initialize API cache
        auth_service_instance, # New: Add AuthService to lifespan
        connection_manager,
        # The following services are initialized with dependencies that might not be ready yet
        # or are managed by their own internal lifecycles.
        # They should be initialized within the lifespan if they need async setup/teardown.
        # For now, we'll assume their __aenter__/__aexit__ are robust enough.
        backlink_service_instance,
        serp_service_instance,
        keyword_service_instance,
        link_health_service_instance,
        technical_auditor_instance,
        alert_service_instance, # New: Add AlertService to lifespan
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
        news_api_client_instance, # New: Add NewsAPIClient
        main_web_crawler, # Add the main_web_crawler to the lifespan context
        distributed_resilience_manager # New: Add DistributedResilienceManager to lifespan
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


    entered_contexts = []
    try:
        for cm in context_managers:
            logger.info(f"Application startup: Entering {cm.__class__.__name__} context.")
            # Call __aenter__ and store the result (which is usually 'self' for context managers)
            entered_contexts.append(await cm.__aenter__())
        
        logger.info("Application startup: Pinging Redis.")
        # The global redis_client is already defined at the top level.
        if redis_client: # Only try to ping if client was initialized
            try:
                await redis_client.ping()
                logger.info("Redis connection successful.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                # Do not set redis_client to None here, as it's a global variable
                # and might be used by other services. Let the service handle its own
                # connection status.
        else:
            logger.warning("Redis client not initialized. Skipping Redis ping.")
        
        # Set dependencies for queue_endpoints before getting coordinator
        set_coordinator_dependencies(
            redis_client=redis_client,
            config_loader=config_loader,
            db=db,
            alert_service=alert_service_instance,
            connection_manager=connection_manager
        )

        # Set the global AI service instance for the ai_router
        set_global_ai_service_instance(ai_service_instance)

        # Set the global Auth service instance for the dependencies module
        set_auth_service_instance(auth_service_instance)

        # Initialize and start JobCoordinator background tasks
        try:
            await get_coordinator() # Use the get_coordinator from queue_endpoints
            logger.info("JobCoordinator successfully initialized and background tasks started via get_coordinator.")
        except Exception as e:
            logger.error(f"Failed to initialize JobCoordinator during lifespan startup: {e}", exc_info=True)
            # Depending on criticality, you might want to raise an exception here
            # to prevent the app from starting if the queue system is essential.
            # For now, we'll just log and continue.

        # Start alert rule refreshing in background
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
    description="API for comprehensive link profiling, SEO analysis, and domain intelligence.",
    version=config_loader.get("system.current_code_version", "0.1.0"),
    lifespan=lifespan # Register the lifespan context manager
)

# Initialize Jinja2Templates (moved up to ensure it's defined before routes use it)
# Dashboard templates moved to project root under 'admin-management-console'
templates = Jinja2Templates(directory=os.path.join(project_root, "admin-management-console"))

# --- Static Files ---
# Mount the 'static' directory to serve CSS and JS files
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(project_root, "admin-management-console", "static")),
    name="static",
)

# --- CORS Middleware ---
# New: Add CORSMiddleware to allow cross-origin requests from the monitoring dashboard
# Configure allowed origins based on your deployment.
# For production, replace "*" with your actual dashboard domain (e.g., "https://monitor.yspanel.com")
origins = [
    "https://monitor.yspanel.com",  # Your monitoring dashboard domain
    "https://api.yspanel.com",     # Your main API domain
    "https://linkprofiler.yspanel.com",  # Alternative domain
    "https://yspanel.com",         # Main domain
    "https://www.yspanel.com",     # WWW domain
    "http://localhost:8001",       # For local testing
    "http://localhost:8000",       # For local testing
    "null"                         # For file:// protocol testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development, allow all origins. Restrict in production.
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Dependency to get the current user
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # Define here for use in Depends

# NOTE: The get_current_user and get_current_admin_user functions are now defined
# in Link_Profiler/api/dependencies.py and imported by other routers.
# We keep them here for the /token and /register endpoints which are directly in main.py.
# The version in dependencies.py will be used by other routers.
# This is a slight duplication but necessary to avoid circular imports if main.py
# were to import get_current_user from dependencies.py at the top level.
# The `set_auth_service_instance` call in lifespan ensures the dependencies.py
# version is correctly initialized.

async def get_current_user_for_main(token: str = Depends(oauth2_scheme)) -> User:
    user = await auth_service_instance.get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_admin_user_for_main(current_user: User = Depends(get_current_user_for_main)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation forbidden: Admin access required"
        )
    return current_user

# --- Authentication Routes ---
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
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

@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_create: UserCreate):
    existing_user = db.get_user_by_username(user_create.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    existing_email = db.get_user_by_email(user_create.email)
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    new_user = await auth_service_instance.register_user(
        username=user_create.username,
        email=user_create.email,
        password=user_create.password
    )
    return UserResponse.from_user(new_user)

@app.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user_for_main)):
    return UserResponse.from_user(current_user)

# --- Health and Monitoring Routes ---
@app.get("/health")
async def health_check():
    db_status = db.ping()
    # Add other service health checks here
    return {"status": "ok", "database_connected": db_status}

@app.get("/metrics")
async def metrics():
    return HTMLResponse(content=get_metrics_text(), media_type="text/plain")

# --- Core Functionality Routes (Examples) ---
@app.get("/link_profile/{target_url:path}", response_model=LinkProfileResponse)
async def get_link_profile(target_url: str, current_user: User = Depends(get_current_user_for_main)):
    profile = db.get_link_profile(target_url)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link profile not found")
    return LinkProfileResponse.from_link_profile(profile)

@app.get("/domain/info/{domain_name}", response_model=DomainResponse)
async def get_domain_info(domain_name: str, current_user: User = Depends(get_current_user_for_main)):
    domain = db.get_domain(domain_name)
    if not domain:
        # Attempt to fetch if not in DB
        async with domain_service_instance as ds:
            domain = await ds.get_domain_info(domain_name)
            if domain:
                db.save_domain(domain) # Save newly fetched domain
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain info not found")
    return DomainResponse.from_domain(domain)

# --- Include API Routers ---
# Import API Routers here, after dependencies like get_current_user are defined
from Link_Profiler.api.ai import ai_router
from Link_Profiler.api.analytics import analytics_router
from Link_Profiler.api.competitive_analysis import competitive_analysis_router
from Link_Profiler.api.crawl_audit import crawl_audit_router
from Link_Profiler.api.link_building import link_building_router
from Link_Profiler.api.public_jobs import public_jobs_router
from Link_Profiler.api.reports import reports_router
from Link_Profiler.api.users import users_router
from Link_Profiler.api.websocket import websocket_router
from Link_Profiler.api.mission_control import mission_control_router
from Link_Profiler.api.queue_endpoints import queue_router # Import queue_router

app.include_router(ai_router)
app.include_router(analytics_router)
app.include_router(competitive_analysis_router)
app.include_router(crawl_audit_router)
app.include_router(link_building_router)
app.include_router(public_jobs_router)
app.include_router(reports_router)
app.include_router(users_router)
app.include_router(websocket_router)
app.include_router(mission_control_router)
app.include_router(queue_router) # Include queue_router

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Link Profiler API</title>
        <link rel="icon" href="/static/favicon.ico" type="image/x-icon">
    </head>
    <body>
        <h1>Welcome to the Link Profiler API!</h1>
        <p>Visit <a href="/docs">/docs</a> for API documentation.</p>
        <p>Visit <a href="/redoc">/redoc</a> for ReDoc documentation.</p>
    </body>
    </html>
    """
