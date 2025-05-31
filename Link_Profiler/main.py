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

# --- Debugging Print Statements ---
print("SYS.PATH (after discovery):", sys.path[:5])
# --- End Debugging Print Statements ---


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import logging
from urllib.parse import urlparse
from datetime import datetime
from contextlib import asynccontextmanager
import redis.asyncio as redis

from Link_Profiler.services.crawl_service import CrawlService
from Link_Profiler.services.domain_service import DomainService, SimulatedDomainAPIClient, RealDomainAPIClient, AbstractDomainAPIClient
from Link_Profiler.services.backlink_service import BacklinkService, SimulatedBacklinkAPIClient, RealBacklinkAPIClient, GSCBacklinkAPIClient, OpenLinkProfilerAPIClient
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService
from Link_Profiler.services.expired_domain_finder_service import ExpiredDomainFinderService
from Link_Profiler.services.serp_service import SERPService, SimulatedSERPAPIClient, RealSERPAPIClient
from Link_Profiler.services.keyword_service import KeywordService, SimulatedKeywordAPIClient, RealKeywordAPIClient
from Link_Profiler.services.link_health_service import LinkHealthService
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


# Configure logging
logging.basicConfig(level=logging.INFO) 
logger = logging.getLogger(__name__)

# Initialize database
db = Database()

# Initialize Redis connection pool and client
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_pool = redis.ConnectionPool.from_url(redis_url)
redis_client = redis.Redis(connection_pool=redis_pool)

# Initialize ClickHouse Loader conditionally
clickhouse_loader_instance: Optional[ClickHouseLoader] = None
if os.getenv("USE_CLICKHOUSE", "false").lower() == "true":
    logger.info("ClickHouse integration enabled. Attempting to initialize ClickHouseLoader.")
    clickhouse_host = os.getenv("CLICKHOUSE_HOST", "localhost")
    clickhouse_port = int(os.getenv("CLICKHOUSE_PORT", 9000))
    clickhouse_user = os.getenv("CLICKHOUSE_USER", "default")
    clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "")
    clickhouse_database = os.getenv("CLICKHOUSE_DATABASE", "default")
    clickhouse_loader_instance = ClickHouseLoader(
        host=clickhouse_host,
        port=clickhouse_port,
        user=clickhouse_user,
        password=clickhouse_password,
        database=clickhouse_database
    )
else:
    logger.info("ClickHouse integration disabled (USE_CLICKHOUSE is not 'true').")


# Initialize DomainService globally, but manage its lifecycle with lifespan
# Determine which DomainAPIClient to use based on priority: AbstractAPI > Real (paid) > Simulated
if os.getenv("USE_ABSTRACT_API", "false").lower() == "true":
    abstract_api_key = os.getenv("ABSTRACT_API_KEY")
    if not abstract_api_key:
        logger.error("ABSTRACT_API_KEY environment variable not set. Falling back to simulated Domain API.")
        domain_service_instance = DomainService(api_client=SimulatedDomainAPIClient())
    else:
        domain_service_instance = DomainService(api_client=AbstractDomainAPIClient(api_key=abstract_api_key))
elif os.getenv("USE_REAL_DOMAIN_API", "false").lower() == "true":
    domain_service_instance = DomainService(api_client=RealDomainAPIClient(api_key=os.getenv("REAL_DOMAIN_API_KEY", "dummy_domain_key")))
else:
    domain_service_instance = DomainService(api_client=SimulatedDomainAPIClient())

# Initialize BacklinkService based on priority: GSC > OpenLinkProfiler > Real (paid) > Simulated
if os.getenv("USE_GSC_API", "false").lower() == "true":
    backlink_service_instance = BacklinkService(api_client=GSCBacklinkAPIClient())
elif os.getenv("USE_OPENLINKPROFILER_API", "false").lower() == "true":
    backlink_service_instance = BacklinkService(api_client=OpenLinkProfilerAPIClient())
elif os.getenv("USE_REAL_BACKLINK_API", "false").lower() == "true":
    backlink_service_instance = BacklinkService(api_client=RealBacklinkAPIClient(api_key=os.getenv("REAL_BACKLINK_API_KEY", "dummy_backlink_key")))
else:
    backlink_service_instance = BacklinkService(api_client=SimulatedBacklinkAPIClient())

# New: Initialize SERPService and SERPCrawler
serp_crawler_instance = None
if os.getenv("USE_PLAYWRIGHT_SERP_CRAWLER", "false").lower() == "true":
    logger.info("Initialising Playwright SERPCrawler.")
    serp_crawler_instance = SERPCrawler(
        headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
        browser_type=os.getenv("PLAYWRIGHT_BROWSER_TYPE", "chromium")
    )
serp_service_instance = SERPService(
    api_client=RealSERPAPIClient(api_key=os.getenv("REAL_SERP_API_KEY", "dummy_serp_key")) if os.getenv("USE_REAL_SERP_API", "false").lower() == "true" else SimulatedSERPAPIClient(),
    serp_crawler=serp_crawler_instance
)

# New: Initialize KeywordService and KeywordScraper
keyword_scraper_instance = None
if os.getenv("USE_KEYWORD_SCRAPER", "false").lower() == "true":
    logger.info("Initialising KeywordScraper.")
    keyword_scraper_instance = KeywordScraper()
keyword_service_instance = KeywordService(
    api_client=RealKeywordAPIClient(api_key=os.getenv("REAL_KEYWORD_API_KEY", "dummy_keyword_key")) if os.getenv("USE_REAL_KEYWORD_API", "false").lower() == "true" else SimulatedKeywordAPIClient(),
    keyword_scraper=keyword_scraper_instance
)

# New: Initialize LinkHealthService
link_health_service_instance = LinkHealthService(db)

# New: Initialize TechnicalAuditor
technical_auditor_instance = TechnicalAuditor(
    lighthouse_path=os.getenv("LIGHTHOUSE_PATH", "lighthouse") # Allow custom path for Lighthouse CLI
)


# Initialize other services that depend on domain_service and backlink_service
crawl_service = CrawlService(
    db, 
    backlink_service=backlink_service_instance, 
    domain_service=domain_service_instance,
    serp_service=serp_service_instance,
    keyword_service=keyword_service_instance,
    link_health_service=link_health_service_instance,
    clickhouse_loader=clickhouse_loader_instance, # Pass the potentially None instance
    redis_client=redis_client,
    technical_auditor=technical_auditor_instance
) 
domain_analyzer_service = DomainAnalyzerService(db, domain_service_instance)
expired_domain_finder_service = ExpiredDomainFinderService(db, domain_service_instance, domain_analyzer_service)


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
    ]

    # Conditionally add ClickHouseLoader to context managers
    if clickhouse_loader_instance:
        context_managers.append(clickhouse_loader_instance)
    # Add Playwright and KeywordScraper contexts if they are enabled
    if serp_crawler_instance:
        context_managers.append(serp_crawler_instance)
    if keyword_scraper_instance:
        context_managers.append(keyword_scraper_instance)

    # Manually manage the context managers to ensure proper nesting and single yield
    # This pattern ensures all __aenter__ are called before yield, and __aexit__ in reverse order.
    entered_contexts = []
    try:
        for cm in context_managers:
            logger.info(f"Application startup: Entering {cm.__class__.__name__} context.")
            # Call __aenter__ and store the result (which is usually 'self' for context managers)
            entered_contexts.append(await cm.__aenter__())
        
        logger.info("Application startup: Pinging Redis.")
        try:
            await redis_client.ping()
            logger.info("Redis connection successful.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
        
        yield # This is the single yield point for the lifespan

    finally:
        # Exit contexts in reverse order of entry
        for cm in reversed(entered_contexts):
            logger.info(f"Application shutdown: Exiting {cm.__class__.__name__} context.")
            # Pass None, None, None for exc_type, exc_val, exc_tb as we're handling exceptions outside
            await cm.__aexit__(None, None, None)
        
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


class StartCrawlRequest(BaseModel):
    target_url: str = Field(..., description="The URL for which to find backlinks (e.g., 'https://example.com').")
    initial_seed_urls: List[str] = Field(..., description="A list of URLs to start crawling from to discover backlinks.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration.")

class LinkHealthAuditRequest(BaseModel):
    source_urls: List[str] = Field(..., description="A list of source URLs whose outgoing links should be audited for brokenness.")

class TechnicalAuditRequest(BaseModel):
    urls_to_audit: List[str] = Field(..., description="A list of URLs to perform a technical audit on using Lighthouse.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration for the audit (e.g., user agent).")

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

@app.post("/crawl/start_backlink_discovery", response_model=CrawlJobResponse, status_code=202)
async def start_backlink_discovery(
    request: StartCrawlRequest, 
    background_tasks: BackgroundTasks
):
    """
    Starts a new backlink discovery job for a given target URL.
    The crawl runs in the background.
    """
    logger.info(f"Received request to start backlink discovery for {request.target_url}")
    JOBS_CREATED_TOTAL.labels(job_type='backlink_discovery').inc()
    JOBS_IN_PROGRESS.labels(job_type='backlink_discovery').inc()

    # Convert Pydantic CrawlConfigRequest to internal CrawlConfig dataclass using from_dict
    crawl_config = CrawlConfig.from_dict(request.config.dict() if request.config else {})

    # Validate target_url and initial_seed_urls
    if not urlparse(request.target_url).scheme or not urlparse(request.target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")
    for url in request.initial_seed_urls:
        if not urlparse(url).scheme or not urlparse(url).netloc:
            raise HTTPException(status_code=400, detail=f"Invalid initial_seed_url: {url}. Must be a full URL.")

    try:
        job = await crawl_service.create_and_start_crawl_job(
            job_type='backlink_discovery',
            target_url=request.target_url,
            initial_seed_urls=request.initial_seed_urls,
            config=crawl_config
        )
        return CrawlJobResponse.from_crawl_job(job)
    except Exception as e:
        logger.error(f"Error starting crawl job: {e}", exc_info=True)
        JOBS_IN_PROGRESS.labels(job_type='backlink_discovery').dec() # Decrement on immediate failure
        JOBS_FAILED_TOTAL.labels(job_type='backlink_discovery').inc()
        raise HTTPException(status_code=500, detail=f"Failed to start crawl job: {e}")

@app.post("/audit/link_health", response_model=CrawlJobResponse, status_code=202)
async def start_link_health_audit(
    request: LinkHealthAuditRequest,
    background_tasks: BackgroundTasks
):
    """
    Starts a new link health audit job for a list of source URLs.
    The audit runs in the background.
    """
    logger.info(f"Received request to start link health audit for {len(request.source_urls)} URLs.")
    JOBS_CREATED_TOTAL.labels(job_type='link_health_audit').inc()
    JOBS_IN_PROGRESS.labels(job_type='link_health_audit').inc()

    if not request.source_urls:
        raise HTTPException(status_code=400, detail="At least one source URL must be provided for link health audit.")
    
    for url in request.source_urls:
        if not urlparse(url).scheme or not urlparse(url).netloc:
            raise HTTPException(status_code=400, detail=f"Invalid source_url: {url}. Must be a full URL (e.g., https://example.com).")

    try:
        job = await crawl_service.create_and_start_crawl_job(
            job_type='link_health_audit',
            source_urls_to_audit=request.source_urls
        )
        return CrawlJobResponse.from_crawl_job(job)
    except Exception as e:
        logger.error(f"Error starting link health audit job: {e}", exc_info=True)
        JOBS_IN_PROGRESS.labels(job_type='link_health_audit').dec()
        JOBS_FAILED_TOTAL.labels(job_type='link_health_audit').inc()
        raise HTTPException(status_code=500, detail=f"Failed to start link health audit job: {e}")

@app.post("/audit/technical_audit", response_model=CrawlJobResponse, status_code=202)
async def start_technical_audit(
    request: TechnicalAuditRequest,
    background_tasks: BackgroundTasks
):
    """
    Starts a new technical audit job for a list of URLs using Lighthouse.
    The audit runs in the background.
    """
    logger.info(f"Received request to start technical audit for {len(request.urls_to_audit)} URLs.")
    JOBS_CREATED_TOTAL.labels(job_type='technical_audit').inc()
    JOBS_IN_PROGRESS.labels(job_type='technical_audit').inc()

    if not request.urls_to_audit:
        raise HTTPException(status_code=400, detail="At least one URL must be provided for technical audit.")
    
    for url in request.urls_to_audit:
        if not urlparse(url).scheme or not urlparse(url).netloc:
            raise HTTPException(status_code=400, detail=f"Invalid URL for audit: {url}. Must be a full URL (e.g., https://example.com).")

    try:
        crawl_config = CrawlConfig.from_dict(request.config.dict() if request.config else {})

        job = await crawl_service.create_and_start_crawl_job(
            job_type='technical_audit',
            urls_to_audit_tech=request.urls_to_audit,
            config=crawl_config
        )
        return CrawlJobResponse.from_crawl_job(job)
    except Exception as e:
        logger.error(f"Error starting technical audit job: {e}", exc_info=True)
        JOBS_IN_PROGRESS.labels(job_type='technical_audit').dec()
        JOBS_FAILED_TOTAL.labels(job_type='technical_audit').inc()
        raise HTTPException(status_code=500, detail=f"Failed to start technical audit job: {e}")


@app.get("/crawl/status/{job_id}", response_model=CrawlJobResponse)
async def get_crawl_status(job_id: str):
    """
    Retrieves the current status of a specific crawl job.
    """
    job = db.get_crawl_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found.")
    return CrawlJobResponse.from_crawl_job(job)

@app.post("/crawl/pause/{job_id}", response_model=CrawlJobResponse)
async def pause_crawl_job(job_id: str):
    """
    Pauses an in-progress crawl job.
    """
    try:
        job = await crawl_service.pause_crawl_job(job_id)
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
        job = await crawl_service.resume_crawl_job(job_id)
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
        job = await crawl_service.stop_crawl_job(job_id)
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

@app.post("/serp/search", response_model=CrawlJobResponse, status_code=202)
async def search_serp(request: SERPSearchRequest):
    """
    Fetches Search Engine Results Page (SERP) data for a given keyword.
    """
    logger.info(f"Received request to search SERP for keyword: {request.keyword}")
    JOBS_CREATED_TOTAL.labels(job_type='serp_analysis').inc()
    JOBS_IN_PROGRESS.labels(job_type='serp_analysis').inc()

    try:
        job = await crawl_service.create_and_start_crawl_job(
            job_type='serp_analysis',
            keyword=request.keyword,
            num_results=request.num_results
        )
        return CrawlJobResponse.from_crawl_job(job)
    except Exception as e:
        logger.error(f"Error fetching SERP results for '{request.keyword}': {e}", exc_info=True)
        JOBS_IN_PROGRESS.labels(job_type='serp_analysis').dec()
        JOBS_FAILED_TOTAL.labels(job_type='serp_analysis').inc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch SERP results: {e}")

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

@app.post("/keyword/suggest", response_model=CrawlJobResponse, status_code=202)
async def suggest_keywords(request: KeywordSuggestRequest):
    """
    Fetches keyword suggestions for a given seed keyword.
    """
    logger.info(f"Received request to get keyword suggestions for seed: {request.seed_keyword}")
    JOBS_CREATED_TOTAL.labels(job_type='keyword_research').inc()
    JOBS_IN_PROGRESS.labels(job_type='keyword_research').inc()

    try:
        job = await crawl_service.create_and_start_crawl_job(
            job_type='keyword_research',
            keyword=request.seed_keyword,
            num_results=request.num_suggestions
        )
        return CrawlJobResponse.from_crawl_job(job)
    except Exception as e:
        logger.error(f"Error fetching keyword suggestions for '{request.seed_keyword}': {e}", exc_info=True)
        JOBS_IN_PROGRESS.labels(job_type='keyword_research').dec()
        JOBS_FAILED_TOTAL.labels(job_type='keyword_research').inc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch keyword suggestions: {e}")

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
    Basic health check endpoint.
    """
    return {"status": "ok", "message": "Link Profiler API is running"}

@app.get("/metrics", response_class=Response)
async def prometheus_metrics():
    """
    Exposes Prometheus metrics.
    """
    return Response(content=get_metrics_text(), media_type="text/plain; version=0.0.4; charset=utf-8")
