"""
API Endpoints for the Link Profiler System
File: Link_Profiler/main.py (formerly Link_Profiler/api/main.py)
"""

import os
import sys
import time
import logging # Import logging early
from typing import List, Optional, Dict, Any, Union, Annotated # Import Optional here
import inspect # Import inspect for signature validation

# --- Robust Project Root Discovery ---
# Assuming this file is at Link_Profiler/Link_Profiler/main.py
# The project root (containing setup.py) is one level up from the 'Link_Profiler' package directory.
# So, it's os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if project_root and project_root not in sys.path:
    sys.path.insert(0, project_root) # Corrected: sys.sys.path.insert -> sys.path.insert
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

# New: Subdomain configuration for UI routing
CUSTOMER_SUBDOMAIN = config_loader.get("subdomains.customer", "customer")
MISSION_CONTROL_SUBDOMAIN = config_loader.get("subdomains.mission_control", "monitor") # Corrected default to "monitor"

# Added: Debug logging for subdomain configuration
logger.info(f"Subdomain configuration - Customer: '{CUSTOMER_SUBDOMAIN}', Mission Control: '{MISSION_CONTROL_SUBDOMAIN}'")
logger.info(f"Expected URLs - Customer: {CUSTOMER_SUBDOMAIN}.yspanel.com, Mission Control: {MISSION_CONTROL_SUBDOMAIN}.yspanel.com")


# Initialize Redis connection pool and client (moved up to ensure it's defined before lifespan)
import redis.asyncio as redis
redis_pool = redis.ConnectionPool.from_url(REDIS_URL)
redis_client: Optional[redis.Redis] = redis.Redis(connection_pool=redis_pool) # Make redis_client optional

# New: Initialize SessionManager
from Link_Profiler.utils.session_manager import session_manager # Use the singleton instance

# Now import other FastAPI and application modules
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, WebSocket, WebSocketDisconnect, Depends, status, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse # Import RedirectResponse
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
# Removed: from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm # Added missing imports
# These are now imported from Link_Profiler.api.dependencies or handled by FastAPI directly

# New: Import SubdomainRouterMiddleware
from Link_Profiler.middleware.subdomain_router import SubdomainRouterMiddleware

# New: Import DistributedResilienceManager (Initialize before APIQuotaManager)
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import the class only
# Instantiate the singleton after redis_client is available
distributed_resilience_manager = DistributedResilienceManager(redis_client=redis_client)

# New: Import API Quota Manager (Initialize after DistributedResilienceManager)
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import the class only

# New: Import SmartAPIRouterService (Initialize after APIQuotaManager and all clients)
from Link_Profiler.services.smart_api_router_service import SmartAPIRouterService # Removed smart_api_router_service from import
# Import both class and singleton

# New: Import API Clients (Instantiate all of them)
from Link_Profiler.clients.google_search_console_client import GoogleSearchConsoleClient # Renamed GSCClient to GoogleSearchConsoleClient
from Link_Profiler.clients.google_pagespeed_client import PageSpeedClient
from Link_Profiler.clients.google_trends_client import GoogleTrendsClient
from Link_Profiler.clients.whois_client import WHOISClient
from Link_Profiler.clients.dns_client import DNSClient
from Link_Profiler.clients.reddit_client import RedditClient
from Link_Profiler.clients.youtube_client import YouTubeClient
from Link_Profiler.clients.news_api_client import NewsAPIClient
from Link_Profiler.clients.serpstack_client import SerpstackClient # Import SerpstackClient
from Link_Profiler.clients.valueserp_client import ValueserpClient # Import ValueserpClient
from Link_Profiler.clients.webscraping_ai_client import WebscrapingAIClient # Import WebscrapingAIClient
from Link_Profiler.clients.hunter_io_client import HunterIOClient # Import HunterIOClient
from Link_Profiler.clients.builtwith_client import BuiltWithClient # Import BuiltWithClient
from Link_Profiler.clients.security_trails_client import SecurityTrailsClient # Import SecurityTrailsClient


# Initialize API Quota Manager (requires resilience_manager)
api_quota_manager = APIQuotaManager(config_loader._config_data, resilience_manager=distributed_resilience_manager, redis_client=redis_client)

# Initialize all individual API clients, passing all required dependencies
gsc_client_instance = GoogleSearchConsoleClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
pagespeed_client_instance = PageSpeedClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
google_trends_client_instance = GoogleTrendsClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
whois_client_instance = WHOISClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
dns_client_instance = DNSClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
reddit_client_instance = RedditClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
youtube_client_instance = YouTubeClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
news_api_client_instance = NewsAPIClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
serpstack_client_instance = SerpstackClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
valueserp_client_instance = ValueserpClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
webscraping_ai_client_instance = WebscrapingAIClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
hunter_io_client_instance = HunterIOClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
builtwith_client_instance = BuiltWithClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)
security_trails_client_instance = SecurityTrailsClient(session_manager=session_manager, resilience_manager=distributed_resilience_manager, api_quota_manager=api_quota_manager)


# Initialize SmartAPIRouterService (requires all clients)
smart_api_router_service = SmartAPIRouterService(
    config=config_loader._config_data,
    session_manager=session_manager,
    resilience_manager=distributed_resilience_manager,
    api_quota_manager=api_quota_manager,
    redis_client=redis_client, # Pass redis_client
    google_search_console_client=gsc_client_instance,
    google_pagespeed_client=pagespeed_client_instance,
    google_trends_client=google_trends_client_instance,
    whois_client=whois_client_instance,
    dns_client=dns_client_instance,
    reddit_client=reddit_client_instance,
    youtube_client=youtube_client_instance,
    news_api_client=news_api_client_instance,
    serpstack_client=serpstack_client_instance,
    valueserp_client=valueserp_client_instance,
    webscraping_ai_client=webscraping_ai_client_instance,
    hunter_io_client=hunter_io_client_instance,
    builtwith_client=builtwith_client_instance,
    security_trails_client=security_trails_client_instance
)


# Now import other services that will use the SmartAPIRouterService
from Link_Profiler.services.crawl_service import CrawlService
from Link_Profiler.services.domain_service import DomainService
from Link_Profiler.services.backlink_service import BacklinkService
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService
from Link_Profiler.services.expired_domain_finder_service import ExpiredDomainFinderService
from Link_Profiler.services.serp_service import SERPService
from Link_Profiler.services.keyword_service import KeywordService
from Link_Profiler.services.link_health_service import LinkHealthService
from Link_Profiler.services.ai_service import AIService
from Link_Profiler.services.alert_service import AlertService # Import AlertService class only
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
from Link_Profiler.core.models import CrawlConfig, CrawlJob, LinkProfile, Backlink, serialize_model, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion, LinkIntersectResult, CompetitiveKeywordAnalysisResult, AlertRule, AlertSeverity, AlertChannel, User, ContentGapAnalysisResult, DomainHistory, LinkProspect, OutreachCampaign, OutreachEvent, ReportJob, SatellitePerformanceLog # New: Import SatellitePerformanceLog
from Link_Profiler.monitoring.prometheus_metrics import (
    API_REQUESTS_TOTAL, API_REQUEST_DURATION_SECONDS, get_metrics_text, # Re-added for middleware
    JOBS_CREATED_TOTAL, JOBS_IN_PROGRESS, JOBS_PENDING, JOBS_COMPLETED_SUCCESS_TOTAL, JOBS_FAILED_TOTAL
)
# Removed submit_crawl_to_queue, get_coordinator, set_coordinator_dependencies from job_submission_service
# as they are now in queue_endpoints.py
from Link_Profiler.queue_system.job_coordinator import get_coordinator # Import canonical get_coordinator
from Link_Profiler.api.monitoring_debug import health_check_internal, _get_aggregated_stats_for_api, _get_satellites_data_internal, verify_admin_access # Import monitoring debug functions

# New: Import WebCrawler and SmartCrawlQueue
from Link_Profiler.crawlers.web_crawler import EnhancedWebCrawler # Changed to EnhancedWebCrawler
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue, Priority

# New: Import Dashboard Alert Service
from Link_Profiler.services.dashboard_alert_service import DashboardAlertService, dashboard_alert_service # Import both class and singleton

# New: Import Mission Control Service
from Link_Profiler.services import mission_control_service as mission_control_module
from Link_Profiler.services.mission_control_service import MissionControlService

# Import api_cache singleton
from Link_Profiler.utils.api_cache import api_cache

# Import schemas
from Link_Profiler.api.schemas import (
    UserCreate, UserResponse, Token, CrawlJobResponse, LinkProfileResponse, DomainResponse, 
    ReportJobResponse, QueueStatsResponse, SERPResultResponse, KeywordSuggestionResponse, 
    LinkIntersectResponse, CompetitiveKeywordAnalysisResponse, AlertRuleResponse, # Corrected import name
    ContentGapAnalysisResultResponse, LinkProspectResponse, OutreachCampaignResponse, 
    OutreachEventResponse, SEOMetricsResponse, QueueCrawlRequest, SystemConfigResponse, SystemConfigUpdate # Added QueueCrawlRequest, SystemConfig schemas
)

# Import API Routers
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
# New: Import customer_router
from Link_Profiler.api.customer_routes import customer_router
# New: Import admin_routes
from Link_Profiler.api.admin_routes import admin_router # Import the new admin router

# New: Import authentication dependencies
from Link_Profiler.api.dependencies import get_current_user, get_current_admin_user, get_current_customer_user # Import specific dependency functions
from fastapi.security import OAuth2PasswordRequestForm # Only import this specific class needed for /token endpoint

# --- RESTORED: Import CORSMiddleware ---
from fastapi.middleware.cors import CORSMiddleware
# --- END RESTORED ---


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
# DomainService now takes SmartAPIRouterService
domain_service_instance = DomainService(
    db=db, # DomainService needs db
    smart_api_router_service=smart_api_router_service, # Pass the new router service
    session_manager=session_manager, # Pass session_manager
    resilience_manager=distributed_resilience_manager, # Pass resilience_manager
    api_quota_manager=api_quota_manager, # Pass api_quota_manager
    redis_client=redis_client # Pass redis_client
)

# Initialize BacklinkService based on priority: GSC > OpenLinkProfiler > Real (paid) > Simulated
# BacklinkService constructor signature: (session_manager, resilience_manager, api_client=None, redis_client=None, cache_ttl=3600, database=None)
backlink_service_instance = BacklinkService(
    session_manager=session_manager,
    resilience_manager=distributed_resilience_manager,
    redis_client=redis_client, # Already passing redis_client
    cache_ttl=API_CACHE_TTL,
    database=db # BacklinkService needs db as database parameter
)

# New: Initialize SERPService and SERPCrawler
serp_crawler_instance = None
if config_loader.get("serp_crawler.playwright.enabled"):
    logger.info("Initialising Playwright SERPCrawler.")
    serp_crawler_instance = SERPCrawler(
        headless=config_loader.get("serp_crawler.playwright.headless"),
        browser_type=config_loader.get("serp_crawler.playwright.browser_type"),
        session_manager=session_manager,
        resilience_manager=distributed_resilience_manager
    )
# SERPService constructor signature: (api_client=None, serp_crawler=None, pagespeed_client=None, redis_client=None, cache_ttl=3600, session_manager=None, resilience_manager=None, api_quota_manager=None, api_routing_service=None)
serp_service_instance = SERPService(
    serp_crawler=serp_crawler_instance,
    pagespeed_client=pagespeed_client_instance,
    redis_client=redis_client, # Already passing redis_client
    cache_ttl=API_CACHE_TTL,
    session_manager=session_manager,
    resilience_manager=distributed_resilience_manager,
    api_quota_manager=api_quota_manager,
    api_routing_service=smart_api_router_service # Pass the router service as api_routing_service
)

# New: Initialize KeywordService and KeywordScraper
keyword_scraper_instance = None
if config_loader.get("keyword_scraper.enabled"): # Assuming a config for keyword_scraper.enabled
    logger.info("Initialising KeywordScraper.")
    keyword_scraper_instance = KeywordScraper(
        session_manager=session_manager,
        resilience_manager=distributed_resilience_manager
    )
# KeywordService constructor signature: (database=None, api_client=None, keyword_scraper=None, google_trends_client=None, session_manager=None, resilience_manager=None)
keyword_service_instance = KeywordService(
    database=db,
    keyword_scraper=keyword_scraper_instance,
    google_trends_client=google_trends_client_instance,
    session_manager=session_manager,
    resilience_manager=distributed_resilience_manager,
    redis_client=redis_client # Pass redis_client
)

# New: Initialize LinkHealthService
link_health_service_instance = LinkHealthService(db)

# New: Initialize TechnicalAuditor
technical_auditor_instance = TechnicalAuditor(
    lighthouse_path=config_loader.get("technical_auditor.lighthouse_path") # Allow custom path for Lighthouse CLI
)

# New: Initialize AI Service
ai_service_instance = AIService(
    database=db,
    session_manager=session_manager,
    resilience_manager=distributed_resilience_manager,
    redis_client=redis_client # Pass redis_client
)

# New: Initialize Report Service
report_service_instance = ReportService(db)

# New: Initialize Competitive Analysis Service
competitive_analysis_service_instance = CompetitiveAnalysisService(db, backlink_service_instance, serp_service_instance)

# New: Initialize Social Media Service and Crawler
social_media_crawler_instance = None
if config_loader.get("social_media_crawler.enabled"):
    logger.info("Initialising SocialMediaCrawler.")
    social_media_crawler_instance = SocialMediaCrawler(
        session_manager=session_manager,
        resilience_manager=distributed_resilience_manager
    )
# SocialMediaService constructor signature: (database, session_manager, social_media_crawler=None, reddit_client=None, youtube_client=None, news_api_client=None, resilience_manager=None)
social_media_service_instance = SocialMediaService(
    database=db,
    session_manager=session_manager,
    social_media_crawler=social_media_crawler_instance,
    reddit_client=reddit_client_instance,
    youtube_client=youtube_client_instance,
    news_api_client=news_api_client_instance,
    resilience_manager=distributed_resilience_manager,
    redis_client=redis_client # Pass redis_client
)

# New: Initialize Web3 Service
# Web3Service constructor signature: (database, redis_client=None, cache_ttl=3600)
web3_service_instance = Web3Service(
    database=db,
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
smart_crawl_queue = SmartCrawlQueue(redis_client=redis_client, config_loader=config_loader) # Pass redis_client and config_loader here

# Initialize DashboardAlertService
dashboard_alert_service = DashboardAlertService(
    db=db,
    redis_client=redis_client, # Pass the redis_client singleton
    api_quota_manager=api_quota_manager # Pass the api_quota_manager singleton
)

# Initialize MissionControlService and set the global singleton
mission_control_service = MissionControlService(
    redis_client=redis_client,  # Pass the redis_client singleton
    smart_crawl_queue=smart_crawl_queue,
    api_quota_manager=api_quota_manager,
    dashboard_alert_service=dashboard_alert_service
)

# Update the global singleton in the module
mission_control_module.mission_control_service = mission_control_service

# Create WebCrawler instance, passing the SmartCrawlQueue
main_web_crawler = EnhancedWebCrawler(config=main_crawl_config, crawl_queue=smart_crawl_queue, ai_service=ai_service_instance, playwright_browser=playwright_browser_instance, resilience_manager=distributed_resilience_manager, session_manager=session_manager)
# --- End New Instantiation ---

# Initialize AlertService instance after its dependencies are available
alert_service_instance = AlertService(db=db, connection_manager=connection_manager, redis_client=redis_client, config_loader=config_loader)

async def validate_redis_dependencies(redis_client: redis.Redis, services_to_validate: List[Any]) -> bool:
    """
    Validates that the Redis client is connected and that all specified services
    accept a 'redis_client' parameter in their constructor.
    """
    logger.info("Starting Redis and service dependency validation...")
    
    # 1. Test Redis connection
    try:
        await redis_client.ping()
        logger.info("✅ Redis connection validated.")
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Redis connection failed: {e}")
        return False
    
    # 2. Validate service constructors
    all_valid = True
    for service_class in services_to_validate:
        try:
            # Get the __init__ signature
            sig = inspect.signature(service_class.__init__)
            
            # Check if 'redis_client' is a parameter
            if 'redis_client' not in sig.parameters:
                logger.critical(f"❌ CRITICAL: {service_class.__name__}.__init__ does NOT accept 'redis_client' parameter.")
                all_valid = False
            else:
                # Optionally, check its type hint if desired, but just presence is enough for this check
                param = sig.parameters['redis_client']
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    logger.warning(f"⚠️ WARNING: {service_class.__name__}.__init__ 'redis_client' parameter is positional-only. Consider making it keyword-only or mixed.")
                logger.info(f"✅ {service_class.__name__}.__init__ 'redis_client' parameter validated.")
        except Exception as e:
            logger.critical(f"❌ CRITICAL: Error inspecting {service_class.__name__}.__init__: {e}", exc_info=True) # Added exc_info
            all_valid = False
            
    if not all_valid:
        logger.critical("❌ CRITICAL: One or more Redis service dependencies failed validation. Application may not function correctly.")
    else:
        logger.info("✅ All Redis service dependencies validated successfully.")
        
    return all_valid


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for managing the lifespan of the FastAPI application.
    Ensures resources like aiohttp sessions are properly opened and closed.
    """
    context_managers = [
        session_manager,
        distributed_resilience_manager, # Add resilience manager to lifespan
        api_quota_manager, # Add API quota manager to lifespan
        smart_api_router_service, # Add smart API router service to lifespan
        # Individual API clients are managed by SmartAPIRouterService, no need to add them here
        auth_service_instance,
        connection_manager,
        dashboard_alert_service, # Add DashboardAlertService to lifespan
        mission_control_service, # Add MissionControlService to lifespan
        backlink_service_instance,
        serp_service_instance,
        keyword_service_instance,
        link_health_service_instance,
        technical_auditor_instance,
        alert_service_instance, # Add alert_service_instance to lifespan
        report_service_instance,
        competitive_analysis_service_instance,
        social_media_service_instance,
        web3_service_instance,
        link_building_service_instance,
        main_web_crawler,
        # DomainService is now managed by smart_api_router_service, no need to add it here directly
        domain_service_instance # DomainService still needs to be entered for its own internal setup
    ]

    if clickhouse_loader_instance:
        context_managers.append(clickhouse_loader_instance)
    if serp_crawler_instance:
        context_managers.append(serp_crawler_instance)
    if keyword_scraper_instance:
        context_managers.append(keyword_scraper_instance)
    if social_media_crawler_instance:
        context_managers.append(social_media_crawler_instance)

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
        
        crawl_service_for_lifespan.playwright_browser = playwright_browser_instance
        logger.info("Global Playwright browser launched and assigned to CrawlService.")
    else:
        logger.info("Global Playwright browser for WebCrawler is disabled by configuration.")


    entered_contexts = []
    try:
        # Perform Redis dependency validation early
        if not await validate_redis_dependencies(redis_client, [
            DistributedResilienceManager, SmartAPIRouterService, APIQuotaManager,
            SmartCrawlQueue, DashboardAlertService, MissionControlService, AlertService,
            DomainService, BacklinkService, SERPService, KeywordService,
            AIService, SocialMediaService, Web3Service,
            # Add any other services that directly accept redis_client
        ]):
            logger.critical("Critical Redis dependencies not met. Aborting application startup.")
            raise RuntimeError("Critical Redis dependencies not met. Aborting application startup.")

        for i, cm in enumerate(context_managers):
            logger.info(f"Application startup: Attempting to enter {cm.__class__.__name__} context (Index: {i})...")
            try:
                entered_contexts.append(await cm.__aenter__())
                logger.info(f"Application startup: Successfully entered {cm.__class__.__name__} context (Index: {i}).")
            except Exception as e:
                logger.critical(f"Application startup: FAILED to enter {cm.__class__.__name__} context (Index: {i}): {e}", exc_info=True)
                raise # Re-raise to ensure lifespan exits

        logger.info("Application startup: All context managers entered successfully.")
        logger.info("Application startup: Pinging Redis.")
        if redis_client:
            try:
                await redis_client.ping()
                logger.info("Redis connection successful.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
        else:
            logger.warning("Redis client not initialized. Skipping Redis ping.")
        
        # Removed set_coordinator_dependencies as it's now handled by get_coordinator in queue_system
        # Removed explicit asyncio.create_task calls for JobCoordinator as they are handled by get_coordinator in queue_system

        try:
            await get_coordinator() # This will initialize the JobCoordinator and start its tasks
            logger.info("JobCoordinator instance successfully retrieved/initialized (background tasks are managed internally).")
        except Exception as e:
            logger.error(f"Failed to retrieve/initialize JobCoordinator during lifespan startup: {e}", exc_info=True)

        asyncio.create_task(alert_service_instance.refresh_rules())

        # --- NEW: Create default admin user if not exists ---
        default_admin_username = "monitor_user"
        default_admin_password = "monitor_password" # This should ideally be loaded from a secure config/env var
        
        existing_admin_user = db.get_user_by_username(default_admin_username)
        if not existing_admin_user:
            logger.info(f"Default admin user '{default_admin_username}' not found. Creating...")
            try:
                await auth_service_instance.register_user(
                    username=default_admin_username,
                    email="admin@linkprofiler.com", # Use a default admin email
                    password=default_admin_password,
                    is_admin=True,
                    role="admin"
                )
                logger.info(f"Default admin user '{default_admin_username}' created successfully.")
            except Exception as e:
                logger.error(f"Failed to create default admin user '{default_admin_username}': {e}", exc_info=True)
        else:
            logger.info(f"Default admin user '{default_admin_username}' already exists.")
        # --- END NEW ---

        yield

    finally:
        for cm in reversed(entered_contexts):
            logger.info(f"Application shutdown: Exiting {cm.__class__.__name__} context.")
            await cm.__aexit__(None, None, None)
        
        if playwright_browser_instance:
            logger.info("Application shutdown: Closing global Playwright browser.")
            await playwright_browser_instance.close()
            if 'playwright_instance' in locals() and playwright_instance:
                await playwright_instance.stop()

        if redis_pool:
            logger.info("Application shutdown: Closing Redis connection pool.")
            await redis_pool.disconnect()


app = FastAPI(
    title="Link Profiler API",
    description="API for comprehensive link profiling, SEO analysis, and domain intelligence.",
    version=config_loader.get("system.current_code_version", "0.1.0"),
    lifespan=lifespan
)

# Add the subdomain router middleware BEFORE other middleware or routes
app.add_middleware(
    SubdomainRouterMiddleware,
    customer_subdomain=CUSTOMER_SUBDOMAIN,
    mission_control_subdomain=MISSION_CONTROL_SUBDOMAIN
)


# --- RESTORED: CORS Middleware ---
origins = [
    "https://monitor.yspanel.com",
    "https://api.yspanel.com",
    "https://linkprofiler.yspanel.com",
    "https://yspanel.com",
    "https://www.yspanel.com",
    "http://localhost:8001",
    "http://localhost:8000",
    "null" # For local development with file:// or some dev servers
]

from fastapi.middleware.cors import CORSMiddleware # Import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)
# --- END RESTORED ---


# Mount the mission-control-dashboard static assets
app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(project_root, "Link_Profiler", "static", "mission-control-dashboard", "dist", "assets")),
    name="mission-control-dashboard-assets",
)

# Mount the customer-dashboard static assets
app.mount(
    "/customer-dashboard/assets",
    StaticFiles(directory=os.path.join(project_root, "Link_Profiler", "static", "customer-dashboard", "dist", "assets")),
    name="customer-dashboard-assets",
)


# Removed: origins and app.add_middleware(CORSMiddleware, ...) block from here


# Removed: oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
# Removed: async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
# Removed: async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:


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
        data={"sub": user.username, "role": user.role, "organization_id": user.organization_id}, # Pass role and org_id
        expires_delta=access_token_expires
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
async def read_users_me(current_user: User = Depends(get_current_user)): # Use imported get_current_user
    return UserResponse.from_user(current_user)

# --- New Admin API Endpoints for Mission Control Dashboard ---

# Moved to admin_routes.py
# @app.get("/admin/users", response_model=List[UserResponse])
# async def get_all_users(current_user: User = Depends(get_current_admin_user)):
#     """Retrieve all users. Requires admin access."""
#     logger.info(f"Admin user {current_user.username} requesting all users.")
#     users = db.get_all_users()
#     return [UserResponse.from_user(user) for user in users]

# Moved to admin_routes.py
# @app.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
# async def create_new_user(user_create: UserCreate, current_user: User = Depends(get_current_admin_user)):
#     """Create a new user. Requires admin access."""
#     logger.info(f"Admin user {current_user.username} creating new user: {user_create.username}.")
#     existing_user = db.get_user_by_username(user_create.username)
#     if existing_user:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
#     existing_email = db.get_user_by_email(user_create.email)
#     if existing_email:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
#     new_user = await auth_service_instance.register_user(
#         username=user_create.username,
#         email=user_create.email,
#         password=user_create.password,
#         is_admin=user_create.is_admin # Allow admin to set admin status
#     )
#     return UserResponse.from_user(new_user)

# Moved to admin_routes.py
# @app.put("/admin/users/{user_id}", response_model=UserResponse)
# async def update_existing_user(user_id: str, user_update: UserCreate, current_user: User = Depends(get_current_admin_user)):
#     """Update an existing user's details. Requires admin access."""
#     logger.info(f"Admin user {current_user.username} updating user ID: {user_id}.")
#     user = db.get_user_by_id(user_id)
#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
#     # Update fields
#     user.username = user_update.username
#     user.email = user_update.email
#     user.is_admin = user_update.is_admin
    
#     # Handle password change if provided
#     if user_update.password:
#         user.hashed_password = auth_service_instance.get_password_hash(user_update.password)
    
#     updated_user = db.update_user(user)
#     return UserResponse.from_user(updated_user) # Corrected: Changed new_user to updated_user

# Moved to admin_routes.py
# @app.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_existing_user(user_id: str, current_user: User = Depends(get_current_admin_user)):
#     """Delete a user. Requires admin access."""
#     logger.info(f"Admin user {current_user.username} deleting user ID: {user_id}.")
#     if current_user.user_id == user_id:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account.")
    
#     success = db.delete_user(user_id)
#     if not success:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
#     return Response(status_code=status.HTTP_204_NO_CONTENT)

# Moved to admin_routes.py
# @app.get("/admin/config", response_model=SystemConfigResponse)
# async def get_system_config(current_user: User = Depends(get_current_admin_user)):
#     """Retrieve current system configuration. Requires admin access."""
#     logger.info(f"Admin user {current_user.username} requesting system config.")
#     # For simplicity, return a subset of config that might be editable via UI
#     # In a real app, you'd have a dedicated config service/model
#     return SystemConfigResponse(
#         logging_level=config_loader.get("logging.level"),
#         api_cache_enabled=config_loader.get("api_cache.enabled"),
#         api_cache_ttl=config_loader.get("api_cache.ttl"),
#         crawler_max_depth=config_loader.get("crawler.max_depth"),
#         crawler_render_javascript=config_loader.get("crawler.render_javascript"),
#         # Add other relevant config items here
#     )

# Moved to admin_routes.py
# @app.put("/admin/config", response_model=SystemConfigResponse)
# async def update_system_config(config_update: SystemConfigUpdate, current_user: User = Depends(get_current_admin_user)):
#     """Update system configuration. Requires admin access."""
#     logger.info(f"Admin user {current_user.username} updating system config.")
#     # Apply updates to config_loader (which should persist them if configured)
#     if config_update.logging_level:
#         config_loader.set("logging.level", config_update.logging_level)
#         LoggingConfig.setup_logging(level=config_update.logging_level) # Re-apply logging config
#     if config_update.api_cache_enabled is not None:
#         config_loader.set("api_cache.enabled", config_update.api_cache_enabled)
#     if config_update.api_cache_ttl is not None:
#         config_loader.set("api_cache.ttl", config_update.api_cache_ttl)
#     if config_update.crawler_max_depth is not None:
#         config_loader.set("crawler.max_depth", config_update.crawler_max_depth)
#     if config_update.crawler_render_javascript is not None:
#         config_loader.set("crawler.render_javascript", config_update.crawler_render_javascript)
    
#     # Reload config to ensure changes are reflected (if config_loader supports it)
#     config_loader.reload_config() # Assuming this method exists and persists changes
    
#     return SystemConfigResponse(
#         logging_level=config_loader.get("logging.level"),
#         api_cache_enabled=config_loader.get("api_cache.enabled"),
#         api_cache_ttl=config_loader.get("api_cache.ttl"),
#         crawler_max_depth=config_loader.get("crawler.max_depth"),
#         crawler_render_javascript=config_loader.get("crawler.render_javascript"),
#     )

# Moved to admin_routes.py
# @app.get("/admin/audit_logs", response_model=List[Dict[str, Any]])
# async def get_audit_logs(
#     limit: int = Query(100, ge=1, le=1000),
#     offset: int = Query(0, ge=0),
#     current_user: User = Depends(get_current_admin_user)
# ):
#     """Retrieve recent audit logs. Requires admin access."""
#     logger.info(f"Admin user {current_user.username} requesting audit logs (limit={limit}, offset={offset}).")
#     # This is a placeholder. In a real system, you'd query a dedicated audit log database/service.
#     # For now, simulate some logs.
#     simulated_logs = [
#         {"timestamp": datetime.now().isoformat(), "user": "admin", "action": "LOGIN_SUCCESS", "details": {"ip": "192.168.1.1"}},
#         {"timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(), "user": "admin", "action": "UPDATE_CONFIG", "details": {"key": "logging.level", "old": "INFO", "new": "DEBUG"}},
#         {"timestamp": (datetime.now() - timedelta(hours=1)).isoformat(), "user": "user1", "action": "SUBMIT_CRAWL_JOB", "details": {"job_id": "abc-123", "target": "example.com"}},
#     ]
#     return simulated_logs[offset:offset+limit]

# Moved to admin_routes.py
# @app.post("/admin/api_keys/{api_name}/update", response_model=Dict[str, str])
# async def update_api_key(api_name: str, new_key: str, current_user: User = Depends(get_current_admin_user)):
#     """Update an external API key. Requires admin access."""
#     logger.info(f"Admin user {current_user.username} updating API key for {api_name}.")
#     # This is a placeholder. You would update this in a secure config store.
#     # For now, directly update config_loader (not persistent across restarts unless configured)
#     current_config = config_loader.get("external_apis", {})
#     if api_name in current_config:
#         current_config[api_name]["api_key"] = new_key
#         config_loader.set("external_apis", current_config) # This might not persist depending on config_loader impl
#         config_loader.reload_config() # Attempt to persist/reload
#         return {"message": f"API key for {api_name} updated successfully."}
#     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API {api_name} not found in configuration.")

# --- Re-exposed Monitoring Endpoints from dashboard_server.py ---
# These endpoints are now part of the main API for Mission Control to consume.

# Moved to admin_routes.py
# @app.get("/api/monitoring/health")
# async def health_check_main_endpoint():
#     """
#     Performs a comprehensive health check of the API and its dependencies.
#     """
#     health_status = await health_check_internal()
#     status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
#     return Response(content=json.dumps(health_status, indent=2), media_type="application/json", status_code=status_code)

# Moved to admin_routes.py
# @app.get("/api/monitoring/stats")
# async def get_api_stats_main_endpoint(current_user: User = Depends(get_current_admin_user)):
#     """
#     Retrieves aggregated statistics for the Link Profiler system.
#     Requires admin authentication.
#     """
#     logger.info(f"Main API: Received request for aggregated stats by admin: {current_user.username}.")
#     return await _get_aggregated_stats_for_api()

# Moved to admin_routes.py
# @app.get("/api/monitoring/satellites")
# async def get_satellites_main_endpoint(current_user: User = Depends(get_current_admin_user)):
#     """
#     Retrieves detailed health information for all satellite crawlers.
#     Requires admin authentication.
#     """
#     logger.info(f"Main API: Received request for detailed satellite health by admin: {current_user.username}.")
#     return await _get_satellites_data_internal()

# Moved to admin_routes.py
# @app.get("/api/monitoring/jobs")
# async def get_jobs_main_endpoint(
#     status_filter: Optional[str] = Query(None, description="Filter jobs by status (e.g., 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED')."),
#     current_user: User = Depends(get_current_admin_user)
# ):
#     """
#     Retrieves a list of crawl jobs, optionally filtered by status.
#     Requires admin authentication.
#     """
#     logger.info(f"Main API: Received request for jobs by admin: {current_user.username} (status_filter: {status_filter}).")
    
#     try:
#         all_jobs = db.get_all_crawl_jobs()
        
#         if status_filter:
#             try:
#                 filter_status = CrawlStatus[status_filter.upper()]
#                 all_jobs = [job for job in all_jobs if job.status == filter_status]
#             except KeyError:
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status_filter: {status_filter}. Must be one of {list(CrawlStatus.__members__.keys())}.")
        
#         # Sort by created date, newest first
#         sorted_jobs = sorted(all_jobs, key=lambda job: job.created_at, reverse=True) # Corrected from job.created_date
        
#         # Convert CrawlJob objects to their dictionary representation for JSON serialization
#         return [job.to_dict() for job in sorted_jobs]
#     except Exception as e:
#         logger.error(f"Main API: Error retrieving jobs: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve jobs: {e}")
#     finally:
#         if db and hasattr(db, 'Session'):
#             db.Session.remove()

# Moved to admin_routes.py
# @app.post("/api/monitoring/jobs/{job_id}/cancel")
# async def cancel_job_main_endpoint(job_id: str, current_user: User = Depends(get_current_admin_user)):
#     """
#     Cancels a specific crawl job.
#     Requires admin authentication.
#     """
#     logger.info(f"Admin user {current_user.username} requesting to cancel job {job_id}.")
#     try:
#         coordinator = await get_coordinator()
#         success = await coordinator.cancel_job(job_id)
#         if success:
#             return {"message": f"Job {job_id} cancelled successfully."}
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found or could not be cancelled.")
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel job {job_id}: {e}")

# Moved to admin_routes.py
# @app.post("/api/monitoring/jobs/pause_all")
# async def pause_all_jobs_main_endpoint(current_user: User = Depends(get_current_admin_user)):
#     """
#     Pauses all new job processing.
#     Requires admin authentication.
#     """
#     logger.info(f"Admin user {current_user.username} requesting to pause all jobs.")
#     try:
#         coordinator = await get_coordinator()
#         await coordinator.pause_job_processing()
#         return {"message": "All new job processing paused."}
#     except Exception as e:
#         logger.error(f"Error pausing all jobs: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to pause all jobs: {e}")

# Moved to admin_routes.py
# @app.post("/api/monitoring/jobs/resume_all")
# async def resume_all_jobs_main_endpoint(current_user: User = Depends(get_current_admin_user)):
#     """
#     Resumes all job processing.
#     Requires admin authentication.
#     """
#     logger.info(f"Admin user {current_user.username} requesting to resume all jobs.")
#     try:
#         coordinator = await get_coordinator()
#         await coordinator.resume_job_processing()
#         return {"message": "All job processing resumed."}
#     except Exception as e:
#         logger.error(f"Error resuming all jobs: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to resume all jobs: {e}")

# Moved to admin_routes.py
# @app.post("/api/monitoring/satellites/control/{crawler_id}/{command}")
# async def control_single_satellite_main_endpoint(crawler_id: str, command: str, current_user: User = Depends(get_current_admin_user)):
#     """
#     Sends a control command to a specific satellite crawler.
#     Commands: PAUSE, RESUME, SHUTDOWN, RESTART.
#     Requires admin authentication.
#     """
#     logger.info(f"Admin user {current_user.username} requesting command '{command}' for satellite '{crawler_id}'.")
#     try:
#         coordinator = await get_coordinator()
#         response = await coordinator.send_control_command(crawler_id, command)
#         return response
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Main API: Error controlling satellite {crawler_id}: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to control satellite {crawler_id}: {e}")

# Moved to admin_routes.py
# @app.post("/api/monitoring/satellites/control/all/{command}")
# async def control_all_satellites_main_endpoint(command: str, current_user: User = Depends(get_current_admin_user)):
#     """
#     Sends a control command to all active satellite crawlers.
#     Commands: PAUSE, RESUME, SHUTDOWN, RESTART.
#     Requires admin authentication.
#     """
#     logger.info(f"Main API: Received command '{command}' for all satellites by admin: {current_user.username}.")
#     try:
#         coordinator = await get_coordinator()
#         response = await coordinator.send_global_control_command(command)
#         return response
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Main API: Error controlling all satellites: {e}", exc_info=True)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to control all satellites: {e}")

# --- End New Admin API Endpoints ---


@app.get("/health")
async def health_check():
    db_status = db.ping()
    return {"status": "ok", "database_connected": db_status}

@app.get("/metrics")
async def metrics():
    return HTMLResponse(content=get_metrics_text(), media_type="text/plain")

@app.get("/link_profile/{target_url:path}", response_model=LinkProfileResponse)
async def get_link_profile(target_url: str, current_user: User = Depends(get_current_user)): # Use imported get_current_user
    profile = db.get_link_profile(target_url)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link profile not found")
    return LinkProfileResponse.from_link_profile(profile)

@app.get("/domain/info/{domain_name}", response_model=DomainResponse)
async def get_domain_info(domain_name: str, current_user: User = Depends(get_current_user)): # Use imported get_current_user
    domain = db.get_domain(domain_name)
    if not domain:
        # DomainService now uses smart_api_router_service internally
        async with domain_service_instance as ds:
            domain = await ds.get_domain_info(domain_name)
            if domain:
                db.save_domain(domain)
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain info not found")
    return DomainResponse.from_domain(domain)

# --- Register API Routers ---
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
app.include_router(customer_router) # Include the new customer router
app.include_router(admin_router) # Include the new admin router
# --- End Register API Routers ---

# Mount static files AFTER API routers
app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(project_root, "Link_Profiler", "static", "mission-control-dashboard", "dist", "assets")),
    name="mission-control-dashboard-assets",
)

app.mount(
    "/customer-dashboard/assets",
    StaticFiles(directory=os.path.join(project_root, "Link_Profiler", "static", "customer-dashboard", "dist", "assets")),
    name="customer-dashboard-assets",
)

# Catch-all route for serving SPAs based on subdomain
# This must come AFTER all other API routes and static mounts to ensure they are matched first.
@app.get("/{path:path}", response_class=HTMLResponse)
async def serve_dashboard_spa(request: Request, path: str):
    """
    Serves the appropriate SPA (Customer or Mission Control) based on subdomain,
    or redirects if no specific subdomain is matched.
    """
    logger.debug(f"serve_dashboard_spa invoked for path: {request.url.path}. is_api_request: {getattr(request.state, 'is_api_request', 'N/A')}")
    if hasattr(request.state, 'is_api_request') and request.state.is_api_request:
        logger.warning(f"serve_dashboard_spa received an API request: {request.url.path}. This should have been handled by a specific router.")
        raise HTTPException(status_code=404, detail="API endpoint not found or handled by other routers.")

    # Check if this is a customer dashboard request
    if hasattr(request.state, 'is_customer_dashboard') and request.state.is_customer_dashboard:
        dashboard_path = os.path.join(project_root, "Link_Profiler", "static", "customer-dashboard", "dist")
        index_html_path = os.path.join(dashboard_path, "index.html")
        
        logger.info(f"Serving customer dashboard from {index_html_path} for request to {request.url}")
        
        if os.path.exists(index_html_path):
            with open(index_html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            logger.error(f"Customer dashboard index.html not found at {index_html_path}")
            raise HTTPException(status_code=500, detail="Customer Dashboard not built or found.")

    # Check if this is a mission control dashboard request
    elif hasattr(request.state, 'is_mission_control_dashboard') and request.state.is_mission_control_dashboard:
        dashboard_path = os.path.join(project_root, "Link_Profiler", "static", "mission-control-dashboard", "dist")
        index_html_path = os.path.join(dashboard_path, "index.html")

        logger.info(f"Serving mission control dashboard from {index_html_path} for request to {request.url}")
        
        if os.path.exists(index_html_path):
            with open(index_html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            logger.error(f"Mission Control dashboard index.html not found at {index_html_path}")
            raise HTTPException(status_code=500, detail="Mission Control Dashboard not built or found.")
    
    else:
        # If no specific subdomain, redirect to customer dashboard by default
        # This assumes the main domain (e.g., yspanel.com) should redirect to customer.yspanel.com
        host = request.headers.get('host', 'localhost')
        logger.info(f"No specific dashboard subdomain detected for host {host}. Redirecting to customer dashboard.")
        
        # Extract the domain from the current host (remove subdomain if present)
        host_parts = host.split('.')
        if len(host_parts) > 2:
            # Remove subdomain, keep domain.tld
            base_domain = '.'.join(host_parts[1:])
        else:
            # Already a base domain
            base_domain = host
        
        # Construct the redirect URL
        redirect_host = f"{CUSTOMER_SUBDOMAIN}.{base_domain}"
        scheme = "https" if request.url.scheme == "https" else "http"
        redirect_url = f"{scheme}://{redirect_host}/"
        
        logger.info(f"Redirecting from {host} to {redirect_url}")
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
