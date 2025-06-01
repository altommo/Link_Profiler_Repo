"""
Simplified API Endpoints for the Link Profiler System with Queue Support
File: Link_Profiler/api/main_simple.py
"""

import os
import sys

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import logging
from urllib.parse import urlparse
from datetime import datetime
from contextlib import asynccontextmanager

# Import simplified services
from Link_Profiler.services.crawl_service_simplified import CrawlService
from Link_Profiler.services.domain_service import DomainService, SimulatedDomainAPIClient
from Link_Profiler.database.database import Database
from Link_Profiler.core.models import (
    CrawlConfig, CrawlJob, LinkProfile, Backlink, 
    serialize_model, CrawlStatus, LinkType, SpamLevel, Domain
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
db = Database()

# Initialize services with simplified dependencies
domain_service_instance = DomainService(api_client=SimulatedDomainAPIClient())
crawl_service = CrawlService(db, domain_service=domain_service_instance)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    logger.info("Application startup: Entering DomainService context.")
    async with domain_service_instance:
        yield
    logger.info("Application shutdown: Exiting DomainService context.")

app = FastAPI(
    title="Link Profiler API (Simplified)",
    description="Simplified API for discovering backlinks and generating link profiles with queue support.",
    version="0.1.0",
    lifespan=lifespan
)

# Pydantic Models
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
    allowed_domains: Optional[List[str]] = Field(None, description="List of domains explicitly allowed to crawl.")
    blocked_domains: Optional[List[str]] = Field(None, description="List of domains explicitly blocked from crawling.")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="Custom HTTP headers to send with requests.")

class StartCrawlRequest(BaseModel):
    target_url: str = Field(..., description="The URL for which to find backlinks.")
    initial_seed_urls: List[str] = Field(..., description="A list of URLs to start crawling from to discover backlinks.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration.")

class CrawlJobResponse(BaseModel):
    id: str
    target_url: str
    job_type: str
    status: str
    created_date: datetime
    started_date: Optional[datetime]
    completed_date: Optional[datetime]
    progress_percentage: float
    urls_crawled: int
    links_found: int
    errors_count: int
    results: Dict = Field(default_factory=dict)

    @classmethod
    def from_crawl_job(cls, job: CrawlJob):
        job_dict = serialize_model(job)
        job_dict['status'] = job.status.value
        
        # Handle datetime conversion
        for date_field in ['created_date', 'started_date', 'completed_date']:
            if isinstance(job_dict.get(date_field), str):
                try:
                    job_dict[date_field] = datetime.fromisoformat(job_dict[date_field])
                except ValueError:
                    job_dict[date_field] = None
        
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
    referring_domains: List[str]
    analysis_date: datetime

    @classmethod
    def from_link_profile(cls, profile: LinkProfile):
        profile_dict = serialize_model(profile)
        profile_dict['referring_domains'] = list(profile.referring_domains)
        if isinstance(profile_dict.get('analysis_date'), str):
            try:
                profile_dict['analysis_date'] = datetime.fromisoformat(profile_dict['analysis_date'])
            except ValueError:
                profile_dict['analysis_date'] = datetime.now()
        return cls(**profile_dict)

class BacklinkResponse(BaseModel):
    source_url: str
    target_url: str
    source_domain: str
    target_domain: str
    anchor_text: str
    link_type: str
    context_text: str
    is_image_link: bool
    alt_text: Optional[str]
    discovered_date: datetime
    authority_passed: float
    spam_level: str

    @classmethod
    def from_backlink(cls, backlink: Backlink):
        backlink_dict = serialize_model(backlink)
        backlink_dict['link_type'] = backlink.link_type.value
        backlink_dict['spam_level'] = backlink.spam_level.value
        
        if isinstance(backlink_dict.get('discovered_date'), str):
            try:
                backlink_dict['discovered_date'] = datetime.fromisoformat(backlink_dict['discovered_date'])
            except ValueError:
                backlink_dict['discovered_date'] = datetime.now()
        return cls(**backlink_dict)

# API Endpoints
@app.post("/crawl/start_backlink_discovery", response_model=CrawlJobResponse, status_code=202)
async def start_backlink_discovery(request: StartCrawlRequest, background_tasks: BackgroundTasks):
    """Starts a new backlink discovery crawl job."""
    logger.info(f"Received request to start backlink discovery for {request.target_url}")
    
    # Convert config
    crawl_config = CrawlConfig.from_dict(request.config.dict() if request.config else {})

    # Validate URLs
    if not urlparse(request.target_url).scheme or not urlparse(request.target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided.")
    
    for url in request.initial_seed_urls:
        if not urlparse(url).scheme or not urlparse(url).netloc:
            raise HTTPException(status_code=400, detail=f"Invalid initial_seed_url: {url}")

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
    """Retrieves the current status of a specific crawl job."""
    job = crawl_service.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Crawl job not found.")
    return CrawlJobResponse.from_crawl_job(job)

@app.get("/link_profile/{target_url:path}", response_model=LinkProfileResponse)
async def get_link_profile(target_url: str):
    """Retrieves the link profile for a given target URL."""
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided.")

    profile = crawl_service.get_link_profile_for_url(target_url)
    if not profile:
        raise HTTPException(status_code=404, detail="Link profile not found for this URL.")
    return LinkProfileResponse.from_link_profile(profile)

@app.get("/backlinks/{target_url:path}", response_model=List[BacklinkResponse])
async def get_backlinks(target_url: str):
    """Retrieves all raw backlinks found for a given target URL."""
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=400, detail="Invalid target_url provided.")

    backlinks = crawl_service.get_backlinks_for_url(target_url)
    if not backlinks:
        raise HTTPException(status_code=404, detail="No backlinks found for this URL.")
    
    return [BacklinkResponse.from_backlink(bl) for bl in backlinks]

@app.get("/domain/info/{domain_name}")
async def get_domain_info(domain_name: str):
    """Retrieves comprehensive domain information."""
    if not domain_name or '.' not in domain_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")
    
    domain_obj = await domain_service_instance.get_domain_info(domain_name)
    if not domain_obj:
        raise HTTPException(status_code=404, detail="Domain information not found.")
    return serialize_model(domain_obj)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Add queue endpoints if available
try:
    from Link_Profiler.api.queue_endpoints import add_queue_endpoints
    add_queue_endpoints(app)
    logger.info("✅ Queue endpoints added successfully")
except ImportError as e:
    logger.warning(f"⚠️ Queue endpoints not available: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
