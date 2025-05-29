"""
API Endpoints for the Link Profiler System
File: api/main.py
"""

import os
import sys

# --- Robust Project Root Discovery ---
# This method searches upwards from the current file's directory
# until it finds a known marker file (e.g., setup.py or main.py launcher).
# This is more resilient to different ways of launching the application.
current_dir = os.path.dirname(os.path.abspath(__file__))
found_project_root = None
for _ in range(5): # Search up to 5 levels
    if os.path.exists(os.path.join(current_dir, 'setup.py')) or \
       os.path.exists(os.path.join(current_dir, 'main.py')): # Assuming main.py is in project root
        found_project_root = current_dir
        break
    current_dir = os.path.dirname(current_dir)

if found_project_root and found_project_root not in sys.path:
    sys.path.insert(0, found_project_root)
# --- End Robust Project Root Discovery ---

# --- Debugging Print Statements ---
print("PROJECT_ROOT (discovered):", found_project_root)
print("SYS.PATH (after discovery):", sys.path[:5])  # show the first few entries
# --- End Debugging Print Statements ---


from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import logging
from urllib.parse import urlparse
from datetime import datetime # Import datetime for Pydantic models
from contextlib import asynccontextmanager # Import asynccontextmanager

from Link_Profiler.services.crawl_service import CrawlService # Changed to absolute import
from Link_Profiler.services.domain_service import DomainService, SimulatedDomainAPIClient # Changed to absolute import
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService # Changed to absolute import
from Link_Profiler.services.expired_domain_finder_service import ExpiredDomainFinderService # Changed to absolute import
from Link_Profiler.database.database import Database # Changed to absolute import
from Link_Profiler.core.models import CrawlConfig, CrawlJob, LinkProfile, Backlink, serialize_model, CrawlStatus, LinkType, SpamLevel, Domain # Changed to absolute import

# Configure logging
# Temporarily set level to DEBUG to see detailed logs from database operations
logging.basicConfig(level=logging.DEBUG) 
logger = logging.getLogger(__name__)

# Initialize database
db = Database()

# Initialize DomainService globally, but manage its lifecycle with lifespan
# The api_client is passed here, and its session will be managed by the lifespan event.
domain_service_instance = DomainService(api_client=SimulatedDomainAPIClient())

# Initialize other services that depend on domain_service
crawl_service = CrawlService(db) 
domain_analyzer_service = DomainAnalyzerService(db, domain_service_instance)
expired_domain_finder_service = ExpiredDomainFinderService(db, domain_service_instance, domain_analyzer_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for managing the lifespan of the FastAPI application.
    Ensures resources like aiohttp sessions are properly opened and closed.
    """
    logger.info("Application startup: Entering DomainService context.")
    async with domain_service_instance as ds:
        # Yield control to the application
        yield
    logger.info("Application shutdown: Exiting DomainService context.")


app = FastAPI(
    title="Link Profiler API",
    description="API for discovering backlinks and generating link profiles.",
    version="0.1.0",
    lifespan=lifespan # Register the lifespan context manager
)


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

class StartCrawlRequest(BaseModel):
    target_url: str = Field(..., description="The URL for which to find backlinks (e.g., 'https://example.com').")
    initial_seed_urls: List[str] = Field(..., description="A list of URLs to start crawling from to discover backlinks.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration.")

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
    error_log: List[str]
    results: Dict = Field(default_factory=dict)

    @classmethod
    def from_crawl_job(cls, job: CrawlJob):
        # Convert CrawlJob dataclass to a dictionary
        job_dict = serialize_model(job)
        
        # Explicitly convert Enum to its value string for Pydantic
        job_dict['status'] = job.status.value 

        # Ensure datetime objects are correctly handled by Pydantic
        # Pydantic v2 handles ISO 8601 strings automatically if the type hint is datetime
        # We can remove the explicit conversion here if serialize_model already outputs ISO strings
        # Let's keep it for robustness in case serialize_model changes or for older Pydantic versions
        if isinstance(job_dict.get('created_date'), str):
            try:
                job_dict['created_date'] = datetime.fromisoformat(job_dict['created_date'])
            except ValueError:
                 logger.warning(f"Could not parse created_date string: {job_dict.get('created_date')}")
                 job_dict['created_date'] = None # Or handle as error

        if isinstance(job_dict.get('started_date'), str):
             try:
                job_dict['started_date'] = datetime.fromisoformat(job_dict['started_date'])
             except ValueError:
                 logger.warning(f"Could not parse started_date string: {job_dict.get('started_date')}")
                 job_dict['started_date'] = None # Or handle as error

        if isinstance(job_dict.get('completed_date'), str):
             try:
                job_dict['completed_date'] = datetime.fromisoformat(job_dict['completed_date'])
             except ValueError:
                 logger.warning(f"Could not parse completed_date string: {job_dict.get('completed_date')}")
                 job_dict['completed_date'] = None # Or handle as error

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
                 profile_dict['analysis_date'] = None # Or handle as error
        return cls(**profile_dict)

class BacklinkResponse(BaseModel):
    source_url: str
    target_url: str
    source_domain: str
    target_domain: str
    anchor_text: str
    link_type: LinkType # Pydantic handles Enum directly
    context_text: str
    is_image_link: bool
    alt_text: Optional[str]
    discovered_date: datetime
    authority_passed: bool
    spam_level: SpamLevel # Pydantic handles Enum directly

    @classmethod
    def from_backlink(cls, backlink: Backlink):
        backlink_dict = serialize_model(backlink)
        # Pydantic handles Enum directly if type hint is Enum
        backlink_dict['link_type'] = backlink.link_type
        backlink_dict['spam_level'] = backlink.spam_level
        if isinstance(backlink_dict.get('discovered_date'), str):
            try:
                backlink_dict['discovered_date'] = datetime.fromisoformat(backlink_dict['discovered_date'])
            except ValueError:
                 logger.warning(f"Could not parse discovered_date string: {backlink_dict.get('discovered_date')}")
                 backlink_dict['discovered_date'] = None # Or handle as error
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
                 domain_dict['first_seen'] = None # Or handle as error
        if isinstance(domain_dict.get('last_crawled'), str):
            try:
                domain_dict['last_crawled'] = datetime.fromisoformat(domain_dict['last_crawled'])
            except ValueError:
                 logger.warning(f"Could not parse last_crawled string: {domain_dict.get('last_crawled')}")
                 domain_dict['last_crawled'] = None # Or handle as error
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


# --- API Endpoints ---

@app.post("/crawl/start_backlink_discovery", response_model=CrawlJobResponse, status_code=202)
async def start_backlink_discovery(
    request: StartCrawlRequest, 
    background_tasks: BackgroundTasks
):
    """
    Starts a new backlink discovery crawl job for a given target URL.
    The crawl runs in the background.
    """
    logger.info(f"Received request to start backlink discovery for {request.target_url}")
    
    # Convert Pydantic CrawlConfigRequest to internal CrawlConfig dataclass using from_dict
    crawl_config = CrawlConfig.from_dict(request.config.dict() if request.config else {})

    # Validate target_url and initial_seed_urls
    if not urlparse(request.target_url).scheme or not urlparse(request.target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")
    for url in request.initial_seed_urls:
        if not urlparse(url).scheme or not urlparse(url).netloc:
            raise HTTPException(status_code=400, detail=f"Invalid initial_seed_url: {url}. Must be a full URL.")

    try:
        job = await crawl_service.create_and_start_backlink_crawl_job(
            target_url=request.target_url,
            initial_seed_urls=request.initial_seed_urls,
            config=crawl_config
        )
        return CrawlJobResponse.from_crawl_job(job)
    except Exception as e:
        logger.error(f"Error starting crawl job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start crawl job: {e}")

@app.get("/crawl/status/{job_id}", response_model=CrawlJobResponse)
async def get_crawl_status(job_id: str):
    """
    Retrieves the current status of a specific crawl job.
    """
    job = db.get_crawl_job(job_id) # Fetch directly from DB
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found.")
    return CrawlJobResponse.from_crawl_job(job)

@app.get("/link_profile/{target_url:path}", response_model=LinkProfileResponse)
async def get_link_profile(target_url: str):
    """
    Retrieves the link profile for a given target URL.
    """
    # Ensure the target_url is properly encoded if it contains special characters
    # FastAPI's path converter handles this to some extent, but for consistency
    # with how it's stored, it's good to ensure it's canonical.
    
    # Basic validation
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    profile = db.get_link_profile(target_url) # Fetch directly from DB
    if not profile:
        raise HTTPException(status_code=404, detail="Link profile not found for this URL. A crawl might not have been completed yet.")
    return LinkProfileResponse.from_link_profile(profile)

@app.get("/backlinks/{target_url:path}", response_model=List[BacklinkResponse])
async def get_backlinks(target_url: str):
    """
    Retrieves all raw backlinks found for a given target URL.
    """
    # Basic validation
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    # Revert to using the database method directly
    backlinks = db.get_backlinks_for_target(target_url) 
    
    if not backlinks:
        # This will now correctly return 404 if the database query returns 0
        raise HTTPException(status_code=404, detail=f"No backlinks found for target URL {target_url}.")
    
    return [BacklinkResponse.from_backlink(bl) for bl in backlinks]

# Temporary endpoint to get ALL backlinks for debugging
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
    
    # Use the context-managed domain_service_instance
    is_available = await domain_service_instance.check_domain_availability(domain_name)
    return {"domain_name": domain_name, "is_available": is_available}

@app.get("/domain/whois/{domain_name}", response_model=Dict)
async def get_domain_whois(domain_name: str):
    """
    Retrieves WHOIS information for a given domain name.
    """
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    # Use the context-managed domain_service_instance
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
    
    # Use the context-managed domain_service_instance
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
    
    # domain_analyzer_service uses the context-managed domain_service_instance internally
    analysis_result = await domain_analyzer_service.analyze_domain_for_expiration_value(domain_name)
    
    if not analysis_result:
        # This case might occur if domain_analyzer_service couldn't get domain info
        raise HTTPException(status_code=404, detail="Failed to perform domain analysis, domain info not found or error occurred.")
    
    return analysis_result

@app.post("/domain/find_expired_domains", response_model=FindExpiredDomainsResponse)
async def find_expired_domains(request: FindExpiredDomainsRequest):
    """
    Searches for valuable expired domains among a list of potential candidates.
    """
    if not request.potential_domains:
        raise HTTPException(status_code=400, detail="No potential domains provided.")
    
    # expired_domain_finder_service uses the context-managed domain_service_instance internally
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

