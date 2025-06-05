import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

# Import from core.models for shared data structures and serialization
from Link_Profiler.core.models import User, Token, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion, LinkIntersectResult, CompetitiveKeywordAnalysisResult, AlertRule, AlertSeverity, AlertChannel, ContentGapAnalysisResult, DomainHistory, LinkProspect, OutreachCampaign, OutreachEvent, ReportJob, CrawlJob, LinkProfile, Backlink, SEOMetrics # Added serialize_model, ReportJob, SEOMetrics

# Initialize logger for this module
logger = logging.getLogger(__name__)


# Pydantic Models for API Request/Response (moved from main.py)

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
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
        user_dict = user.to_dict() # Use to_dict() method
        if isinstance(user_dict.get('created_at'), str):
            try:
                user_dict['created_at'] = datetime.fromisoformat(user_dict['created_at'])
            except ValueError:
                 logger.warning(f"Could not parse created_at string: {user_dict.get('created_at')}")
                 user_dict['created_at'] = None
        return cls(**user_dict)

# Token model is already defined in core.models, so we can just import it.
# If it was a Pydantic model specific to the API response, it would be here.
# For now, assuming core.models.Token is sufficient.
# Let's define it here to be explicit about API response models.
class Token(BaseModel):
    access_token: str
    token_type: str

# --- Pydantic Models for Crawl and Audit Requests (moved from main.py) ---

class CrawlConfigRequest(BaseModel):
    max_depth: int = Field(3, description="Maximum depth to crawl from seed URLs.")
    max_pages: int = Field(1000, description="Maximum number of pages to crawl.")
    # delay_seconds: float = Field(1.0, description="Delay between requests to the same domain in seconds.") # Removed
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
    # ml_rate_optimization: bool = Field(False, description="Whether to enable machine learning-based rate optimization for adaptive delays.") # Removed
    captcha_solving_enabled: bool = Field(False, description="Whether to enable CAPTCHA solving for browser-based crawls.")
    anomaly_detection_enabled: bool = Field(False, description="Whether to enable real-time anomaly detection.")
    use_proxies: bool = Field(False, description="Whether to use proxies for crawling.")
    proxy_list: Optional[List[Dict[str, str]]] = Field(None, description="List of proxy configurations (e.g., [{'url': 'http://user:pass@ip:port', 'region': 'us-east'}]).")
    proxy_region: Optional[str] = Field(None, description="Desired proxy region for this crawl job. If not specified, any available proxy will be used.")
    render_javascript: bool = Field(False, description="Whether to use a headless browser to render JavaScript content for crawling.")
    browser_type: Optional[str] = Field("chromium", description="Browser type for headless rendering (chromium, firefox, webkit). Only applicable if render_javascript is true.")
    headless_browser: bool = Field(True, description="Whether the browser should run in headless mode. Only applicable if render_javascript is true.")
    extract_image_text: bool = Field(False, description="Whether to perform OCR on images to extract text.")
    crawl_web3_content: bool = Field(False, description="Whether to crawl Web3 content (e.g., IPFS hash, blockchain address).")
    crawl_social_media: bool = Field(False, description="Whether to crawl social media content.")
    job_type: str = Field("unknown", description="The type of job this configuration is for (e.g., 'backlink_discovery', 'technical_audit').") # Added job_type to CrawlConfig


class StartCrawlRequest(BaseModel):
    target_url: str = Field(..., description="The URL for which to find backlinks (e.g., 'https://example.com').")
    initial_seed_urls: List[str] = Field(..., description="A list of URLs to start crawling from to discover backlinks.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration.")
    priority: int = Field(5, ge=1, le=10, description="Priority of the job (1=highest, 10=lowest).") # Added priority
    scheduled_at: Optional[datetime] = Field(None, description="Optional: UTC datetime to schedule the job for.") # Added scheduled_at
    cron_schedule: Optional[str] = Field(None, description="Optional: Cron string for recurring jobs.") # Added cron_schedule


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

# --- Pydantic Models for API Responses and other requests (moved from main.py) ---

class CrawlErrorResponse(BaseModel):
    timestamp: datetime
    url: str
    error_type: str
    message: str
    details: Optional[str]

    @classmethod
    def from_crawl_error(cls, error: CrawlError):
        return cls(**error.to_dict()) # Use to_dict() method


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
    initial_seed_urls: List[str] = Field(default_factory=list) # Added initial_seed_urls

    class Config:
        use_enum_values = True # Ensure enums are serialized by value

    @classmethod
    def from_crawl_job(cls, job: CrawlJob):
        job_dict = job.to_dict() # Use to_dict() method
        
        # Explicitly convert Enum to its value string for Pydantic if not using use_enum_values
        # job_dict['status'] = job.status.value 

        if isinstance(job_dict.get('created_date'), str):
            try:
                job_dict['created_date'] = datetime.fromisoformat(job_dict['created_date'])
            except ValueError:
                 logger.warning(f"Could not parse created_date string: {job_dict.get('created_date')}")
                 job_dict['created_date'] = None

        if isinstance(job_dict.get('started_date'), str):
             try:
                job_dict['started_2025-06-02 01:31:15,173 - Link_Profiler.services.web3_service:38 - INFO - Web3 Service is disabled by configuration.
2025-06-02 01:31:15,319 - Link_Profiler.main:368 - INFO - Global Playwright browser for WebCrawler is disabled by configuration.
2025-06-02 01:31:15,321 - Link_Profiler.main:376 - INFO - Application startup: Entering DomainService context.
2025-06-02 01:31:15,323 - Link_Profiler.services.domain_service:403 - DEBUG - Entering DomainService context.
2025-06-02 01:31:15,325 - Link_Profiler.services.domain_service.SimulatedDomainAPIClient:61 - DEBUG - Entering SimulatedDomainAPIClient context.
2025-06-02 01:31:15,327 - Link_Profiler.main:376 - INFO - Application startup: Entering BacklinkService context.
2025-06-02 01:31:15,327 - Link_Profiler.services.backlink_service:568 - DEBUG - Entering BacklinkService context.
2025-06-02 01:31:15,328 - Link_Profiler.services.backlink_service.SimulatedBacklinkAPIClient:62 - DEBUG - Entering SimulatedBacklinkAPIClient context.
2025-06-02 01:31:15,329 - Link_Profiler.main:376 - INFO - Application startup: Entering SERPService context.
2025-06-02 01:31:15,329 - Link_Profiler.services.serp_service:258 - DEBUG - Entering SERPService context.
2025-06-02 01:31:15,330 - Link_Profiler.services.serp_service.SimulatedSERPAPIClient:51 - DEBUG - Entering SimulatedSERPAPIClient context.
2025-06-02 01:31:15,331 - Link_Profiler.main:376 - INFO - Application startup: Entering KeywordService context.
2025-06-02 01:31:15,331 - Link_Profiler.services.keyword_service:348 - DEBUG - Entering KeywordService context.
2025-06-02 01:31:15,332 - Link_Profiler.services.keyword_service.SimulatedKeywordAPIClient:52 - DEBUG - Entering SimulatedKeywordAPIClient context.
2025-06-02 01:31:15,332 - Link_Profiler.main:376 - INFO - Application startup: Entering LinkHealthService context.
2025-06-02 01:31:15,333 - Link_Profiler.services.link_health_service:45 - DEBUG - Entering LinkHealthService context.
2025-06-02 01:31:15,334 - Link_Profiler.main:376 - INFO - Application startup: Entering TechnicalAuditor context.
2025-06-02 01:31:15,335 - Link_Profiler.crawlers.technical_auditor:28 - INFO - Entering TechnicalAuditor context.
2025-06-02 01:31:15,335 - Link_Profiler.main:376 - INFO - Application startup: Entering AIService context.
2025-06-02 01:31:15,336 - Link_Profiler.main:376 - INFO - Application startup: Entering AlertService context.
2025-06-02 01:31:15,337 - Link_Profiler.services.alert_service:32 - INFO - AlertService starting up. Loading active alert rules.
2025-06-02 01:31:15,529 - Link_Profiler.services.alert_service:47 - INFO - Loaded 0 active alert rules.
2025-06-02 01:31:15,530 - Link_Profiler.main:376 - INFO - Application startup: Entering AuthService context.
2025-06-02 01:31:15,531 - Link_Profiler.main:376 - INFO - Application startup: Entering ReportService context.
2025-06-02 01:31:15,531 - Link_Profiler.main:376 - INFO - Application startup: Entering CompetitiveAnalysisService context.
2025-06-02 01:31:15,532 - Link_Profiler.main:376 - INFO - Application startup: Entering SocialMediaService context.
2025-06-02 01:31:15,532 - Link_Profiler.services.social_media_service:46 - DEBUG - Entering SocialMediaService context.
2025-06-02 01:31:15,533 - Link_Profiler.main:376 - INFO - Application startup: Entering Web3Service context.
2025-06-02 01:31:15,534 - Link_Profiler.main:376 - INFO - Application startup: Entering LinkBuildingService context.
2025-06-02 01:31:15,534 - Link_Profiler.main:376 - INFO - Application startup: Entering GSCClient context.
2025-06-02 01:31:15,535 - Link_Profiler.main:376 - INFO - Application startup: Entering PageSpeedClient context.
2025-06-02 01:31:15,535 - Link_Profiler.main:376 - INFO - Application startup: Entering GoogleTrendsClient context.
2025-06-02 01:31:15,536 - Link_Profiler.main:376 - INFO - Application startup: Entering WHOISClient context.
2025-06-02 01:31:15,536 - Link_Profiler.main:376 - INFO - Application startup: Entering DNSClient context.
2025-06-02 01:31:15,537 - Link_Profiler.main:376 - INFO - Application startup: Entering RedditClient context.
2025-06-02 01:31:15,537 - Link_Profiler.main:376 - INFO - Application startup: Entering YouTubeClient context.
2025-06-02 01:31:15,539 - Link_Profiler.main:376 - INFO - Application startup: Entering NewsAPIClient context.
2025-06-02 01:31:15,540 - Link_Profiler.main:380 - INFO - Application startup: Pinging Redis.
2025-06-02 01:31:19,653 - Link_Profiler.main:387 - ERROR - Failed to connect to Redis: Error Multiple exceptions: [Errno 10061] Connect call failed ('::1', 6379, 0, 0), [Errno 10061] Connect call failed ('127.0.0.1', 6379) connecting to localhost:6379.
2025-06-02 01:36:19,641 - Link_Profiler.services.alert_service:221 - DEBUG - Refreshing alert rules.
2025-06-02 01:36:19,650 - Link_Profiler.services.alert_service:47 - INFO - Loaded 0 active alert rules.
2025-06-02 01:41:19,629 - Link_Profiler.services.alert_service:221 - DEBUG - Refreshing alert rules.
2025-06-02 01:41:19,629 - Link_Profiler.services.alert_service:47 - INFO - Loaded 0 active alert rules.
2025-06-02 01:45:41,726 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting NewsAPIClient context.
2025-06-02 01:45:41,733 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting YouTubeClient context.
2025-06-02 01:45:41,733 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting RedditClient context.
2025-06-02 01:45:41,733 - Link_Profiler.clients.reddit_client.RedditClient:60 - INFO - Exiting RedditClient context.
2025-06-02 01:45:41,733 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting DNSClient context.
2025-06-02 01:45:41,742 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting WHOISClient context.
2025-06-02 01:45:41,742 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting GoogleTrendsClient context.
2025-06-02 01:45:41,742 - Link_Profiler.clients.google_trends_client.GoogleTrendsClient:42 - INFO - Exiting GoogleTrendsClient context.
2025-06-02 01:45:41,742 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting PageSpeedClient context.
2025-06-02 01:45:41,742 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting GSCClient context.
2025-06-02 01:45:41,742 - Link_Profiler.clients.google_search_console_client.GSCClient:107 - INFO - Exiting GSCClient context.
2025-06-02 01:45:41,742 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting LinkBuildingService context.
2025-06-02 01:45:41,742 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting Web3Service context.
2025-06-02 01:45:41,742 - Link_Profiler.services.web3_service:55 - INFO - Exiting Web3Service context.
2025-06-02 01:45:41,742 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting SocialMediaService context.
2025-06-02 01:45:41,758 - Link_Profiler.services.social_media_service:59 - DEBUG - Exiting SocialMediaService context.
2025-06-02 01:45:41,758 - Link_Profiler.clients.reddit_client.RedditClient:60 - INFO - Exiting RedditClient context.
2025-06-02 01:45:41,758 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting CompetitiveAnalysisService context.
2025-06-02 01:45:41,758 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting ReportService context.
2025-06-02 01:45:41,758 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting AuthService context.
2025-06-02 01:45:41,758 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting AlertService context.
2025-06-02 01:45:41,758 - Link_Profiler.services.alert_service:39 - INFO - AlertService shutting down.
2025-06-02 01:45:41,773 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting AIService context.
2025-06-02 01:45:41,773 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting TechnicalAuditor context.
2025-06-02 01:45:41,778 - Link_Profiler.crawlers.technical_auditor:33 - INFO - Exiting TechnicalAuditor context.
2025-06-02 01:45:41,780 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting LinkHealthService context.
2025-06-02 01:45:41,780 - Link_Profiler.services.link_health_service:68 - DEBUG - Exiting LinkHealthService context.
2025-06-02 01:45:41,780 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting KeywordService context.
2025-06-02 01:45:41,784 - Link_Profiler.services.keyword_service:360 - DEBUG - Exiting SimulatedKeywordAPIClient context.
2025-06-02 01:45:41,784 - Link_Profiler.clients.google_trends_client.GoogleTrendsClient:42 - INFO - Exiting GoogleTrendsClient context.
2025-06-02 01:45:41,789 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting SERPService context.
2025-06-02 01:45:41,791 - Link_Profiler.services.serp_service:268 - DEBUG - Exiting SimulatedSERPAPIClient context.
2025-06-02 01:45:41,791 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting BacklinkService context.
2025-06-02 01:45:41,796 - Link_Profiler.services.backlink_service:574 - DEBUG - Exiting SimulatedBacklinkAPIClient context.
2025-06-02 01:45:41,799 - Link_Profiler.main:400 - INFO - Application shutdown: Exiting DomainService context.
2025-06-02 01:45:41,799 - Link_Profiler.services.domain_service:413 - DEBUG - Exiting SimulatedDomainAPIClient context.
2025-06-02 01:45:41,799 - Link_Profiler.main:413 - INFO - Application shutdown: Closing Redis connection pool.
