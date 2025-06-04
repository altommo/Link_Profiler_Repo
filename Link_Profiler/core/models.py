"""
Core Models - Data structures for the Link Profiler system
File: core/models.py
"""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Set, Any, Union
from urllib.parse import urlparse
import json

from pydantic import BaseModel, Field # Import BaseModel and Field from pydantic


# --- Enums ---
# Moved Enum definitions to the top to ensure they are defined before use
class LinkType(enum.Enum):
    """Types of links we can discover"""
    FOLLOW = "follow"
    NOFOLLOW = "nofollow" 
    SPONSORED = "sponsored"
    UGC = "ugc"
    REDIRECT = "redirect"
    CANONICAL = "canonical"


class ContentType(enum.Enum):
    """Types of content we can analyze"""
    HTML = "text/html"
    PDF = "application/pdf"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    OTHER = "other"


class CrawlStatus(enum.Enum):
    """Status of crawling operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class SpamLevel(enum.Enum):
    """Spam classification levels"""
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    LIKELY_SPAM = "likely_spam"
    CONFIRMED_SPAM = "confirmed_spam"


class AlertSeverity(enum.Enum): # Defined here, so it's available for AlertRule
    """Severity levels for alerts."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AlertChannel(enum.Enum): # Defined here, so it's available for AlertRule
    """Supported notification channels for alerts."""
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    DASHBOARD = "dashboard" # For in-app notifications


# Changed CrawlConfig to Pydantic BaseModel and moved its definition up
class CrawlConfig(BaseModel):
    """Configuration for crawling operations"""
    max_depth: int = Field(3, description="Maximum depth to crawl from seed URLs.")
    max_pages: int = Field(1000, description="Maximum number of pages to crawl.")
    delay_seconds: float = Field(1.0, description="Delay between requests to the same domain in seconds.")
    timeout_seconds: int = Field(30, description="Timeout for HTTP requests in seconds.")
    user_agent: str = Field("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", description="Changed default user agent to Googlebot") # Changed default user agent to Googlebot
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
    ml_rate_optimization: bool = Field(False, description="Whether to enable machine learning-based rate optimization for adaptive delays.")
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
    extract_video_content: bool = Field(False, description="Whether to extract and analyze video content") # New: Whether to extract and analyze video content
    job_type: str = Field("unknown", description="The type of job this configuration is for (e.g., 'backlink_discovery', 'technical_audit').") # Added job_type to CrawlConfig

    class Config:
        use_enum_values = True # Ensure enums are serialized by value
        extra = "allow" # Allow extra fields for flexibility if needed

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlConfig':
        return cls(**data)

    def is_domain_allowed(self, domain: str) -> bool:
        """Check if a domain is allowed for crawling based on allowed_domains and blocked_domains."""
        # If allowed_domains is specified, only allow domains in that list
        if self.allowed_domains:
            # Check for exact match or subdomain match
            if domain in self.allowed_domains:
                return True
            for allowed_domain in self.allowed_domains:
                # Handle subdomains: e.g., if allowed_domain is 'example.com', 'sub.example.com' is allowed
                if domain.endswith('.' + allowed_domain) or domain == allowed_domain:
                    return True
            return False # Not in allowed list
        
        # If blocked_domains is specified, block domains in that list
        if self.blocked_domains:
            # Check for exact match or subdomain match
            if domain in self.blocked_domains:
                return False
            for blocked_domain in self.blocked_domains:
                # Handle subdomains: e.g., if blocked_domain is 'example.com', 'sub.example.com' is blocked
                if domain.endswith('.' + blocked_domain) or domain == blocked_domain:
                    return False
            return True # Not in blocked list
        
        # If neither allowed_domains nor blocked_domains are specified, allow all
        return True


# --- Data Models ---
@dataclass
class Domain:
    """Represents a domain with its metrics"""
    name: str
    authority_score: float = 0.0
    trust_score: float = 0.0
    spam_score: float = 0.0
    age_days: Optional[int] = None
    country: Optional[str] = None
    ip_address: Optional[str] = None
    whois_data: Dict = field(default_factory=dict)
    total_pages: int = 0
    total_backlinks: int = 0
    referring_domains: int = 0
    first_seen: Optional[datetime] = None
    last_crawled: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate domain name format"""
        if not self.name or '.' not in self.name:
            raise ValueError(f"Invalid domain name: {self.name}")
    
    @property
    def is_trusted(self) -> bool:
        return self.trust_score > 0.7 and self.spam_score < 0.3
    
    @property
    def tld(self) -> str:
        """Extract top-level domain"""
        return self.name.split('.')[-1]

    @classmethod
    def from_dict(cls, data: Dict) -> 'Domain':
        """Create a Domain instance from a dictionary."""
        # Convert datetime strings back to datetime objects
        if 'first_seen' in data and isinstance(data['first_seen'], str):
            data['first_seen'] = datetime.fromisoformat(data['first_seen'])
        if 'last_crawled' in data and isinstance(data['last_crawled'], str):
            data['last_crawled'] = datetime.fromisoformat(data['last_crawled'])
        
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass 
class URL:
    """Represents a URL with its metadata"""
    url: str
    domain: str = field(init=False)
    path: str = field(init=False)
    title: Optional[str] = None
    description: Optional[str] = None
    content_type: ContentType = ContentType.HTML
    content_length: int = 0
    status_code: Optional[int] = None
    redirect_url: Optional[str] = None
    canonical_url: Optional[str] = None
    last_modified: Optional[datetime] = None
    crawl_status: CrawlStatus = CrawlStatus.PENDING
    crawl_date: Optional[datetime] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Parse URL components"""
        try:
            parsed = urlparse(self.url)
            self.domain = parsed.netloc.lower()
            self.path = parsed.path or '/'
        except Exception as e:
            raise ValueError(f"Invalid URL format: {self.url}") from e
    
    @property
    def is_internal(self) -> bool:
        """Check if URL is internal (same domain)"""
        # This would be set by context in actual usage
        return True
    
    @property
    def is_crawlable(self) -> bool:
        """Check if URL can be crawled"""
        return self.crawl_status in [CrawlStatus.PENDING, CrawlStatus.FAILED]

    @classmethod
    def from_dict(cls, data: Dict) -> 'URL':
        """Create a URL instance from a dictionary."""
        if 'content_type' in data and isinstance(data['content_type'], str):
            data['content_type'] = ContentType(data['content_type'])
        if 'last_modified' in data and isinstance(data['last_modified'], str):
            data['last_modified'] = datetime.fromisoformat(data['last_modified'])
        if 'crawl_status' in data and isinstance(data['crawl_status'], str):
            data['crawl_status'] = CrawlStatus(data['crawl_status'])
        if 'crawl_date' in data and isinstance(data['crawl_date'], str):
            data['crawl_date'] = datetime.fromisoformat(data['crawl_date'])
        
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass
class Backlink:
    """Represents a backlink between two URLs"""
    id: Optional[str] = None
    source_url: str = ""
    target_url: str = ""
    source_domain: str = field(init=False)
    target_domain: str = field(init=False)
    anchor_text: str = ""
    link_type: LinkType = LinkType.FOLLOW
    rel_attributes: List[str] = field(default_factory=list) # New field for all rel values
    context_text: str = ""  # Surrounding text
    position_on_page: int = 0
    is_image_link: bool = False
    alt_text: Optional[str] = None
    discovered_date: datetime = field(default_factory=datetime.now)
    last_seen_date: datetime = field(default_factory=datetime.now)
    authority_passed: float = 0.0
    is_active: bool = True
    spam_level: SpamLevel = SpamLevel.CLEAN
    # New fields for Backlink Data
    http_status: Optional[int] = None # HTTP response code when fetching source_url
    crawl_timestamp: Optional[datetime] = None # UTC timestamp when the page was crawled
    source_domain_metrics: Dict[str, Any] = field(default_factory=dict) # domain-level data such as estimated domain authority or PageRank
    
    def __post_init__(self):
        """Extract domain information from URLs"""
        try:
            parsed = urlparse(self.source_url)
            self.source_domain = parsed.netloc.lower()
            parsed = urlparse(self.target_url)
            self.target_domain = parsed.netloc.lower()
        except Exception:
            pass  # Will be validated elsewhere
    
    @property
    def is_external(self) -> bool:
        """Check if this is an external link"""
        return self.source_domain != self.target_domain
    
    @property
    def passes_authority(self) -> bool:
        """Check if link passes SEO authority"""
        return (self.link_type == LinkType.FOLLOW and 
                self.spam_level == SpamLevel.CLEAN and
                self.is_active)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Backlink':
        """Create a Backlink instance from a dictionary."""
        if 'link_type' in data and isinstance(data['link_type'], str):
            data['link_type'] = LinkType(data['link_type'])
        if 'spam_level' in data and isinstance(data['spam_level'], str):
            data['spam_level'] = SpamLevel(data['spam_level'])
        if 'discovered_date' in data and isinstance(data['discovered_date'], str):
            data['discovered_date'] = datetime.fromisoformat(data['discovered_date'])
        if 'last_seen_date' in data and isinstance(data['last_seen_date'], str):
            data['last_seen_date'] = datetime.fromisoformat(data['last_seen_date'])
        if 'crawl_timestamp' in data and isinstance(data['crawl_timestamp'], str):
            data['crawl_timestamp'] = datetime.fromisoformat(data['crawl_timestamp'])
        
        # Remove 'source_domain' and 'target_domain' from data if present,
        # as they are calculated in __post_init__ and not part of __init__
        data.pop('source_domain', None)
        data.pop('target_domain', None)

        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass
class CrawlResult:
    """Result of a single page crawl"""
    url: str
    status_code: int
    content: Union[str, bytes] = "" # Content can be string (HTML) or bytes (image/pdf)
    headers: Dict[str, str] = field(default_factory=dict)
    links_found: List[Backlink] = field(default_factory=list)
    redirect_url: Optional[str] = None
    error_message: Optional[str] = None
    crawl_time_ms: int = 0
    content_type: str = "text/html"
    seo_metrics: Optional['SEOMetrics'] = None # Use forward reference as SEOMetrics is defined later
    crawl_timestamp: Optional[datetime] = None
    validation_issues: List[str] = field(default_factory=list)
    anomaly_flags: List[str] = field(default_factory=list)
    
    # New fields for overall crawl summary
    pages_crawled: int = 0
    total_links_found: int = 0
    backlinks_found: int = 0 # Count of backlinks found to the target
    failed_urls_count: int = 0 # Count of URLs that failed to crawl
    is_final_summary: bool = False # Flag to indicate if this is the final summary result
    crawl_duration_seconds: float = 0.0
    errors: List['CrawlError'] = field(default_factory=list) # List of CrawlError objects encountered during the crawl

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlResult':
        """Create a CrawlResult instance from a dictionary."""
        if 'crawl_timestamp' in data and isinstance(data['crawl_timestamp'], str):
            data['crawl_timestamp'] = datetime.fromisoformat(data['crawl_timestamp'])
        if 'links_found' in data and isinstance(data['links_found'], list):
            data['links_found'] = [Backlink.from_dict(bl_data) for bl_data in data['links_found']]
        if 'seo_metrics' in data and isinstance(data['seo_metrics'], dict):
            data['seo_metrics'] = SEOMetrics.from_dict(data['seo_metrics'])
        if 'errors' in data and isinstance(data['errors'], list):
            data['errors'] = [CrawlError.from_dict(err_data) for err_data in data['errors']]
        
        # Handle content which might be bytes but serialized as string
        if 'content' in data and isinstance(data['content'], str) and data.get('content_type') != 'text/html':
            try:
                data['content'] = data['content'].encode('latin-1') # Or appropriate encoding
            except Exception:
                pass # Keep as string if encoding fails

        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass
class LinkProfile:
    """Complete link profile for a domain or URL"""
    target_url: str
    target_domain: str = field(init=False)
    total_backlinks: int = 0
    unique_domains: int = 0
    dofollow_links: int = 0
    nofollow_links: int = 0
    authority_score: float = 0.0
    trust_score: float = 0.0
    spam_score: float = 0.0
    anchor_text_distribution: Dict[str, int] = field(default_factory=dict)
    referring_domains: Set[str] = field(default_factory=set)
    backlinks: List[Backlink] = field(default_factory=list)
    top_pages: List[str] = field(default_factory=list)
    analysis_date: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Extract target domain"""
        try:
            parsed = urlparse(self.target_url)
            self.target_domain = parsed.netloc.lower()
        except Exception:
            pass
    
    def add_backlink(self, backlink: Backlink) -> None:
        """Add a backlink to the profile"""
        self.backlinks.append(backlink)
        self.referring_domains.add(backlink.source_domain)
        
        # Update anchor text distribution
        if backlink.anchor_text:
            self.anchor_text_distribution[backlink.anchor_text] = \
                self.anchor_text_distribution.get(backlink.anchor_text, 0) + 1
    
    # Removed calculate_metrics method. This logic will be handled in the service layer.

    @classmethod
    def from_dict(cls, data: Dict) -> 'LinkProfile':
        """Create a LinkProfile instance from a dictionary."""
        if 'analysis_date' in data and isinstance(data['analysis_date'], str):
            data['analysis_date'] = datetime.fromisoformat(data['analysis_date'])
        if 'referring_domains' in data and isinstance(data['referring_domains'], list):
            data['referring_domains'] = set(data['referring_domains'])
        if 'backlinks' in data and isinstance(data['backlinks'], list):
            data['backlinks'] = [Backlink.from_dict(bl_data) for bl_data in data['backlinks']]
        
        # Remove 'target_domain' from data if present,
        # as it is calculated in __post_init__ and not part of __init__
        data.pop('target_domain', None)

        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass
class LinkIntersectResult:
    """Result of a link intersect analysis."""
    primary_domain: str
    competitor_domains: List[str]
    common_linking_domains: List[str] = field(default_factory=list)


@dataclass
class CompetitiveKeywordAnalysisResult:
    """Result of a competitive keyword analysis."""
    primary_domain: str

    competitor_domains: List[str]
    common_keywords: List[str] = field(default_factory=list)
    keyword_gaps: Dict[str, List[str]] = field(default_factory=dict) # competitor_domain -> keywords they rank for, but primary doesn't
    primary_unique_keywords: List[str] = field(default_factory=list) # keywords primary ranks for, but competitors don't


@dataclass
class ContentGapAnalysisResult:
    """Result of a content gap analysis."""
    target_url: str
    competitor_urls: List[str]
    missing_topics: List[str] = field(default_factory=list)
    missing_keywords: List[str] = field(default_factory=list)
    content_format_gaps: List[str] = field(default_factory=list)
    actionable_insights: List[str] = field(default_factory=list)
    analysis_date: datetime = field(default_factory=datetime.now)


@dataclass
class CrawlError:
    """Represents a structured error encountered during crawling."""
    timestamp: datetime = field(default_factory=datetime.now)
    url: str = ""
    error_type: str = "UnknownError"
    message: str = "An unexpected error occurred."
    details: Optional[str] = None # e.g., traceback, specific API error message

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlError':
        """Create a CrawlError instance from a dictionary."""
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class CrawlJob:
    """Represents a crawling job"""
    id: str
    target_url: str
    job_type: str  # 'backlinks', 'seo_audit', 'competitor_analysis', 'serp_analysis', 'keyword_research', 'domain_analysis', 'full_seo_audit', 'web3_crawl', 'social_media_crawl', 'video_analysis'
    status: CrawlStatus = CrawlStatus.PENDING
    priority: int = 5  # 1-10, higher = more priority
    created_date: datetime = field(default_factory=datetime.now)
    started_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    progress_percentage: float = 0.0
    urls_discovered: int = 0
    urls_crawled: int = 0
    links_found: int = 0
    errors_count: int = 0
    config: CrawlConfig = field(default_factory=CrawlConfig) # Configuration specific to this job
    results: Dict = field(default_factory=dict)
    error_log: List[CrawlError] = field(default_factory=list) # Changed to List[CrawlError]
    anomalies_detected: List[str] = field(default_factory=list) # New: List of detected anomalies for the job
    initial_seed_urls: List[str] = field(default_factory=list) # New: Initial seed URLs for the crawl job
    
    # New fields for scheduling
    scheduled_at: Optional[datetime] = None # When the job should be moved to the active queue
    cron_schedule: Optional[str] = None # Cron string for recurring jobs (e.g., "0 0 * * *")
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration"""
        if self.started_date and self.completed_date:
            return (self.completed_date - self.started_date).total_seconds()
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if job is completed"""
        return self.status in [CrawlStatus.COMPLETED, CrawlStatus.FAILED, CrawlStatus.STOPPED, CrawlStatus.CANCELLED] # Added STOPPED and CANCELLED
    
    def add_error(self, url: str, error_type: str, message: str, details: Optional[str] = None) -> None:
        """Add a structured error to the job log"""
        error = CrawlError(url=url, error_type=error_type, message=message, details=details)
        self.error_log.append(error)
        self.errors_count += 1

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlJob':
        """Create a CrawlJob instance from a dictionary."""
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = CrawlStatus(data['status'])
        if 'created_date' in data and isinstance(data['created_date'], str):
            data['created_date'] = datetime.fromisoformat(data['created_date'])
        if 'started_date' in data and isinstance(data['started_date'], str):
            data['started_date'] = datetime.fromisoformat(data['started_date'])
        if 'completed_date' in data and isinstance(data['completed_date'], str):
            data['completed_date'] = datetime.fromisoformat(data['completed_date'])
        if 'scheduled_at' in data and isinstance(data['scheduled_at'], str):
            data['scheduled_at'] = datetime.fromisoformat(data['scheduled_at'])
        
        # Deserialize error_log
        if 'error_log' in data and isinstance(data['error_log'], list):
            data['error_log'] = [CrawlError.from_dict(err_data) for err_data in data['error_log']]
        
        # Deserialize config
        if 'config' in data and isinstance(data['config'], dict):
            data['config'] = CrawlConfig.from_dict(data['config'])
        elif 'config' in data and isinstance(data['config'], CrawlConfig): # If it's already a CrawlConfig object
            pass # No conversion needed
        else: # Default to empty CrawlConfig if not present or invalid
            data['config'] = CrawlConfig()

        # Ensure anomalies_detected is a list
        if 'anomalies_detected' in data and data['anomalies_detected'] is None:
            data['anomalies_detected'] = []
        
        # Ensure initial_seed_urls is a list
        if 'initial_seed_urls' in data and data['initial_seed_urls'] is None:
            data['initial_seed_urls'] = []

        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass 
class SEOMetrics:
    """SEO metrics for a URL or domain"""
    url: str
    # Page-level Metrics (for each page crawled)
    http_status: Optional[int] = None # HTTP response code
    response_time_ms: Optional[float] = None # Time to first byte and full load
    page_size_bytes: Optional[int] = None # Total HTML size
    # SEO Checks
    title_length: int = 0
    meta_description_length: int = 0 # Renamed from description_length
    h1_count: int = 0
    h2_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    images_count: int = 0
    images_without_alt: int = 0
    has_canonical: bool = False
    has_robots_meta: bool = False
    has_schema_markup: bool = False
    broken_links: List[str] = field(default_factory=list) # List of internal/external links returning 4xx/5xx
    # Performance & Best Practices (optional with Lighthouse CI)
    performance_score: Optional[float] = None # 0–100
    mobile_friendly: Optional[bool] = None # Boolean or score
    accessibility_score: Optional[float] = None # 0–100
    audit_timestamp: Optional[datetime] = None # UTC timestamp of audit execution
    # Existing fields
    seo_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    
    # New fields for content quality and completeness
    structured_data_types: List[str] = field(default_factory=list) # e.g., ["Article", "FAPage"]
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    validation_issues: List[str] = field(default_factory=list) # Issues found by ContentValidator
    ai_content_classification: Optional[str] = None # New: AI-driven content classification (e.g., "high_quality", "spam")
    ai_content_score: Optional[float] = None # New: AI-driven content quality score (0-100)
    ocr_text: Optional[str] = None # New: Extracted text from images via OCR
    nlp_entities: List[str] = field(default_factory=list) # New: Entities extracted via NLP
    nlp_sentiment: Optional[str] = None # New: Sentiment extracted via NLP (positive, neutral, negative)
    nlp_topics: List[str] = field(default_factory=list) # New: Main topics extracted via NLP
    video_transcription: Optional[str] = None # New: Transcription of video content
    video_topics: List[str] = field(default_factory=list) # New: Topics extracted from video content

    # AI-generated insights
    ai_suggestions: List[str] = field(default_factory=list) # AI-generated improvement suggestions
    ai_semantic_keywords: List[str] = field(default_factory=list) # AI-identified semantic keywords
    ai_readability_score: Optional[float] = None # AI-assessed readability score

    def calculate_seo_score(self) -> float:
        """Calculate overall SEO score"""
        score = 100.0
        
        # Title optimization
        if self.title_length == 0:
            score -= 15
        elif self.title_length > 60:
            score -= 5
            
        # Description optimization  
        if self.meta_description_length == 0: # Changed to meta_description_length
            score -= 10
        elif self.meta_description_length > 160:
            score -= 3
            
        # Headers
        if self.h1_count == 0:
            score -= 10
        elif self.h1_count > 1:
            score -= 5
            
        # Images
        if self.images_count > 0 and self.images_without_alt > 0:
            score -= (self.images_without_alt / self.images_count) * 10
            
        # Technical SEO
        if not self.has_canonical:
            score -= 5
        # SSL Enabled (this can't be determined from HTML content alone, needs HTTP response info)
        # For now, we'll assume it's true if the URL scheme is https
        # Removed ssl_enabled from here, as it's not directly from content parsing.
        # It should be part of the URL model or passed in from the crawler.
        
        # New SEO checks
        if self.broken_links:
            score -= len(self.broken_links) * 5 # Penalty for broken links
        if self.performance_score is not None:
            score -= (100 - self.performance_score) * 0.1 # Scale 0-100 to 0-1 penalty
        if self.mobile_friendly is False:
            score -= 15
        if self.accessibility_score is not None:
            score -= (100 - self.accessibility_score) * 0.05 # Smaller adjustment for accessibility

        # AI-driven score adjustments
        if self.ai_content_score is not None:
            score += (self.ai_content_score - 50) * 0.1 # Adjust based on AI score, e.g., +5 for 100, -5 for 0
        if self.ai_readability_score is not None:
            score += (self.ai_readability_score - 50) * 0.05 # Smaller adjustment for readability
        
        # AI content classification adjustment
        if self.ai_content_classification == "spam":
            score -= 30
        elif self.ai_content_classification == "low_quality":
            score -= 10
        elif self.ai_content_classification == "irrelevant":
            score -= 5

        # Penalize for validation issues
        if self.validation_issues:
            score -= len(self.validation_issues) * 2 # Small penalty per validation issue

        self.seo_score = max(0.0, score)
        return self.seo_score

    @classmethod
    def from_dict(cls, data: Dict) -> 'SEOMetrics':
        """Create a SEOMetrics instance from a dictionary."""
        if 'audit_timestamp' in data and isinstance(data['audit_timestamp'], str):
            data['audit_timestamp'] = datetime.fromisoformat(data['audit_timestamp'])
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass
class SERPResult:
    """Represents a single search engine results page (SERP) entry."""
    keyword: str
    position: int
    result_url: str
    title_text: str
    snippet_text: Optional[str] = None
    rich_features: List[str] = field(default_factory=list) # Flags or details for featured snippets, local packs, etc.
    page_load_time: Optional[float] = None # Time to fully render the SERP page
    crawl_timestamp: datetime = field(default_factory=datetime.now) # UTC timestamp of when the search was performed

    @classmethod
    def from_dict(cls, data: Dict) -> 'SERPResult':
        """Create a SERPResult instance from a dictionary."""
        if 'crawl_timestamp' in data and isinstance(data['crawl_timestamp'], str):
            data['crawl_timestamp'] = datetime.fromisoformat(data['crawl_timestamp'])
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass
class KeywordSuggestion:
    """Represents a keyword suggestion from a research tool."""
    seed_keyword: str
    suggested_keyword: str
    search_volume_monthly: Optional[int] = None
    cpc_estimate: Optional[float] = None # Cost-per-click estimate
    keyword_trend: List[float] = field(default_factory=list) # JSON array of monthly interest values
    competition_level: Optional[str] = None # Low/Medium/High
    data_timestamp: datetime = field(default_factory=datetime.now) # UTC when this data was gathered

    @classmethod
    def from_dict(cls, data: Dict) -> 'KeywordSuggestion':
        """Create a KeywordSuggestion instance from a dictionary."""
        if 'data_timestamp' in data and isinstance(data['data_timestamp'], str):
            data['data_timestamp'] = datetime.fromisoformat(data['data_timestamp'])
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


# New: Alerting Models
# AlertSeverity and AlertChannel are defined above CrawlJob and CrawlConfig
# to ensure they are available when CrawlJob and CrawlConfig are defined.
# This resolves the F821 errors.

@dataclass
class AlertRule:
    """Defines a rule for triggering alerts based on job or metric conditions."""
    name: str
    trigger_type: str # e.g., "job_status_change", "metric_threshold", "anomaly_detected"
    id: Optional[str] = None # UUID for the rule
    description: Optional[str] = None
    is_active: bool = True
    
    job_type_filter: Optional[str] = None # Apply rule only to specific job types (e.g., "backlink_discovery")
    target_url_pattern: Optional[str] = None # Regex pattern for target URLs
    
    # Metric-based conditions (for "metric_threshold" trigger_type)
    metric_name: Optional[str] = None # e.g., "seo_score", "broken_links_count", "crawl_errors_rate"
    threshold_value: Optional[Union[int, float]] = None
    comparison_operator: Optional[str] = None # e.g., ">", "<", ">=", "<=", "=="
    
    # Anomaly-based conditions (for "anomaly_detected" trigger_type)
    anomaly_type_filter: Optional[str] = None # e.g., "captcha_spike", "crawl_rate_drop", "content_quality_drop"
    
    severity: AlertSeverity = AlertSeverity.WARNING
    notification_channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.DASHBOARD])
    notification_recipients: List[str] = field(default_factory=list) # e.g., email addresses, Slack channel IDs, webhook URLs (if not global)
    
    created_at: datetime = field(default_factory=datetime.now)
    last_triggered_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'AlertRule':
        """Create an AlertRule instance from a dictionary."""
        if 'severity' in data and isinstance(data['severity'], str):
            data['severity'] = AlertSeverity(data['severity'])
        if 'notification_channels' in data and isinstance(data['notification_channels'], str): # Changed from list to str for single channel
            data['notification_channels'] = [AlertChannel(c) for c in data['notification_channels'].split(',')] # Split string to list of enums
        elif 'notification_channels' in data and isinstance(data['notification_channels'], list): # Keep existing list handling
            data['notification_channels'] = [AlertChannel(c) for c in data['notification_channels']]
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'last_triggered_at' in data and isinstance(data['last_triggered_at'], str):
            data['last_triggered_at'] = datetime.fromisoformat(data['last_triggered_at'])
        
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


# New: Authentication Models
@dataclass
class User:
    """Represents a user in the system."""
    username: str
    email: str
    hashed_password: str
    id: Optional[str] = None # UUID for the user
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """Create a User instance from a dictionary."""
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)

@dataclass
class Token:
    """Represents a JWT token."""
    access_token: str
    token_type: str = "bearer"

@dataclass
class TokenData:
    """Represents data contained within a JWT token."""
    username: Optional[str] = None

@dataclass
class DomainHistory:
    """Represents a historical snapshot of a domain's metrics."""
    domain_name: str
    snapshot_date: datetime = field(default_factory=datetime.now)
    authority_score: float = 0.0
    trust_score: float = 0.0
    spam_score: float = 0.0
    total_backlinks: int = 0
    referring_domains: int = 0

    @classmethod
    def from_dict(cls, data: Dict) -> 'DomainHistory':
        """Create a DomainHistory instance from a dictionary."""
        if 'snapshot_date' in data and isinstance(data['snapshot_date'], str):
            data['snapshot_date'] = datetime.fromisoformat(data['snapshot_date'])
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)

@dataclass
class LinkProspect:
    """Represents a potential link building opportunity."""
    url: str
    domain: str = field(init=False)
    score: float = 0.0 # Calculated score for prospect quality/relevance
    reasons: List[str] = field(default_factory=list) # Reasons for the score/identification
    contact_info: Dict[str, str] = field(default_factory=dict) # e.g., {'email': '...', 'twitter': '...'}
    last_outreach_date: Optional[datetime] = None
    status: str = "identified" # e.g., "identified", "contacted", "rejected", "acquired"
    discovered_date: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Parse domain from URL."""
        try:
            parsed = urlparse(self.url)
            self.domain = parsed.netloc.lower()
        except Exception:
            self.domain = "" # Handle invalid URL gracefully

    @classmethod
    def from_dict(cls, data: Dict) -> 'LinkProspect':
        """Create a LinkProspect instance from a dictionary."""
        if 'last_outreach_date' in data and isinstance(data['last_outreach_date'], str):
            data['last_outreach_date'] = datetime.fromisoformat(data['last_outreach_date'])
        if 'discovered_date' in data and isinstance(data['discovered_date'], str):
            data['discovered_date'] = datetime.fromisoformat(data['discovered_date'])
        
        # Remove 'domain' from data if present, as it is calculated in __post_init__
        data.pop('domain', None)

        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)

@dataclass
class OutreachCampaign:
    """Represents a link building outreach campaign."""
    id: str
    name: str
    target_domain: str
    status: str = "active" # e.g., "active", "completed", "paused"
    created_date: datetime = field(default_factory=datetime.now)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict) # e.g., {'emails_sent': 100, 'replies': 20, 'links_acquired': 5}

    @classmethod
    def from_dict(cls, data: Dict) -> 'OutreachCampaign':
        """Create an OutreachCampaign instance from a dictionary."""
        if 'created_date' in data and isinstance(data['created_date'], str):
            data['created_date'] = datetime.fromisoformat(data['created_date'])
        if 'start_date' in data and isinstance(data['start_date'], str):
            data['start_date'] = datetime.fromisoformat(data['start_date'])
        if 'end_date' in data and isinstance(data['end_date'], str):
            data['end_date'] = datetime.fromisoformat(data['end_date'])
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)

@dataclass
class OutreachEvent:
    """Represents a single event within an outreach campaign."""
    id: str
    campaign_id: str
    prospect_url: str
    event_type: str # e.g., "email_sent", "reply_received", "link_acquired", "rejected"
    event_date: datetime = field(default_factory=datetime.now)
    notes: Optional[str] = None
    success: Optional[bool] = None # True if positive outcome (e.g., link acquired, positive reply)

    @classmethod
    def from_dict(cls, data: Dict) -> 'OutreachEvent':
        """Create an OutreachEvent instance from a dictionary."""
        if 'event_date' in data and isinstance(data['event_date'], str):
            data['event_date'] = datetime.fromisoformat(data['event_date'])
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)

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
