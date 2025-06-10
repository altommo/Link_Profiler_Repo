import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
from urllib.parse import urlparse # Import urlparse

# Import from core.models for shared data structures and serialization
from Link_Profiler.core.models import User, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion, AlertRule, AlertSeverity, AlertChannel, ContentGapAnalysisResult, DomainHistory, LinkProspect, OutreachCampaign, OutreachEvent, ReportJob, CrawlJob, LinkProfile, Backlink, SEOMetrics, Token, TokenData, LinkIntersectResult, CompetitiveKeywordAnalysisResult # Added Token, TokenData, LinkIntersectResult, CompetitiveAnalysisResult

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
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        # Pydantic V2: 'orm_mode' has been renamed to 'from_attributes'
        from_attributes = True 
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_user(cls, user: User):
        user_dict = user.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**user_dict)

# Token model is already defined in core.models, so we can just import it.
# If it was a Pydantic model specific to the API response, it would be here.
# For now, assuming core.models.Token is sufficient.
# Let's define it here to be explicit about API response models.
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel): # Re-defining TokenData as a Pydantic model for API schema
    username: Optional[str] = None


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
    crawl_web3_content: bool = Field(False, description="Whether to crawl Web3 content (e.g., IPFS hash, blockchain data, etc.).")
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

class FullSEOAuditRequest(BaseModel): # New Pydantic model for full SEO audit job submission
    urls_to_audit: List[str] = Field(..., description="A list of URLs to perform a full SEO audit on.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration for the audit (e.g., user agent).")

class Web3CrawlRequest(BaseModel): # New Pydantic model for Web3 crawl job submission
    web3_content_identifier: str = Field(..., description="The identifier for Web3 content (e.g., IPFS hash, blockchain data).")
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

# New: Pydantic model for QueueCrawlRequest
class QueueCrawlRequest(BaseModel):
    target_url: str = Field(..., description="The URL to crawl.")
    config: Optional[CrawlConfigRequest] = Field(None, description="Optional crawl configuration.")
    priority: int = Field(5, ge=1, le=10, description="Priority of the job (1=highest, 10=lowest).")
    scheduled_at: Optional[datetime] = Field(None, description="Optional: UTC datetime to schedule the job for.")
    cron_schedule: Optional[str] = Field(None, description="Optional: Cron string for recurring jobs.")


# --- Pydantic Models for API Responses and other requests (moved from main.py) ---

class CrawlErrorResponse(BaseModel):
    timestamp: datetime
    url: str
    error_type: str
    message: str
    details: Optional[str]
    severity: AlertSeverity # Added severity

    class Config:
        use_enum_values = True # Ensure enums are serialized by value

    @classmethod
    def from_crawl_error(cls, error: CrawlError):
        return cls(**error.to_dict()) # Use to_dict() method


class CrawlJobResponse(BaseModel):
    id: str
    target_url: str
    job_type: str
    status: CrawlStatus # Keep as Enum type hint
    created_date: datetime = Field(..., alias="created_at") # Use created_at from core.models.CrawlJob
    started_date: Optional[datetime]
    completed_date: Optional[datetime]
    progress_percentage: float
    urls_crawled: int
    links_found: int
    errors_count: int = Field(..., alias="errors_count") # Use errors_count from core.models.CrawlJob
    error_log: List[CrawlErrorResponse] = Field(..., alias="errors") # Use errors from core.models.CrawlJob
    results: Dict = Field(default_factory=dict)
    # initial_seed_urls is not part of CrawlJob dataclass directly, it's part of the request
    # If needed in CrawlJob, it should be added to its definition or stored in config/results
    priority: int # Added priority
    scheduled_at: Optional[datetime] # Added scheduled_at
    cron_schedule: Optional[str] # Added cron_schedule
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_crawl_job(cls, job: CrawlJob):
        job_dict = job.to_dict() # Use to_dict() method
        
        # Manually map fields that have different names or need special handling
        job_dict['created_date'] = job_dict.pop('created_at', None) # Map created_at to created_date
        job_dict['errors_count'] = len(job.errors) # Calculate errors_count
        job_dict['error_log'] = [CrawlErrorResponse.from_crawl_error(err) for err in job.errors] # Map errors to error_log
        job_dict['last_updated'] = job_dict.pop('last_fetched_at', None) # Map last_fetched_at to last_updated

        return cls(**job_dict)

class LinkProfileResponse(BaseModel):
    target_url: str
    target_domain: str # Added target_domain
    total_backlinks: int
    unique_referring_domains: int # Changed from unique_domains
    dofollow_backlinks: int # Changed from dofollow_links
    nofollow_backlinks: int # Changed from nofollow_links
    ugc_backlinks: int # Added
    sponsored_backlinks: int # Added
    internal_backlinks: int # Added
    external_backlinks: int # Added
    broken_backlinks: int # Added
    top_anchor_texts: Dict[str, int] # Changed from anchor_text_distribution
    top_referring_domains: Dict[str, int] = Field(default_factory=dict) # Changed from referring_domains
    last_updated: datetime # Changed from analysis_date
    last_fetched_at: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_link_profile(cls, profile: LinkProfile):
        profile_dict = profile.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        # No need for manual conversion or logger.warning for parsing errors if from_dict is robust
        
        # Add target_domain from parsing target_url
        profile_dict['target_domain'] = urlparse(profile.target_url).netloc
        
        return cls(**profile_dict)

class BacklinkResponse(BaseModel):
    source_url: str
    target_url: str
    source_domain: Optional[str] # Made optional
    target_domain: Optional[str] # Made optional
    anchor_text: str
    link_type: LinkType 
    nofollow: bool # Added
    ugc: bool # Added
    sponsored: bool # Added
    first_seen: datetime # Changed from discovered_date
    last_seen: datetime # Added
    source_page_authority: Optional[int] # Added
    source_domain_authority: Optional[int] # Added
    rel_attributes: List[str] = Field(default_factory=list) # Added
    context_text: Optional[str] # Made optional
    position_on_page: Optional[str] # Added
    is_image_link: bool # Added
    alt_text: Optional[str] # Added
    authority_passed: Optional[float] # Made optional
    is_active: Optional[bool] # Added
    spam_level: Optional[SpamLevel] # Added
    http_status: Optional[int] = None
    crawl_timestamp: Optional[datetime] = None
    source_domain_metrics: Dict[str, Any] = Field(default_factory=dict)
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_backlink(cls, backlink: Backlink):
        backlink_dict = backlink.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**backlink_dict)

class DomainResponse(BaseModel):
    name: str
    authority_score: Optional[float] # Made optional
    trust_score: Optional[float] = None # Made optional
    spam_score: Optional[float] = None # Made optional
    registered_date: Optional[datetime] = None # Changed from first_seen
    expiration_date: Optional[datetime] = None # Added
    registrar: Optional[str] = None # Added
    is_registered: Optional[bool] = None # Added
    is_parked: Optional[bool] = None # Added
    is_dead: Optional[bool] = None # Added
    whois_raw: Optional[str] = None # Changed from whois_data
    dns_records: Dict[str, List[str]] = Field(default_factory=dict) # Added
    ip_address: Optional[str] = None # Added
    country: Optional[str] = None # Added
    seo_metrics: SEOMetrics = Field(default_factory=SEOMetrics) # Added
    last_checked: datetime # Changed from last_crawled
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_domain(cls, domain: Domain):
        domain_dict = domain.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        # Handle nested SEOMetrics
        if 'seo_metrics' in domain_dict and isinstance(domain_dict['seo_metrics'], dict):
            domain_dict['seo_metrics'] = SEOMetrics(**domain_dict['seo_metrics'])
        return cls(**domain_dict)

class DomainAnalysisResponse(BaseModel):
    domain_name: str
    value_score: float
    is_valuable: bool
    reasons: List[str]
    details: Dict[str, Any]
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        populate_by_name = True # Allow field names to be populated by their alias

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
    rank: int # Changed from position
    url: str # Changed from result_url
    title: str # Changed from title_text
    snippet: Optional[str] = None # Changed from snippet_text
    domain: str # Added
    position_type: Optional[str] = None # Added
    timestamp: datetime # Changed from crawl_timestamp
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at
    
    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_serp_result(cls, result: SERPResult):
        result_dict = result.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**result_dict)

class KeywordSuggestRequest(BaseModel):
    seed_keyword: str = Field(..., description="The initial keyword to get suggestions for.")
    num_suggestions: int = Field(10, description="Number of keyword suggestions to fetch.")

class KeywordSuggestionResponse(BaseModel):
    keyword: str # Changed from suggested_keyword
    search_volume: Optional[int] = None # Changed from search_volume_monthly
    cpc: Optional[float] = None # Changed from cpc_estimate
    competition: Optional[float] = None # Changed from competition_level
    difficulty: Optional[int] = None # Added
    relevance: Optional[float] = None # Added
    source: Optional[str] = None # Added
    keyword_trend: Optional[List[float]] = None # New: keyword_trend
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at
    
    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_keyword_suggestion(cls, suggestion: KeywordSuggestion):
        suggestion_dict = suggestion.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**suggestion_dict)

class LinkIntersectRequest(BaseModel):
    primary_domain: str = Field(..., description="The primary domain for analysis (e.g., 'https://example.com').")
    competitor_domains: List[str] = Field(..., description="A list of competitor domains to compare against (e.g., ['competitor1.com', 'competitor2.com']).")

class LinkIntersectResponse(BaseModel):
    primary_domain: str
    competitor_domains: List[str]
    common_linking_domains: List[str]
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    @classmethod
    def from_link_intersect_result(cls, result: LinkIntersectResult):
        return cls(**result.to_dict()) # Use to_dict() method

class CompetitiveKeywordAnalysisRequest(BaseModel):
    primary_domain: str = Field(..., description="The primary domain for which to perform keyword analysis.")
    competitor_domains: List[str] = Field(..., description="A list of competitor domains to compare against.")

class CompetitiveKeywordAnalysisResponse(BaseModel):
    primary_domain: str
    competitor_domains: List[str]
    common_keywords: List[str]
    keyword_gaps: Dict[str, List[str]]
    primary_unique_keywords: List[str]
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    @classmethod
    def from_competitive_keyword_analysis_result(cls, result: CompetitiveKeywordAnalysisResult):
        return cls(**result.to_dict()) # Use to_dict() method

# New: Pydantic models for AlertRule management
class AlertRuleCreateRequest(BaseModel):
    name: str = Field(..., description="A unique name for the alert rule.")
    description: Optional[str] = Field(None, description="A brief description of the alert rule.")
    is_active: bool = Field(True, description="Whether the alert rule is active.")
    
    trigger_type: str = Field(..., description="Type of event that triggers the alert (e.g., 'job_status_change', 'metric_threshold', 'anomaly_detected').")
    job_type_filter: Optional[str] = Field(None, description="Optional: Apply rule only to specific job types (e.g., 'backlink_discovery').")
    target_url_pattern: Optional[str] = Field(None, description="Optional: Regex pattern for target URLs to apply the rule to.")
    
    metric_name: Optional[str] = Field(None, description="Optional: Name of the metric to monitor (for 'metric_threshold' trigger_type, e.g., 'seo_score', 'broken_links_count', 'crawl_errors_rate').")
    threshold_value: Optional[Union[int, float]] = Field(None, description="Optional: Threshold value for the metric.")
    comparison_operator: Optional[str] = Field(None, description="Optional: Comparison operator for the metric threshold (e.g., '>', '<', '>=', '<=', '==').")
    
    anomaly_type_filter: Optional[str] = Field(None, description="Optional: Filter for specific anomaly types (for 'anomaly_detected' trigger_type, e.g., 'captcha_spike').")
    
    severity: AlertSeverity = Field(AlertSeverity.WARNING, description="Severity level of the alert.")
    notification_channels: List[AlertChannel] = Field([AlertChannel.DASHBOARD], description="List of channels to send notifications to.")
    notification_recipients: List[str] = Field([], description="List of recipients (e.g., email addresses, Slack channel IDs).")

class AlertRuleResponse(BaseModel):
    id: str

    name: str
    description: Optional[str]
    is_active: bool
    trigger_type: str
    job_type_filter: Optional[str]
    target_url_pattern: Optional[str]
    metric_name: Optional[str]
    threshold_value: Optional[Union[int, float]]
    comparison_operator: Optional[str]
    anomaly_type_filter: Optional[str]
    severity: AlertSeverity
    notification_channels: List[AlertChannel]
    notification_recipients: List[str]
    created_at: datetime
    last_triggered_at: Optional[datetime]
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_alert_rule(cls, rule: AlertRule):
        rule_dict = rule.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**rule_dict)

class ContentGapAnalysisResultResponse(BaseModel): # New Pydantic model for ContentGapAnalysisResult
    target_url: str
    competitor_urls: List[str]
    missing_topics: List[str]
    missing_keywords: List[str]
    content_format_gaps: List[str]
    actionable_insights: List[str]
    analysis_date: datetime
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    @classmethod
    def from_content_gap_analysis_result(cls, result: ContentGapAnalysisResult):
        return cls(**result.to_dict()) # Use to_dict() method

# New: Pydantic models for Link Building
class LinkProspectResponse(BaseModel):
    id: str # Added id
    target_domain: str # Added target_domain
    prospect_url: str # Changed from url
    status: str # Added
    contact_email: Optional[str] = None # Added
    contact_name: Optional[str] = None # Added
    notes: Optional[str] = None # Added
    priority: str # Added
    discovered_date: datetime # Added
    last_contacted: Optional[datetime] = None # Added
    link_acquired_date: Optional[datetime] = None # Added
    prospect_seo_metrics: SEOMetrics = Field(default_factory=SEOMetrics) # Added
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_link_prospect(cls, prospect: LinkProspect):
        prospect_dict = prospect.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        # Handle nested SEOMetrics
        if 'prospect_seo_metrics' in prospect_dict and isinstance(prospect_dict['prospect_seo_metrics'], dict):
            prospect_dict['prospect_seo_metrics'] = SEOMetrics(**prospect_dict['prospect_seo_metrics'])
        return cls(**prospect_dict)

class LinkProspectUpdateRequest(BaseModel):
    status: Optional[str] = None
    last_outreach_date: Optional[datetime] = None
    contact_info: Optional[Dict[str, str]] = None
    reasons: Optional[List[str]] = None
    score: Optional[float] = None

class ProspectIdentificationRequest(BaseModel):
    target_domain: str = Field(..., description="The primary domain for which to find link building prospects.")
    competitor_domains: List[str] = Field(..., description="A list of competitor domains to analyze for backlinks.")
    keywords: List[str] = Field(..., description="A list of keywords to search SERPs for relevant pages.")
    min_domain_authority: float = Field(20.0, description="Minimum domain authority for a prospect to be considered.")
    max_spam_score: float = Field(0.3, description="Maximum spam score for a prospect to be considered.")
    num_serp_results_to_check: int = Field(50, description="Number of SERP results to check for each keyword.")
    num_competitor_backlinks_to_check: int = Field(100, description="Number of competitor backlinks to check for intersect analysis.")

class OutreachCampaignCreateRequest(BaseModel):
    name: str = Field(..., description="Name of the outreach campaign.")
    target_domain: str = Field(..., description="The target domain for this campaign.")
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class OutreachCampaignResponse(BaseModel):
    id: str

    name: str
    target_domain: str
    status: str
    created_date: datetime = Field(..., alias="created_at") # Use created_at from core.models.OutreachCampaign
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    notes: Optional[str] # Added notes
    total_prospects: int # Added total_prospects
    contacts_made: int # Added contacts_made
    replies_received: int # Added replies_received
    links_acquired: int # Added links_acquired
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_outreach_campaign(cls, campaign: OutreachCampaign):
        campaign_dict = campaign.to_dict() # Use to_dict() method
        campaign_dict['created_date'] = campaign_dict.pop('created_at', None) # Map created_at to created_date
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**campaign_dict)

class OutreachEventCreateRequest(BaseModel):
    campaign_id: str
    prospect_id: str # Changed from prospect_url
    event_type: str = Field(..., description="Type of event (e.g., 'email_sent', 'reply_received', 'link_acquired').")
    notes: Optional[str] = None
    success: Optional[bool] = None

class OutreachEventResponse(BaseModel):
    id: str
    campaign_id: str
    prospect_id: str # Changed from prospect_url
    event_type: str
    timestamp: datetime # Changed from event_date
    notes: Optional[str]
    success: Optional[bool]
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_outreach_event(cls, event: OutreachEvent):
        event_dict = event.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**event_dict)

# New: Pydantic models for AI features
class ContentGenerationRequest(BaseModel):
    topic: str = Field(..., description="The topic for which to generate content ideas.")
    num_ideas: int = Field(5, description="Number of content ideas to generate.")

class CompetitorStrategyAnalysisRequest(BaseModel):
    primary_domain: str = Field(..., description="The primary domain for analysis.")
    competitor_domains: List[str] = Field(..., description="List of competitor domains.")

class ReportScheduleRequest(BaseModel):
    report_type: str = Field(..., description="Type of report (e.g., 'link_profile_pdf', 'all_backlinks_excel').")
    target_identifier: str = Field(..., description="Identifier for the report target (e.g., URL, 'all').")
    format: str = Field(..., description="Format of the report (e.g., 'pdf', 'excel').")
    scheduled_at: Optional[datetime] = Field(None, description="Specific UTC datetime to run the report (ISO format).")
    cron_schedule: Optional[str] = Field(None, description="Cron string for recurring reports (e.g., '0 0 * * *').")
    config: Optional[Dict] = Field(None, description="Optional configuration for report generation.")

class ReportJobResponse(BaseModel):
    id: str
    report_type: str
    target_identifier: str
    format: str
    status: CrawlStatus
    created_date: datetime = Field(..., alias="created_at") # Use created_at from core.models.ReportJob
    completed_date: Optional[datetime] = Field(None, alias="completed_at") # Use completed_at from core.models.ReportJob
    file_path: Optional[str] = Field(None, alias="generated_file_path") # Use generated_file_path from core.models.ReportJob
    error_message: Optional[str]
    config: Optional[Dict] # Added config
    scheduled_at: Optional[datetime] = Field(None, alias="scheduled_at") # Added scheduled_at
    cron_schedule: Optional[str] = Field(None, alias="cron_schedule") # Added cron_schedule
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_report_job(cls, job: ReportJob):
        job_dict = job.to_dict() # Use to_dict() method
        job_dict['created_date'] = job_dict.pop('created_at', None) # Map created_at to created_date
        job_dict['completed_date'] = job_dict.pop('completed_at', None) # Map completed_at to completed_date
        job_dict['file_path'] = job_dict.pop('generated_file_path', None) # Map generated_file_path to file_path
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**job_dict)

class DomainHistoryResponse(BaseModel): # New Pydantic model for DomainHistory
    domain_name: str
    snapshot_date: datetime
    authority_score: Optional[float]
    trust_score: Optional[float]
    spam_score: Optional[float]
    total_backlinks: Optional[int]
    referring_domains: Optional[int]
    last_updated: Optional[datetime] = Field(None, alias="last_fetched_at") # New: last_fetched_at

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_domain_history(cls, history: DomainHistory):
        history_dict = history.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**history_dict)

# New: Pydantic models for Queue Endpoints
class QueueStatsResponse(BaseModel):
    pending_jobs: int
    results_pending: int
    active_satellites: int
    satellite_crawlers: Dict[str, Any] # Detailed info about each satellite
    timestamp: datetime

class JobStatusResponse(BaseModel):
    job_id: str
    status: CrawlStatus
    progress_percentage: float
    message: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    results_summary: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime

    class Config:
        use_enum_values = True

class CrawlerHealthResponse(BaseModel):
    crawler_id: str
    status: str
    last_seen: datetime
    cpu_usage: float
    memory_usage: float
    jobs_processed: int
    current_job_id: Optional[str] = None
    current_job_type: Optional[str] = None
    current_job_progress: Optional[float] = None

class SEOMetricsResponse(BaseModel): # New Pydantic model for SEOMetrics
    domain_authority: Optional[int] = None
    page_authority: Optional[int] = None
    trust_flow: Optional[int] = None
    citation_flow: Optional[int] = None
    organic_keywords: Optional[int] = None
    organic_traffic: Optional[int] = None
    referring_domains: Optional[int] = None
    spam_score: Optional[float] = None
    moz_rank: Optional[float] = None
    ahrefs_rank: Optional[int] = None
    semrush_rank: Optional[int] = None
    majestic_trust_flow: Optional[int] = None
    majestic_citation_flow: Optional[int] = None
    
    # Page-level Metrics (from SEOMetricsORM)
    url: Optional[str] = None # Added url
    http_status: Optional[int] = None
    response_time_ms: Optional[float] = None
    page_size_bytes: Optional[int] = None
    title_length: Optional[int] = None
    meta_description_length: Optional[int] = None
    h1_count: Optional[int] = None
    h2_count: Optional[int] = None
    internal_links: Optional[int] = None
    external_links: Optional[int] = None
    images_count: Optional[int] = None
    images_without_alt: Optional[int] = None
    has_canonical: Optional[bool] = None
    has_robots_meta: Optional[bool] = None
    has_schema_markup: Optional[bool] = None
    broken_links: List[str] = Field(default_factory=list)
    performance_score: Optional[float] = None
    mobile_friendly: Optional[bool] = None
    accessibility_score: Optional[float] = None
    audit_timestamp: Optional[datetime] = None
    seo_score: Optional[float] = None
    issues: List[str] = Field(default_factory=list)
    structured_data_types: List[str] = Field(default_factory=list)
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    validation_issues: List[str] = Field(default_factory=list)
    ocr_text: Optional[str] = None
    nlp_entities: List[str] = Field(default_factory=list)
    nlp_sentiment: Optional[str] = None
    nlp_topics: List[str] = Field(default_factory=list)
    video_transcription: Optional[str] = None
    video_topics: List[str] = Field(default_factory=list)
    ai_content_classification: Optional[str] = None # Added
    ai_content_score: Optional[float] = None # Added
    ai_suggestions: List[str] = Field(default_factory=list) # Added
    ai_semantic_keywords: List[str] = Field(default_factory=list) # Added
    ai_readability_score: Optional[float] = None # Added

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        populate_by_name = True # Allow field names to be populated by their alias

    @classmethod
    def from_seo_metrics(cls, metrics: SEOMetrics):
        metrics_dict = metrics.to_dict() # Use to_dict() method
        # Pydantic handles datetime conversion from ISO format string if type hint is datetime
        return cls(**metrics_dict)

# --- Dashboard Specific Schemas ---
class CrawlerMissionStatus(BaseModel):
    active_jobs_count: int
    queued_jobs_count: int
    completed_jobs_24h_count: int
    failed_jobs_24h_count: int
    total_pages_crawled_24h: int
    queue_depth: int
    active_satellites_count: int
    total_satellites_count: int
    satellite_utilization_percentage: float
    avg_job_completion_time_seconds: float
    recent_job_errors: List[CrawlErrorResponse] # Use CrawlErrorResponse for consistency

class BacklinkDiscoveryMetrics(BaseModel):
    total_backlinks_discovered: int
    unique_domains_discovered: int
    new_backlinks_24h: int
    avg_authority_score: float
    top_linking_domains: List[str]
    top_target_urls: List[str]
    potential_spam_links_24h: int

class ApiPerformanceMetrics(BaseModel):
    total_calls: int
    successful_calls: int
    average_response_time_ms: float
    success_rate: float
    circuit_breaker_state: str = "CLOSED" # New: Add circuit breaker state

class ApiQuotaStatus(BaseModel):
    api_name: str
    limit: int
    used: int
    remaining: Optional[int]
    reset_date: str # ISO format string
    percentage_used: float
    status: str # e.g., "OK", "Warning", "Critical"
    predicted_exhaustion_date: Optional[str] = None # ISO format string or null
    recommended_action: Optional[str] = None
    performance: ApiPerformanceMetrics # New: Nested performance metrics

# New Pydantic model for API Key Information
class ApiKeyInfo(BaseModel):
    api_name: str
    enabled: bool
    api_key_masked: str
    monthly_limit: int
    cost_per_unit: float

class DomainIntelligenceMetrics(BaseModel):
    total_domains_analyzed: int
    valuable_expired_domains_found: int
    avg_domain_value_score: float
    new_domains_added_24h: int
    top_niches_identified: List[str]

class PerformanceOptimizationMetrics(BaseModel):
    avg_crawl_speed_pages_per_minute: float
    avg_success_rate_percentage: float
    avg_response_time_ms: float
    bottlenecks_detected: List[str]
    top_performing_satellites: List[str]
    worst_performing_satellites: List[str]

class DashboardAlert(BaseModel): # Renamed from AlertSummary for consistency
    type: str
    severity: AlertSeverity
    message: str
    timestamp: datetime # Added timestamp
    affected_jobs: Optional[List[str]] = None
    recommended_action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True

class SatelliteFleetStatus(BaseModel):
    satellite_id: str
    status: str # e.g., "active", "idle", "unresponsive"
    last_heartbeat: datetime # ISO format string
    jobs_completed_24h: int
    errors_24h: int
    avg_job_duration_seconds: Optional[float] = None
    current_job_id: Optional[str] = None
    current_job_type: Optional[str] = None
    current_job_progress: Optional[float] = None

class DashboardRealtimeUpdates(BaseModel):
    timestamp: str # ISO format string
    crawler_mission_status: CrawlerMissionStatus
    backlink_discovery_metrics: BacklinkDiscoveryMetrics
    api_quota_statuses: List[ApiQuotaStatus]
    domain_intelligence_metrics: DomainIntelligenceMetrics
    performance_optimization_metrics: PerformanceOptimizationMetrics
    alerts: List[DashboardAlert]
    satellite_fleet_status: List[SatelliteFleetStatus]

# New: Pydantic models for System Configuration
class SystemConfigResponse(BaseModel):
    logging_level: str
    api_cache_enabled: bool
    api_cache_ttl: int
    crawler_max_depth: int
    crawler_render_javascript: bool
    # Add other relevant config items here

class SystemConfigUpdate(BaseModel):
    logging_level: Optional[str] = None
    api_cache_enabled: Optional[bool] = None
    api_cache_ttl: Optional[int] = None
    crawler_max_depth: Optional[int] = None
    crawler_render_javascript: Optional[bool] = None
    # Add other relevant config items here

# NEW: Customer Dashboard Summary Schema
class CustomerDashboardSummary(BaseModel):
    total_domains_monitored: int
    avg_domain_authority: Optional[float]
    total_backlinks_discovered: int
    new_backlinks_7d: int
    broken_links_found_7d: int
    api_quota_status: List[ApiQuotaStatus] # User's specific API quotas
    recent_alerts: List[DashboardAlert] # Alerts relevant to the user
    last_updated: datetime
    user_id: str
    organization_id: Optional[str] = None
