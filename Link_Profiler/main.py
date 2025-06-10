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
# New: Import public_api_routes
from Link_Profiler.api.public_api_routes import public_api_router # Import the new public API router

# New: Import authentication dependencies
from fastapi.security import OAuth2PasswordRequestForm # Only import this specific class needed for /token endpoint

# --- RESTORED: Import CORSMiddleware ---
from fastapi.middleware.cors import CORSMiddleware # Import CORSMiddleware

# Define FastAPI app instance here
app = FastAPI(
    title="Link Profiler API",
    description="API for comprehensive link profiling, SEO analysis, and domain intelligence.",
    version=config_loader.get("system.current_code_version", "0.1.0"),
    lifespan=lifespan
)

# Define origins here
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

# Add the subdomain router middleware BEFORE other middleware or routes
app.add_middleware(
    SubdomainRouterMiddleware,
    customer_subdomain=CUSTOMER_SUBDOMAIN,
    mission_control_subdomain=MISSION_CONTROL_SUBDOMAIN
)


# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)
# --- END RESTORED ---


# --- Register API Routers ---
# All API routers must be included BEFORE any static file mounts or catch-all routes
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
app.include_router(public_api_router) # Include the new public API router
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

# Removed: @app.get("/users/me", response_model=UserResponse)
# async def read_users_me(current_user: User = Depends(get_current_user)): # Use imported get_current_user
#     return UserResponse.from_user(current_user)

# --- Re-exposed Monitoring Endpoints from dashboard_server.py ---
# These endpoints are now part of the main API for Mission Control to consume.


# Removed: @app.get("/health")
# async def health_check():
#     db_status = db.ping()
#     return {"status": "ok", "database_connected": db_status}

# Removed: @app.get("/metrics")
# async def metrics():
#     return HTMLResponse(content=get_metrics_text(), media_type="text/plain")

# Removed: @app.get("/link_profile/{target_url:path}", response_model=LinkProfileResponse)
# async def get_link_profile(target_url: str, current_user: User = Depends(get_current_user)): # Use imported get_current_user
#     profile = db.get_link_profile(target_url)
#     if not profile:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link profile not found")
#     return LinkProfileResponse.from_link_profile(profile)

# Removed: @app.get("/domain/info/{domain_name}", response_model=DomainResponse)
# async def get_domain_info(domain_name: str, current_user: User = Depends(get_current_user)): # Use imported get_current_user
#     domain = db.get_domain(domain_name)
#     if not domain:
#         # DomainService now uses smart_api_router_service internally
#         async with domain_service_instance as ds:
#             domain = await ds.get_domain_info(domain_name)
#             if domain:
#                 db.save_domain(domain)
#             else:
#                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain info not found")
#     return DomainResponse.from_domain(domain)

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
        # Do NOT return pass. Instead, raise a 404 to indicate the API endpoint was not found.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    
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
