import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

# Import from core.models for shared data structures and serialization
from Link_Profiler.core.models import User, Token, serialize_model, CrawlStatus, LinkType, SpamLevel, Domain, CrawlError, SERPResult, KeywordSuggestion, LinkIntersectResult, CompetitiveKeywordAnalysisResult, AlertRule, AlertSeverity, AlertChannel, ContentGapAnalysisResult, DomainHistory, LinkProspect, OutreachCampaign, OutreachEvent, ReportJob, CrawlJob, LinkProfile, Backlink, SEOMetrics # Added SEOMetrics

# Get logger from main.py (assuming main.py sets up logging globally)
# This import is safe as schemas.py does not import main.py at the top level
# in a way that would cause circular dependencies.
try:
    from Link_Profiler.main import logger
except ImportError:
    # Fallback logger if main.py is not yet fully initialized or for testing
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)


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
        user_dict = serialize_model(user)
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
    crawl_web3_content: bool = Field(False, description="Whether to crawl Web3 content (e.g., IPFS, blockchain data).")
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
    initial_seed_urls: List[str] = Field(default_factory=list) # Added initial_seed_urls

    class Config:
        use_enum_values = True # Ensure enums are serialized by value

    @classmethod
    def from_crawl_job(cls, job: CrawlJob):
        job_dict = serialize_model(job)
        
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
                job_dict['started_date'] = datetime.fromisoformat(job_dict['started_date'])
             except ValueError:
                 logger.warning(f"Could_not parse started_date string: {job_dict.get('started_date')}")
                 job_dict['started_date'] = None

        if isinstance(job_dict.get('completed_date'), str):
            try:
                job_dict['completed_date'] = datetime.fromisoformat(job_dict['completed_date'])
            except ValueError:
                logger.warning(f"Could not parse completed_date string: {job_dict.get('completed_date')}")
                job_dict['completed_date'] = None

        job_dict['error_log'] = [CrawlErrorResponse.from_crawl_error(err) for err in job.error_log]
        job_dict['initial_seed_urls'] = job.initial_seed_urls # Ensure initial_seed_urls is passed

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

    class Config:
        use_enum_values = True # Ensure enums are serialized by value

    @classmethod
    def from_backlink(cls, backlink: Backlink):
        backlink_dict = serialize_model(backlink)
        
        # backlink_dict['link_type'] = LinkType(backlink.link_type.value) # Handled by use_enum_values
        # backlink_dict['spam_level'] = SpamLevel(backlink.spam_level.value) # Handled by use_enum_values
        
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

class LinkIntersectRequest(BaseModel):
    primary_domain: str = Field(..., description="The primary domain for analysis (e.g., 'example.com').")
    competitor_domains: List[str] = Field(..., description="A list of competitor domains to compare against (e.g., ['competitor1.com', 'competitor2.com']).")

class LinkIntersectResponse(BaseModel):
    primary_domain: str
    competitor_domains: List[str]
    common_linking_domains: List[str]

    @classmethod
    def from_link_intersect_result(cls, result: LinkIntersectResult):
        return cls(**serialize_model(result))

class CompetitiveKeywordAnalysisRequest(BaseModel):
    primary_domain: str = Field(..., description="The primary domain for which to perform keyword analysis.")
    competitor_domains: List[str] = Field(..., description="A list of competitor domains to compare against.")

class CompetitiveKeywordAnalysisResponse(BaseModel):
    primary_domain: str
    competitor_domains: List[str]
    common_keywords: List[str]
    keyword_gaps: Dict[str, List[str]]
    primary_unique_keywords: List[str]

    @classmethod
    def from_competitive_keyword_analysis_result(cls, result: CompetitiveKeywordAnalysisResult):
        return cls(**serialize_model(result))

# New: Pydantic models for AlertRule management
class AlertRuleCreateRequest(BaseModel):
    name: str = Field(..., description="A unique name for the alert rule.")
    description: Optional[str] = Field(None, description="A brief description of the alert rule.")
    is_active: bool = Field(True, description="Whether the alert rule is active.")
    
    trigger_type: str = Field(..., description="Type of event that triggers the alert (e.g., 'job_status_change', 'metric_threshold', 'anomaly_detected').")
    job_type_filter: Optional[str] = Field(None, description="Optional: Apply rule only to specific job types (e.g., 'backlink_discovery').")
    target_url_pattern: Optional[str] = Field(None, description="Optional: Regex pattern for target URLs to apply the rule to.")
    
    metric_name: Optional[str] = Field(None, description="Optional: Name of the metric to monitor (for 'metric_threshold' trigger_type, e.g., 'seo_score', 'broken_links_count').")
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

    class Config:
        use_enum_values = True # Ensure enums are serialized by value

    @classmethod
    def from_alert_rule(cls, rule: AlertRule):
        rule_dict = serialize_model(rule)
        # Ensure enums are converted to their values for Pydantic
        # rule_dict['severity'] = rule.severity.value # Handled by use_enum_values
        # rule_dict['notification_channels'] = [c.value for c in rule.notification_channels] # Handled by use_enum_values
        
        if isinstance(rule_dict.get('created_at'), str):
            try:
                rule_dict['created_at'] = datetime.fromisoformat(rule_dict['created_at'])
            except ValueError:
                 logger.warning(f"Could not parse created_at string: {rule_dict.get('created_at')}")
                 rule_dict['created_at'] = None
        if isinstance(rule_dict.get('last_triggered_at'), str):
            try:
                rule_dict['last_triggered_at'] = datetime.fromisoformat(rule_dict['last_triggered_at'])
            except ValueError:
                 logger.warning(f"Could not parse last_triggered_at string: {rule_dict.get('last_triggered_at')}")
                 rule_dict['last_triggered_at'] = None
        return cls(**rule_dict)

class ContentGapAnalysisResultResponse(BaseModel): # New Pydantic model for ContentGapAnalysisResult
    target_url: str
    competitor_urls: List[str]
    missing_topics: List[str]
    missing_keywords: List[str]
    content_format_gaps: List[str]
    actionable_insights: List[str]
    analysis_date: datetime

    @classmethod
    def from_content_gap_analysis_result(cls, result: ContentGapAnalysisResult):
        result_dict = serialize_model(result)
        if isinstance(result_dict.get('analysis_date'), str):
            try:
                result_dict['analysis_date'] = datetime.fromisoformat(result_dict['analysis_date'])
            except ValueError:
                logger.warning(f"Could not parse analysis_date string: {result_dict.get('analysis_date')}")
                result_dict['analysis_date'] = None
        return cls(**result_dict)

# New: Pydantic models for Link Building
class LinkProspectResponse(BaseModel):
    url: str
    domain: str
    score: float
    reasons: List[str]
    contact_info: Dict[str, str]
    last_outreach_date: Optional[datetime]
    status: str
    discovered_date: datetime

    @classmethod
    def from_link_prospect(cls, prospect: LinkProspect):
        prospect_dict = serialize_model(prospect)
        if isinstance(prospect_dict.get('last_outreach_date'), str):
            try:
                prospect_dict['last_outreach_date'] = datetime.fromisoformat(prospect_dict['last_outreach_date'])
            except ValueError:
                logger.warning(f"Could not parse last_outreach_date string: {prospect_dict.get('last_outreach_date')}")
                prospect_dict['last_outreach_date'] = None
        if isinstance(prospect_dict.get('discovered_date'), str):
            try:
                prospect_dict['discovered_date'] = datetime.fromisoformat(prospect_dict['discovered_date'])
            except ValueError:
                logger.warning(f"Could not parse discovered_date string: {prospect_dict.get('discovered_date')}")
                prospect_dict['discovered_date'] = None
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
    created_date: datetime
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_outreach_campaign(cls, campaign: OutreachCampaign):
        campaign_dict = serialize_model(campaign)
        if isinstance(campaign_dict.get('created_date'), str):
            campaign_dict['created_date'] = datetime.fromisoformat(campaign_dict['created_date'])
        if isinstance(campaign_dict.get('start_date'), str):
            campaign_dict['start_date'] = datetime.fromisoformat(campaign_dict['start_date'])
        if isinstance(campaign_dict.get('end_date'), str):
            campaign_dict['end_date'] = datetime.fromisoformat(campaign_dict['end_date'])
        return cls(**campaign_dict)

class OutreachEventCreateRequest(BaseModel):
    campaign_id: str
    prospect_url: str
    event_type: str = Field(..., description="Type of event (e.g., 'email_sent', 'reply_received', 'link_acquired').")
    notes: Optional[str] = None
    success: Optional[bool] = None

class OutreachEventResponse(BaseModel):
    id: str
    campaign_id: str
    prospect_url: str
    event_type: str
    event_date: datetime
    notes: Optional[str]
    success: Optional[bool]

    @classmethod
    def from_outreach_event(cls, event: OutreachEvent):
        event_dict = serialize_model(event)
        if isinstance(event_dict.get('event_date'), str):
            event_dict['event_date'] = datetime.fromisoformat(event_dict['event_date'])
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
    created_date: datetime
    completed_date: Optional[datetime]
    file_path: Optional[str]
    error_message: Optional[str]

    class Config:
        use_enum_values = True # Ensure enums are serialized by value

    @classmethod
    def from_report_job(cls, job: ReportJob):
        job_dict = serialize_model(job)
        # job_dict['status'] = job.status.value # Handled by use_enum_values
        if isinstance(job_dict.get('created_date'), str):
            job_dict['created_date'] = datetime.fromisoformat(job_dict['created_date'])
        if isinstance(job_dict.get('completed_date'), str):
            job_dict['completed_date'] = datetime.fromisoformat(job_dict['completed_date'])
        return cls(**job_dict)

class DomainHistoryResponse(BaseModel): # New Pydantic model for DomainHistory
    domain_name: str
    snapshot_date: datetime
    authority_score: float
    trust_score: float
    spam_score: float
    total_backlinks: int
    referring_domains: int

    @classmethod
    def from_domain_history(cls, history: DomainHistory):
        history_dict = serialize_model(history)
        if isinstance(history_dict.get('snapshot_date'), str):
            try:
                history_dict['snapshot_date'] = datetime.fromisoformat(history_dict['snapshot_date'])
            except ValueError:
                logger.warning(f"Could not parse snapshot_date string: {history_dict.get('snapshot_date')}")
                history_dict['snapshot_date'] = None
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
    error_rate: float
    uptime_seconds: float

class SEOMetricsResponse(BaseModel): # New Pydantic model for SEOMetrics
    url: str
    http_status: Optional[int] = None
    response_time_ms: Optional[float] = None
    page_size_bytes: Optional[int] = None
    title_length: int = 0
    meta_description_length: int = 0
    h1_count: int = 0
    h2_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    images_count: int = 0
    images_without_alt: int = 0
    has_canonical: bool = False
    has_robots_meta: bool = False
    has_schema_markup: bool = False
    broken_links: List[str] = Field(default_factory=list)
    performance_score: Optional[float] = None
    mobile_friendly: Optional[bool] = None
    accessibility_score: Optional[float] = None
    audit_timestamp: Optional[datetime] = None
    seo_score: float = 0.0
    issues: List[str] = Field(default_factory=list)
    structured_data_types: List[str] = Field(default_factory=list)
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    validation_issues: List[str] = Field(default_factory=list)
    ai_content_classification: Optional[str] = None
    ai_content_score: Optional[float] = None
    ocr_text: Optional[str] = None
    nlp_entities: List[str] = Field(default_factory=list)
    nlp_sentiment: Optional[str] = None
    nlp_topics: List[str] = Field(default_factory=list)
    video_transcription: Optional[str] = None
    video_topics: List[str] = Field(default_factory=list)
    ai_suggestions: List[str] = Field(default_factory=list)
    ai_semantic_keywords: List[str] = Field(default_factory=list)
    ai_readability_score: Optional[float] = None

    @classmethod
    def from_seo_metrics(cls, metrics: SEOMetrics):
        metrics_dict = serialize_model(metrics)
        if isinstance(metrics_dict.get('audit_timestamp'), str):
            try:
                metrics_dict['audit_timestamp'] = datetime.fromisoformat(metrics_dict['audit_timestamp'])
            except ValueError:
                logger.warning(f"Could not parse audit_timestamp string: {metrics_dict.get('audit_timestamp')}")
                metrics_dict['audit_timestamp'] = None
        return cls(**metrics_dict)
