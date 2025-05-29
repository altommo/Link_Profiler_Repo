"""
API Endpoints for the Link Profiler System
File: api/main.py
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import logging
from urllib.parse import urlparse
from datetime import datetime # Import datetime for Pydantic models

from services.crawl_service import CrawlService
from database.database import Database
from core.models import CrawlConfig, CrawlJob, LinkProfile, Backlink, serialize_model, CrawlStatus, LinkType, SpamLevel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Link Profiler API",
    description="API for discovering backlinks and generating link profiles.",
    version="0.1.0",
)

# Initialize database and crawl service
# In a production environment, these would likely be managed by a dependency injection system
# or passed in a more structured way (e.g., via a factory or global state management).
db = Database()
crawl_service = CrawlService(db)

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
    status: CrawlStatus
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
        # Convert CrawlStatus Enum to its value for Pydantic serialization
        job_dict = serialize_model(job)
        # Ensure datetime objects are correctly handled by Pydantic
        if isinstance(job_dict.get('created_date'), str):
            job_dict['created_date'] = datetime.fromisoformat(job_dict['created_date'])
        if isinstance(job_dict.get('started_date'), str):
            job_dict['started_date'] = datetime.fromisoformat(job_dict['started_date'])
        if isinstance(job_dict.get('completed_date'), str):
            job_dict['completed_date'] = datetime.fromisoformat(job_dict['completed_date'])
        
        job_dict['status'] = job.status # Pydantic handles Enum directly if type hint is Enum
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
            profile_dict['analysis_date'] = datetime.fromisoformat(profile_dict['analysis_date'])
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
            backlink_dict['discovered_date'] = datetime.fromisoformat(backlink_dict['discovered_date'])
        return cls(**backlink_dict)


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
    job = crawl_service.get_job_status(job_id)
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

    profile = crawl_service.get_link_profile_for_url(target_url)
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

    backlinks = crawl_service.get_backlinks_for_url(target_url)
    if not backlinks:
        raise HTTPException(status_code=404, detail="No backlinks found for this URL. A crawl might not have been completed yet.")
    
    return [BacklinkResponse.from_backlink(bl) for bl in backlinks]

# Example of how to run the API (for development)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)

