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


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, WebSocket, WebSocketDisconnect, Depends, status, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union, Annotated
import logging
from urllib.parse import urlparse
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import redis.asyncio as redis
import json
import uuid
import asyncio
import psutil
import psycopg2

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
from Link_Profiler.services.competitive_analysis_service import CompetitiveAnalysisService
from Link_Profiler.services.social_media_service import SocialMediaService
from Link_Profiler.services.web3_service import Web3Service
from Link_Profiler.services.link_building_service import LinkBuildingService
from Link_Profiler.services.auth_service import AuthService
from Link_Profiler.database.database import Database
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
from Link_Profiler.crawlers.serp_crawler import SERPCrawler
from Link_Profiler.crawlers.keyword_scraper import KeywordScraper
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.crawlers.social_media_crawler import SocialMediaCrawler
from Link_Profiler.core.models import CrawlConfig, CrawlJob, LinkProfile, Backlink, serialize_model, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion, LinkIntersectResult, CompetitiveKeywordAnalysisResult, AlertRule, AlertSeverity, AlertChannel, User, ContentGapAnalysisResult, DomainHistory, LinkProspect, OutreachCampaign, OutreachEvent, ReportJob
from Link_Profiler.monitoring.prometheus_metrics import (
    API_REQUESTS_TOTAL, API_REQUEST_DURATION_SECONDS, get_metrics_text,
    JOBS_CREATED_TOTAL, JOBS_IN_PROGRESS, JOBS_PENDING, JOBS_COMPLETED_SUCCESS_TOTAL, JOBS_FAILED_TOTAL
)
from Link_Profiler.api.queue_endpoints import add_queue_endpoints, submit_crawl_to_queue, QueueCrawlRequest, get_coordinator
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.utils.logging_config import setup_logging, get_default_logging_config
from Link_Profiler.utils.data_exporter import export_to_csv
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.proxy_manager import proxy_manager
from Link_Profiler.utils.connection_manager import ConnectionManager, connection_manager


# New: Import API Clients
from Link_Profiler.clients.google_search_console_client import GSCClient
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
# Moved to Link_Profiler/api/schemas.py
from Link_Profiler.api.schemas import (
    CrawlConfigRequest, StartCrawlRequest, LinkHealthAuditRequest, TechnicalAuditRequest,
    DomainAnalysisJobRequest, FullSEOAduitRequest, Web3CrawlRequest, SocialMediaCrawlRequest,
    ContentGapAnalysisRequest, CrawlErrorResponse, CrawlJobResponse, LinkProfileResponse,
    BacklinkResponse, DomainResponse, DomainAnalysisResponse, FindExpiredDomainsRequest,
    FindExpiredDomainsResponse, SERPSearchRequest, SERPResultResponse, KeywordSuggestRequest,
    KeywordSuggestionResponse, LinkIntersectRequest, LinkIntersectResponse,
    CompetitiveKeywordAnalysisRequest, CompetitiveKeywordAnalysisResponse,
    AlertRuleCreateRequest, AlertRuleResponse, ContentGapAnalysisResultResponse,
    LinkProspectResponse, LinkProspectUpdateRequest, ProspectIdentificationRequest,
    OutreachCampaignCreateRequest, OutreachCampaignResponse, OutreachEventCreateRequest,
    OutreachEventResponse, ContentGenerationRequest, CompetitorStrategyAnalysisRequest,
    ReportScheduleRequest, ReportJobResponse, LinkVelocityRequest, DomainHistoryResponse,
    TopicClusteringRequest, Token, UserCreate, UserResponse
)


# --- API Endpoints ---

# Import the new routers
from Link_Profiler.api.auth import auth_router
from Link_Profiler.api.users import users_router
from Link_Profiler.api.crawl_audit import crawl_audit_router # New: Import the crawl_audit router
from Link_Profiler.api.dependencies import get_current_user # Import get_current_user for other endpoints that need it

# Register the routers with the main app
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(crawl_audit_router) # New: Include the crawl_audit router


@app.get("/link_profile/{target_domain}/link_velocity", response_model=Dict[str, int]) # Protected endpoint
async def get_link_velocity(target_domain: str, request_params: LinkVelocityRequest = Depends(), current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves the link velocity (new backlinks over time) for a given target domain.
    """
    logger.info(f"API: Received request for link velocity of {target_domain} by user: {current_user.username}.")
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
        logger.error(f"API: Error retrieving link velocity for {target_domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve link velocity: {e}")

@app.get("/domain/{domain_name}/history", response_model=List[DomainHistoryResponse]) # Protected endpoint
async def get_domain_history_endpoint(
    domain_name: str, 
    num_snapshots: Annotated[int, Query(12, gt=0, description="Number of historical snapshots to retrieve.")],
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Retrieves the historical progression of a domain's authority metrics.
    """
    logger.info(f"API: Received request for domain history of {domain_name} by user: {current_user.username}.")
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
        logger.error(f"API: Error retrieving domain history for {domain_name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve domain history: {e}")

@app.get("/serp/history", response_model=List[SERPResultResponse]) # New endpoint
async def get_serp_position_history_endpoint(
    target_url: Annotated[str, Query(..., description="The URL for which to track SERP history.")],
    keyword: Annotated[str, Query(..., description="The keyword for which to track SERP history.")],
    num_snapshots: Annotated[int, Query(12, gt=0, description="The maximum number of recent historical snapshots to retrieve.")],
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Retrieves the historical SERP positions for a specific URL and keyword.
    """
    logger.info(f"API: Received request for SERP history for URL '{target_url}' and keyword '{keyword}' by user: {current_user.username}.")
    if not target_url or not keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL and keyword must be provided.")
    
    try:
        history_data = db.get_serp_position_history(target_url, keyword, num_snapshots)
        if not history_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No SERP history found for URL '{target_url}' and keyword '{keyword}'.")
        return [SERPResultResponse.from_serp_result(sr) for sr in history_data]
    except Exception as e:
        logger.error(f"API: Error retrieving SERP position history for '{target_url}' and '{keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve SERP position history: {e}")

@app.post("/keyword/semantic_suggestions", response_model=List[str]) # New endpoint
async def get_semantic_keyword_suggestions_endpoint(
    primary_keyword: Annotated[str, Query(..., description="The primary keyword to get semantic suggestions for.")],
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Generates a list of semantically related keywords using AI.
    """
    logger.info(f"API: Received request for semantic keyword suggestions for '{primary_keyword}' by user: {current_user.username}.")
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
        logger.error(f"API: Error generating semantic keyword suggestions for '{primary_keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate semantic keyword suggestions: {e}")

@app.post("/competitor/link_intersect", response_model=LinkIntersectResponse) # New endpoint
async def get_link_intersect(request: LinkIntersectRequest, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Performs a link intersect analysis to find common linking domains between a primary domain and competitors.
    """
    logger.info(f"API: Received request for link intersect analysis for {request.primary_domain} by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary domain and at least one competitor domain must be provided.")
    
    try:
        result = await competitive_analysis_service_instance.perform_link_intersect_analysis(
            primary_domain=request.primary_domain,
            competitor_domains=request.competitor_domains
        )
        return LinkIntersectResponse.from_link_intersect_result(result)
    except Exception as e:
        logger.error(f"API: Error performing link intersect analysis: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform link intersect analysis: {e}")

@app.post("/competitor/keyword_analysis", response_model=CompetitiveKeywordAnalysisResponse) # New endpoint
async def get_competitive_keyword_analysis(request: CompetitiveKeywordAnalysisRequest, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Performs a competitive keyword analysis, identifying common keywords, keyword gaps, and unique keywords.
    """
    logger.info(f"API: Received request for competitive keyword analysis for {request.primary_domain} by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary domain and at least one competitor domain must be provided.")
    
    try:
        result = await competitive_analysis_service_instance.perform_competitive_keyword_analysis(
            primary_domain=request.primary_domain,
            competitor_domains=request.competitor_domains
        )
        return CompetitiveKeywordAnalysisResponse.from_competitive_keyword_analysis_result(result)
    except Exception as e:
        logger.error(f"API: Error performing competitive keyword analysis: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform competitive keyword analysis: {e}")

@app.post("/link_building/prospects/identify", response_model=Dict[str, str], status_code=202) # New endpoint
async def identify_link_prospects_job(
    request: ProspectIdentificationRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Submits a job to identify and score link building prospects.
    """
    logger.info(f"API: Received request to identify link prospects for {request.target_domain} by user: {current_user.username}.")
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
    status_filter: Annotated[Optional[str], Query(None, description="Filter prospects by status (e.g., 'identified', 'contacted', 'acquired').")],
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Retrieves all identified link building prospects, optionally filtered by status.
    """
    logger.info(f"API: Received request for all link prospects (status: {status_filter}) by user: {current_user.username}.")
    try:
        prospects = await link_building_service_instance.get_all_prospects(status_filter=status_filter)
        return [LinkProspectResponse.from_link_prospect(p) for p in prospects]
    except Exception as e:
        logger.error(f"API: Error retrieving link prospects: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve link prospects: {e}")

@app.put("/link_building/prospects/{prospect_url:path}", response_model=LinkProspectResponse) # New endpoint
async def update_link_prospect_endpoint(
    prospect_url: str,
    request: LinkProspectUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Updates the status or other details of a specific link prospect.
    """
    logger.info(f"API: Received request to update link prospect {prospect_url} by user: {current_user.username}.")
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
        logger.error(f"API: Error updating link prospect {prospect_url}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update link prospect: {e}")

@app.post("/link_building/campaigns", response_model=OutreachCampaignResponse, status_code=status.HTTP_201_CREATED) # New endpoint
async def create_outreach_campaign_endpoint(
    request: OutreachCampaignCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Creates a new link building outreach campaign.
    """
    logger.info(f"API: Received request to create outreach campaign '{request.name}' by user: {current_user.username}.")
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
        logger.error(f"API: Error creating outreach campaign: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create outreach campaign: {e}")

@app.get("/link_building/campaigns", response_model=List[OutreachCampaignResponse]) # New endpoint
async def get_all_outreach_campaigns_endpoint(
    status_filter: Annotated[Optional[str], Query(None, description="Filter campaigns by status (e.g., 'active', 'completed').")],
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Retrieves all outreach campaigns, optionally filtered by status.
    """
    logger.info(f"API: Received request for all outreach campaigns (status: {status_filter}) by user: {current_user.username}.")
    try:
        campaigns = db.get_all_outreach_campaigns(status_filter=status_filter)
        return [OutreachCampaignResponse.from_outreach_campaign(c) for c in campaigns]
    except Exception as e:
        logger.error(f"API: Error retrieving outreach campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach campaign: {e}")

@app.get("/link_building/campaigns/{campaign_id}", response_model=OutreachCampaignResponse) # New endpoint
async def get_outreach_campaign_by_id_endpoint(
    campaign_id: str,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Retrieves a specific outreach campaign by its ID.
    """
    logger.info(f"API: Received request for outreach campaign {campaign_id} by user: {current_user.username}.")
    try:
        campaign = db.get_outreach_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach campaign not found.")
        return OutreachCampaignResponse.from_outreach_campaign(campaign)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error retrieving outreach campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach campaign: {e}")

@app.post("/link_building/events", response_model=OutreachEventResponse, status_code=status.HTTP_201_CREATED) # New endpoint
async def create_outreach_event_endpoint(
    request: OutreachEventCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Records a new outreach event for a prospect within a campaign.
    """
    logger.info(f"API: Received request to record outreach event for prospect {request.prospect_url} in campaign {request.campaign_id} by user: {current_user.username}.")
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
        logger.error(f"API: Error creating outreach event: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create outreach event: {e}")

@app.get("/link_building/prospects/{prospect_url:path}/events", response_model=List[OutreachEventResponse]) # New endpoint
async def get_outreach_events_for_prospect_endpoint(
    prospect_url: str,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Retrieves all outreach events for a specific link prospect.
    """
    logger.info(f"API: Received request for outreach events for prospect {prospect_url} by user: {current_user.username}.")
    try:
        events = db.get_outreach_events_for_prospect(prospect_url)
        return [OutreachEventResponse.from_outreach_event(e) for e in events]
    except Exception as e:
        logger.error(f"API: Error retrieving outreach events for prospect {prospect_url}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve outreach events: {e}")

@app.post("/ai/content_ideas", response_model=List[str]) # New endpoint
async def generate_content_ideas_endpoint(
    request: ContentGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Generates content ideas for a given topic using AI.
    """
    logger.info(f"API: Received request for content ideas for topic '{request.topic}' by user: {current_user.username}.")
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
        logger.error(f"API: Error generating content ideas for '{request.topic}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate content ideas: {e}")

@app.post("/ai/competitor_strategy", response_model=Dict[str, Any]) # New endpoint
async def analyze_competitor_strategy_endpoint(
    request: CompetitorStrategyAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Analyzes competitor strategies using AI.
    """
    logger.info(f"API: Received request for AI competitor strategy analysis for {request.primary_domain} by user: {current_user.username}.")
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
        logger.error(f"API: Error performing AI competitor strategy analysis for {request.primary_domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform AI competitor strategy analysis: {e}")

@app.post("/reports/schedule", response_model=Dict[str, str], status_code=202) # New endpoint
async def schedule_report_generation_job(
    request: ReportScheduleRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)] # Protected endpoint
):
    """
    Schedules a report generation job to run at a specific time or on a recurring basis.
    """
    logger.info(f"API: Received request to schedule report '{request.report_type}' for '{request.target_identifier}' by user: {current_user.username}.")
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
async def get_report_job_status(job_id: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves the status of a scheduled or generated report job.
    """
    logger.info(f"API: Received request for report job status {job_id} by user: {current_user.username}.")
    try:
        report_job = db.get_report_job(job_id)
        if not report_job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report job not found.")
        return ReportJobResponse.from_report_job(report_job)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error retrieving report job status {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve report job status: {e}")

@app.get("/reports/{job_id}/download") # New endpoint
async def download_report_file(job_id: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Downloads the generated report file for a completed report job.
    """
    logger.info(f"API: Received request to download report for job {job_id} by user: {current_user.username}.")
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
        logger.error(f"API: Error downloading report for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to download report: {e}")

# --- Helper function for aggregated stats (used by /api/stats endpoint) ---
async def _get_aggregated_stats_for_api() -> Dict[str, Any]:
    """Aggregates various statistics for the /api/stats endpoint."""
    
    # Get coordinator instance to access its internal state
    coord = await get_coordinator()
    stats_from_coordinator = await coord.get_queue_stats()

    # Queue Metrics
    queue_metrics = {
        "pending_jobs": stats_from_coordinator.get("pending_jobs", 0),
        "results_pending": stats_from_coordinator.get("results_pending", 0), # This might be missing from coord.get_queue_stats()
        "active_satellites": stats_from_coordinator.get("active_crawlers", 0),
        "satellites": [], # Initialize as empty list
        "timestamp": datetime.now().isoformat()
    }
    
    # Populate detailed satellite info from coordinator's stats
    # The coordinator's get_queue_stats returns a dictionary of satellite_crawlers
    # We need to convert this dictionary of dictionaries into a list of dictionaries
    # and ensure datetime objects are isoformatted for JSON serialization.
    detailed_satellites = []
    for crawler_id, details in stats_from_coordinator.get("satellite_crawlers", {}).items():
        satellite_data = details.copy() # Create a mutable copy
        if "timestamp" in satellite_data and isinstance(satellite_data["timestamp"], datetime):
            satellite_data["timestamp"] = satellite_data["timestamp"].isoformat()
        # Ensure last_seen is isoformatted if it's a datetime object
        if "last_seen" in satellite_data and isinstance(satellite_data["last_seen"], datetime):
            satellite_data["last_seen"] = satellite_data["last_seen"].isoformat()
        detailed_satellites.append(satellite_data)
    
    queue_metrics["satellites"] = detailed_satellites


    # Performance Stats (simplified, as full trends are complex)
    performance_stats = {"error": "Database not connected"}
    if db:
        try:
            # Get total jobs and successful jobs from DB for a simple success rate
            all_jobs = db.get_all_crawl_jobs() # This might be slow for very large datasets
            total_jobs = len(all_jobs)
            successful_jobs = sum(1 for job in all_jobs if job.status == CrawlStatus.COMPLETED)
            
            success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0.0
            
            performance_stats = {
                "total_jobs_processed": total_jobs,
                "successful_jobs": successful_jobs,
                "success_rate": round(success_rate, 1),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting performance stats for /api/stats: {e}", exc_info=True)
            performance_stats = {"error": str(e)}
        finally:
            if db and hasattr(db, 'Session'):
                db.Session.remove()

    # Data Summaries
    data_summaries = {"error": "Database not connected"}
    if db:
        try:
            total_link_profiles = len(db.get_all_link_profiles())
            total_domains_analyzed = len(db.get_all_domains())
            competitive_keyword_analyses = db.get_count_of_competitive_keyword_analyses()
            total_backlinks_stored = len(db.get_all_backlinks())

            data_summaries = {
                "total_link_profiles": total_link_profiles,
                "total_domains_analyzed": total_domains_analyzed,
                "competitive_keyword_analyses": competitive_keyword_analyses,
                "total_backlinks_stored": total_backlinks_stored,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting data summaries for /api/stats: {e}", exc_info=True)
            data_summaries = {"error": str(e)}
        finally:
            if db and hasattr(db, 'Session'):
                db.Session.remove()

    # System Stats (reusing logic from /status endpoint)
    system_stats = {}
    try:
        system_stats = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory": { # Nested memory object
                "percent": psutil.virtual_memory().percent,
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "used": psutil.virtual_memory().used
            },
            "disk": { # Nested disk object
                "percent": psutil.disk_usage('/').percent,
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free
            },
            "uptime": time.time() - psutil.boot_time() # Renamed from uptime_seconds
        }
    except Exception as e:
        logger.error(f"Error getting system stats for /api/stats: {e}", exc_info=True)
        system_stats = {"error": str(e)}

    # API Health (reusing logic from /health endpoint)
    api_health = {}
    try:
        # Call the internal health_check function directly
        health_response = await health_check()
        api_health = json.loads(health_response.body.decode('utf-8'))
    except Exception as e:
        logger.error(f"Error getting API health for /api/stats: {e}", exc_info=True)
        api_health = {"status": "error", "message": str(e)}

    # Redis Stats
    redis_stats = {"status": "disconnected"}
    if redis_client:
        try:
            info = await redis_client.info()
            redis_stats = {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "status": "connected"
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats for /api/stats: {e}", exc_info=True)
            redis_stats = {"status": "error", "message": str(e)}

    # Database Stats
    database_stats = {"status": "disconnected"}
    if db:
        try:
            db.ping()
            conn = psycopg2.connect(db.db_url)
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    relname,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes
                FROM pg_stat_user_tables;
            """)
            tables = []
            for row in cur.fetchall():
                tables.append({
                    "table": row[0],
                    "inserts": row[1],
                    "updates": row[2],
                    "deletes": row[3]
                })
            cur.close()
            conn.close()
            database_stats = {
                "status": "connected",
                "tables": tables
            }
        except Exception as e:
            logger.error(f"Error getting database stats for /api/stats: {e}", exc_info=True)
            database_stats = {"status": "error", "message": str(e)}
        finally:
            if db and hasattr(db, 'Session'):
                db.Session.remove()

    return {
        "queue_metrics": queue_metrics,
        "performance_stats": performance_stats,
        "data_summaries": data_summaries,
        "system": system_stats,
        "api_health": api_health,
        "redis": redis_stats,
        "database": database_stats,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/stats")
async def get_api_stats():
    """
    Retrieves aggregated statistics for the Link Profiler system.
    This endpoint is primarily consumed by the monitoring dashboard and does not require authentication.
    """
    logger.info("API: Received request for aggregated stats (public endpoint).")
    return await _get_aggregated_stats_for_api()

@app.get("/api/jobs/all", response_model=List[CrawlJobResponse])
async def get_all_jobs_api(
    status_filter: Annotated[Optional[str], Query(None, description="Filter jobs by status (e.g., 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED').")]
):
    """
    Retrieves all crawl jobs, optionally filtered by status.
    This endpoint is primarily consumed by the monitoring dashboard and does not require authentication.
    Returns the most recent 50 jobs.
    """
    logger.info(f"API: Received request for all jobs (public endpoint, status_filter: {status_filter}).")
    try:
        all_jobs = db.get_all_crawl_jobs()
        logger.debug(f"API: Retrieved {len(all_jobs)} jobs from database before filtering.")
        
        if status_filter:
            try:
                filter_status = CrawlStatus[status_filter.upper()]
                all_jobs = [job for job in all_jobs if job.status == filter_status]
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid status_filter: {status_filter}. Must be one of {list(CrawlStatus.__members__.keys())}.")
        
        # Sort by created_date descending and limit to the most recent 50
        sorted_jobs = sorted(all_jobs, key=lambda job: job.created_date, reverse=True)[:50]
        
        return [CrawlJobResponse.from_crawl_job(job) for job in sorted_jobs]
    except Exception as e:
        logger.error(f"API: Error retrieving all jobs: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve all jobs: {e}")
    finally:
        if db and hasattr(db, 'Session'):
            db.Session.remove()

@app.get("/api/jobs/is_paused", response_model=Dict[str, bool])
async def is_jobs_paused_endpoint():
    """
    Checks if global job processing is currently paused.
    This endpoint is primarily consumed by the monitoring dashboard and does not require authentication.
    """
    logger.info("API: Received request to check if jobs are paused (public endpoint).")
    if not redis_client:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis is not available.")
    
    try:
        is_paused = await redis_client.get("processing_paused")
        return {"is_paused": is_paused is not None and is_paused.decode('utf-8').lower() == 'true'}
    except Exception as e:
        logger.error(f"API: Error checking if jobs are paused: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to check pause status: {e}")


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
async def get_dead_letters(current_user: Annotated[User, Depends(get_current_user)]): # Protected endpoint
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
async def clear_dead_letters(current_user: Annotated[User, Depends(get_current_user)]): # Protected endpoint
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
async def reprocess_dead_letters(current_user: Annotated[User, Depends(get_current_user)]): # Protected endpoint
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
