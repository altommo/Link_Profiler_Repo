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
    sys.sys.path.insert(0, project_root)
    print(f"PROJECT_ROOT (discovered and added to sys.path): {project_root}")
else:
    print(f"PROJECT_ROOT (discovery failed or already in sys.path): {project_root}")

# --- End Robust Project Root Discovery ---


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, WebSocket, WebSocketDisconnect, Depends, status, Query
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
    JOBS_CREATED_TOTAL, JOBS_IN_PROGRESS, JOBS_PENDING, JOBS_COMPLETED_SUCCESS_TOTAL, JOBS_FAILED_TOTAL
)
from Link_Profiler.api.queue_endpoints import submit_crawl_to_queue, QueueCrawlRequest, get_coordinator
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
        
        # Initialize and start JobCoordinator background tasks
        # This call will now handle its own __aenter__ and task creation
        from Link_Profiler.api.queue_endpoints import get_coordinator as get_job_coordinator_instance
        try:
            await get_job_coordinator_instance()
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
    description="API for discovering backlinks and generating link profiles.",
    version="0.1.0",
    lifespan=lifespan # Register the lifespan context manager
)

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
    TopicClusteringRequest, Token, UserCreate, UserResponse,
    JobStatusResponse, QueueStatsResponse, CrawlerHealthResponse # New: Import queue response models
)


# --- API Endpoints ---

# Import the new routers
from Link_Profiler.api.auth import auth_router
from Link_Profiler.api.users import users_router
from Link_Profiler.api.crawl_audit import crawl_audit_router
from Link_Profiler.api.analytics import analytics_router
from Link_Profiler.api.competitive_analysis import competitive_analysis_router
from Link_Profiler.api.link_building import link_building_router
from Link_Profiler.api.ai import ai_router
from Link_Profiler.api.reports import reports_router
from Link_Profiler.api.monitoring_debug import monitoring_debug_router
from Link_Profiler.api.websocket import websocket_router
from Link_Profiler.api.queue import queue_router # New: Import the queue router

# Register the routers with the main app
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(crawl_audit_router)
app.include_router(analytics_router)
app.include_router(competitive_analysis_router)
app.include_router(link_building_router)
app.include_router(ai_router)
app.include_router(reports_router)
app.include_router(monitoring_debug_router)
app.include_router(websocket_router)
app.include_router(queue_router)
