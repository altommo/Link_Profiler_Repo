import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Union
from pydantic import BaseModel, Field, validator
from urllib.parse import urlparse # Import urlparse
import json
from collections import defaultdict # Added missing import

# Helper function for serialization
def serialize_model(obj: Any) -> Any:
    """
    Recursively converts dataclass instances and Enums to dictionaries/strings.
    Handles datetime objects by converting them to ISO format strings.
    """
    if isinstance(obj, (datetime)):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (list, tuple, set)):
        return [serialize_model(item) for item in obj]
    if isinstance(obj, dict):
        return {k: serialize_model(v) for k, v in obj.items()}
    if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
        return obj.to_dict()
    if hasattr(obj, '__dict__'):
        return {k: serialize_model(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
    return obj

# Enums
class LinkType(str, enum.Enum):
    DOFOLLOW = "dofollow"
    NOFOLLOW = "nofollow"
    UGC = "ugc"
    SPONSORED = "sponsored"
    INTERNAL = "internal"
    EXTERNAL = "external"
    BROKEN = "broken"
    CANONICAL = "canonical" # Added
    REDIRECT = "redirect" # Added

class ContentType(str, enum.Enum):
    HTML = "html"
    PDF = "pdf"
    IMAGE = "image"
    VIDEO = "video"
    OTHER = "other"

class CrawlStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    STOPPED = "stopped"
    CANCELLED = "cancelled"
    QUEUED = "queued" # New status for jobs in Redis queue

class SpamLevel(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class AlertSeverity(str, enum.Enum): # Defined here, so it's available for AlertRule
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AlertChannel(str, enum.Enum): # Defined here, so it's available for AlertRule
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    DASHBOARD = "dashboard"

# Pydantic Models for Configuration
class CrawlConfig(BaseModel):
    """Configuration for crawling operations"""
    max_depth: int = 3
    max_pages: int = 1000
    delay_seconds: float = 1.0
    user_agent: str = "LinkProfilerBot/1.0"
    respect_robots_txt: bool = True
    follow_redirects: bool = True
    extract_images: bool = False
    extract_pdfs: bool = False
    allowed_domains: Set[str] = Field(default_factory=set)
    disallowed_paths: List[str] = Field(default_factory=list)
    request_timeout: int = 30
    enable_javascript: bool = False # For headless browser crawling
    screenshot_pages: bool = False # For headless browser crawling
    proxy: Optional[str] = None # Proxy URL for this job
    custom_headers: Dict[str, str] = Field(default_factory=dict)
    enable_rate_limiting: bool = True
    rate_limit_rps: float = 1.0
    enable_anti_detection: bool = False
    capture_har: bool = False # Capture HTTP Archive (HAR) data
    # New fields for anti-detection and browser-based crawling
    user_agent_rotation: bool = False
    request_header_randomization: bool = False
    human_like_delays: bool = False
    stealth_mode: bool = False
    browser_fingerprint_randomization: bool = False
    captcha_solving_enabled: bool = False
    anomaly_detection_enabled: bool = False
    use_proxies: bool = False
    proxy_list: Optional[List[Dict[str, str]]] = None
    proxy_region: Optional[str] = None
    render_javascript: bool = False
    browser_type: Optional[str] = "chromium"
    headless_browser: bool = True
    extract_image_text: bool = False
    crawl_web3_content: bool = False
    crawl_social_media: bool = False
    job_type: str = "unknown"
    ml_rate_limiter_enabled: bool = False # From rate_limiting.ml_enhanced

    def is_domain_allowed(self, domain: str) -> bool:
        if not self.allowed_domains: # If allowed_domains is empty, all are allowed
            return True
        return domain in self.allowed_domains

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlConfig':
        # Convert 'allowed_domains' from list to set if it's a list
        if 'allowed_domains' in data and isinstance(data['allowed_domains'], list):
            data['allowed_domains'] = set(data['allowed_domains'])
        return cls(**data)

# Dataclasses for Data Models
@dataclass
class SEOMetrics:
    """SEO metrics for a URL or domain"""
    domain_authority: Optional[int] = None
    page_authority: Optional[int] = None
    trust_flow: Optional[int] = None
    citation_flow: Optional[int] = None
    organic_keywords: Optional[int] = None
    organic_traffic: Optional[int] = None
    referring_domains: Optional[int] = None
    spam_score: Optional[float] = None # 0-1 range, higher is worse
    moz_rank: Optional[float] = None
    ahrefs_rank: Optional[int] = None
    semrush_rank: Optional[int] = None
    majestic_trust_flow: Optional[int] = None
    majestic_citation_flow: Optional[int] = None
    # Add more as needed from various SEO tools

    # New fields from TechnicalAuditor
    url: Optional[str] = None # The URL this SEOMetrics object refers to
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
    broken_links: List[str] = field(default_factory=list)
    performance_score: Optional[float] = None # Lighthouse Performance score (0-100)
    mobile_friendly: Optional[bool] = None
    accessibility_score: Optional[float] = None # Lighthouse Accessibility score (0-100)
    audit_timestamp: Optional[datetime] = None # When the audit was run
    seo_score: Optional[float] = None # Overall SEO score (0-100)
    issues: List[str] = field(default_factory=list) # List of identified issues
    structured_data_types: List[str] = field(default_factory=list) # e.g., "Article", "Product"
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    twitter_title: Optional[str] = None
    twitter_description: Optional[str] = None
    validation_issues: List[str] = field(default_factory=list) # Issues from ContentValidator
    ocr_text: Optional[str] = None # Extracted text from images via OCR
    nlp_entities: List[str] = field(default_factory=list) # Entities extracted via NLP
    nlp_sentiment: Optional[str] = None # Sentiment extracted via NLP (positive, neutral, negative)
    nlp_topics: List[str] = field(default_factory=list) # Main topics extracted via NLP
    video_transcription: Optional[str] = None # Transcription from video analysis
    video_topics: List[str] = field(default_factory=list) # Topics from video analysis
    ai_content_classification: Optional[str] = None # AI classification of content quality
    ai_content_score: Optional[float] = None # AI-generated content score
    ai_suggestions: List[str] = field(default_factory=list) # AI-generated suggestions
    ai_semantic_keywords: List[str] = field(default_factory=list) # AI-generated semantic keywords
    ai_readability_score: Optional[float] = None # AI-generated readability score
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def calculate_seo_score(self):
        """Calculates an overall SEO score based on available metrics."""
        weights = {
            'performance_score': 0.3,
            'accessibility_score': 0.2,
            'title_length': 0.1,
            'meta_description_length': 0.1,
            'h1_count': 0.05,
            'has_canonical': 0.05,
            'has_robots_meta': 0.05,
            'has_schema_markup': 0.05,
            'broken_links': -0.1, # Penalty
            'ai_content_score': 0.1 # AI content score contribution
        }
        
        score = 0.0
        
        # Normalize and add scores
        if self.performance_score is not None:
            score += (self.performance_score / 100) * weights['performance_score']
        if self.accessibility_score is not None:
            score += (self.accessibility_score / 100) * weights['accessibility_score']
        if self.title_length is not None:
            # Optimal title length is 30-60 chars. Score based on proximity to this range.
            if 30 <= self.title_length <= 60:
                score += weights['title_length']
            elif self.title_length > 0: # Some title is better than none
                score += weights['title_length'] * 0.5
        if self.meta_description_length is not None:
            # Optimal meta description length is 50-160 chars.
            if 50 <= self.meta_description_length <= 160:
                score += weights['meta_description_length']
            elif self.meta_description_length > 0:
                score += weights['meta_description_length'] * 0.5
        if self.h1_count is not None:
            if self.h1_count == 1:
                score += weights['h1_count']
            elif self.h1_count > 1: # Multiple H1s are a minor issue
                score += weights['h1_count'] * 0.5
        if self.has_canonical is not None and self.has_canonical:
            score += weights['has_canonical']
        if self.has_robots_meta is not None and self.has_robots_meta:
            score += weights['has_robots_meta']
        if self.has_schema_markup is not None and self.has_schema_markup:
            score += weights['has_schema_markup']
        if self.broken_links:
            score += weights['broken_links'] # Apply penalty if broken links exist
        if self.ai_content_score is not None:
            score += (self.ai_content_score / 100) * weights['ai_content_score']

        # Scale to 0-100
        self.seo_score = max(0, min(100, score * 100 / sum(abs(w) for w in weights.values()))) # Normalize by sum of absolute weights

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'SEOMetrics':
        if 'audit_timestamp' in data and isinstance(data['audit_timestamp'], str):
            data['audit_timestamp'] = datetime.fromisoformat(data['audit_timestamp'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class Domain:
    """Represents a domain with its metrics"""
    name: str
    authority_score: Optional[float] = None # General score (e.g., 0-100)
    trust_score: Optional[float] = None # General score (e.g., 0-1)
    spam_score: Optional[float] = None # General score (e.g., 0-1)
    registered_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    registrar: Optional[str] = None
    is_registered: Optional[bool] = None
    is_parked: Optional[bool] = None
    is_dead: Optional[bool] = None
    whois_raw: Optional[str] = None # Raw WHOIS data
    dns_records: Dict[str, List[str]] = field(default_factory=dict) # e.g., {"A": ["1.2.3.4"], "MX": ["mail.example.com"]}
    ip_address: Optional[str] = None
    country: Optional[str] = None # Country of registrant or IP location
    seo_metrics: SEOMetrics = field(default_factory=SEOMetrics) # Nested SEO metrics
    last_checked: datetime = field(default_factory=datetime.now)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        data = {k: serialize_model(v) for k, v in self.__dict__.items()}
        # Ensure seo_metrics is a dict, not a SEOMetrics object
        if isinstance(data.get('seo_metrics'), SEOMetrics):
            data['seo_metrics'] = data['seo_metrics'].to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'Domain':
        # Handle nested SEOMetrics
        if 'seo_metrics' in data and isinstance(data['seo_metrics'], dict):
            data['seo_metrics'] = SEOMetrics.from_dict(data['seo_metrics'])
        # Handle datetime objects
        if 'registered_date' in data and isinstance(data['registered_date'], str):
            data['registered_date'] = datetime.fromisoformat(data['registered_date'])
        if 'expiration_date' in data and isinstance(data['expiration_date'], str):
            data['expiration_date'] = datetime.fromisoformat(data['expiration_date'])
        if 'last_checked' in data and isinstance(data['last_checked'], str):
            data['last_checked'] = datetime.fromisoformat(data['last_checked'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass 
class URL:
    """Represents a URL with its metadata"""
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[ContentType] = None
    word_count: Optional[int] = None
    internal_links: List[str] = field(default_factory=list)
    external_links: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    canonical_url: Optional[str] = None
    meta_robots: Optional[str] = None # e.g., "noindex, nofollow"
    load_time_ms: Optional[int] = None
    is_indexed: Optional[bool] = None # From GSC or similar
    last_crawled: datetime = field(default_factory=datetime.now)
    html_content_hash: Optional[str] = None # MD5 hash of the HTML content
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'URL':
        if 'content_type' in data and isinstance(data['content_type'], str):
            data['content_type'] = ContentType(data['content_type'])
        if 'last_crawled' in data and isinstance(data['last_crawled'], str):
            data['last_crawled'] = datetime.fromisoformat(data['last_crawled'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class Backlink:
    """Represents a backlink between two URLs"""
    source_url: str
    target_url: str
    anchor_text: str
    link_type: LinkType = LinkType.EXTERNAL # Default to external
    nofollow: bool = False
    ugc: bool = False
    sponsored: bool = False
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    source_domain: Optional[str] = None
    target_domain: Optional[str] = None
    # SEO metrics of the source page/domain at the time of discovery
    source_page_authority: Optional[int] = None
    source_domain_authority: Optional[int] = None
    rel_attributes: List[str] = field(default_factory=list) # Added rel_attributes
    context_text: Optional[str] = None # Added context_text
    spam_level: Optional[SpamLevel] = None # Added spam_level
    http_status: Optional[int] = None # Added http_status
    crawl_timestamp: Optional[datetime] = None # Added crawl_timestamp
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def __post_init__(self):
        # Automatically set source_domain and target_domain
        if self.source_url and not self.source_domain:
            self.source_domain = urlparse(self.source_url).netloc
        if self.target_url and not self.target_domain:
            self.target_domain = urlparse(self.target_url).netloc

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'Backlink':
        if 'link_type' in data and isinstance(data['link_type'], str):
            data['link_type'] = LinkType(data['link_type'])
        if 'first_seen' in data and isinstance(data['first_seen'], str):
            data['first_seen'] = datetime.fromisoformat(data['first_seen'])
        if 'last_seen' in data and isinstance(data['last_seen'], str):
            data['last_seen'] = datetime.fromisoformat(data['last_seen'])
        if 'spam_level' in data and isinstance(data['spam_level'], str):
            data['spam_level'] = SpamLevel(data['spam_level'])
        if 'crawl_timestamp' in data and isinstance(data['crawl_timestamp'], str):
            data['crawl_timestamp'] = datetime.fromisoformat(data['crawl_timestamp'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class CrawlResult:
    """Result of a single page crawl"""
    url: str
    status_code: int
    content_type: ContentType
    html_content: Optional[str] = None
    links_found: List[Backlink] = field(default_factory=list)
    images_found: List[str] = field(default_factory=list)
    load_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict) # For any extra data
    seo_metrics: Optional[SEOMetrics] = None # Added seo_metrics
    anomaly_flags: List[str] = field(default_factory=list) # New: List of detected anomalies for this crawl result
    validation_issues: List[str] = field(default_factory=list) # New: Issues from content validator

    def to_dict(self) -> Dict[str, Any]:
        data = {k: serialize_model(v) for k, v in self.__dict__.items()}
        if isinstance(data.get('seo_metrics'), SEOMetrics):
            data['seo_metrics'] = data['seo_metrics'].to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlResult':
        if 'content_type' in data and isinstance(data['content_type'], str):
            data['content_type'] = ContentType(data['content_type'])
        if 'links_found' in data and isinstance(data['links_found'], list):
            data['links_found'] = [Backlink.from_dict(b) for b in data['links_found']]
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'seo_metrics' in data and isinstance(data['seo_metrics'], dict):
            data['seo_metrics'] = SEOMetrics.from_dict(data['seo_metrics'])
        return cls(**data)

@dataclass
class LinkProfile:
    """Complete link profile for a domain or URL"""
    target_url: str
    total_backlinks: int = 0
    unique_referring_domains: int = 0
    dofollow_backlinks: int = 0
    nofollow_backlinks: int = 0
    ugc_backlinks: int = 0
    sponsored_backlinks: int = 0
    internal_backlinks: int = 0
    external_backlinks: int = 0
    broken_backlinks: int = 0
    top_anchor_texts: Dict[str, int] = field(default_factory=dict) # anchor_text: count
    top_referring_domains: Dict[str, int] = field(default_factory=dict) # domain: count
    backlinks: List[Backlink] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'LinkProfile':
        if 'backlinks' in data and isinstance(data['backlinks'], list):
            data['backlinks'] = [Backlink.from_dict(b) for b in data['backlinks']]
        if 'last_updated' in data and isinstance(data['last_updated'], str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

def create_link_profile_from_backlinks(target_url: str, backlinks: List[Backlink]) -> LinkProfile:
    """
    Creates a LinkProfile object from a list of Backlink objects.
    """
    profile = LinkProfile(target_url=target_url)
    profile.total_backlinks = len(backlinks)
    
    referring_domains = set()
    anchor_texts = defaultdict(int)

    for backlink in backlinks:
        referring_domains.add(backlink.source_domain)
        anchor_texts[backlink.anchor_text] += 1

        if backlink.link_type == LinkType.DOFOLLOW:
            profile.dofollow_backlinks += 1
        elif backlink.link_type == LinkType.NOFOLLOW:
            profile.nofollow_backlinks += 1
        elif backlink.link_type == LinkType.UGC:
            profile.ugc_backlinks += 1
        elif backlink.link_type == LinkType.SPONSORED:
            profile.sponsored_backlinks += 1
        elif backlink.link_type == LinkType.INTERNAL:
            profile.internal_backlinks += 1
        elif backlink.link_type == LinkType.EXTERNAL:
            profile.external_backlinks += 1
        elif backlink.link_type == LinkType.BROKEN:
            profile.broken_backlinks += 1
            
        profile.backlinks.append(backlink)

    profile.unique_referring_domains = len(referring_domains)
    profile.top_anchor_texts = dict(sorted(anchor_texts.items(), key=lambda item: item[1], reverse=True)[:10]) # Top 10
    
    # Calculate top referring domains (needs to be done from the set of referring_domains)
    # This part needs actual backlink objects to count per domain, not just unique domains
    domain_counts = defaultdict(int)
    for backlink in backlinks:
        if backlink.source_domain:
            domain_counts[backlink.source_domain] += 1
    profile.top_referring_domains = dict(sorted(domain_counts.items(), key=lambda item: item[1], reverse=True)[:10])

    return profile

@dataclass
class CrawlError:
    """Represents a structured error encountered during crawling."""
    url: str
    error_type: str # e.g., "network_error", "timeout", "parsing_error", "http_error"
    message: str
    details: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    severity: AlertSeverity = AlertSeverity.WARNING # Default severity

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlError':
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'severity' in data and isinstance(data['severity'], str):
            data['severity'] = AlertSeverity(data['severity'])
        return cls(**data)

@dataclass
class CrawlJob:
    """Represents a crawling job"""
    id: str
    target_url: str
    job_type: str # e.g., "backlink_discovery", "site_audit", "content_crawl"
    status: CrawlStatus = CrawlStatus.PENDING
    config: Dict[str, Any] = field(default_factory=dict) # Store CrawlConfig as dict
    created_at: datetime = field(default_factory=datetime.now) # Changed from created_date
    started_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    progress_percentage: float = 0.0
    urls_crawled: int = 0
    links_found: int = 0
    errors: List[CrawlError] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict) # Store summary results
    priority: int = 5 # Added priority
    scheduled_at: Optional[datetime] = None # Added scheduled_at
    cron_schedule: Optional[str] = None # Added cron_schedule
    anomalies_detected: List[str] = field(default_factory=list) # New: List of detected anomalies for the job

    def add_error(self, url: str, error_type: str, message: str, details: Optional[str] = None, severity: AlertSeverity = AlertSeverity.WARNING) -> None:
        error = CrawlError(url=url, error_type=error_type, message=message, details=details, severity=severity)
        self.errors.append(error)

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlJob':
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = CrawlStatus(data['status'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'started_date' in data and isinstance(data['started_date'], str):
            data['started_date'] = datetime.fromisoformat(data['started_date'])
        if 'completed_date' in data and isinstance(data['completed_date'], str):
            data['completed_date'] = datetime.fromisoformat(data['completed_date'])
        if 'errors' in data and isinstance(data['errors'], list):
            data['errors'] = [CrawlError.from_dict(e) for e in data['errors']]
        if 'scheduled_at' in data and isinstance(data['scheduled_at'], str):
            data['scheduled_at'] = datetime.fromisoformat(data['scheduled_at'])
        return cls(**data)

@dataclass 
class SERPResult:
    """Represents a single search engine results page (SERP) entry."""
    keyword: str
    rank: int
    url: str
    title: str
    snippet: str
    domain: str
    position_type: Optional[str] = None # e.g., "organic", "featured_snippet", "ad"
    timestamp: datetime = field(default_factory=datetime.now)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'SERPResult':
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class KeywordSuggestion:
    """Represents a keyword suggestion from a research tool."""
    keyword: str
    search_volume: Optional[int] = None
    cpc: Optional[float] = None # Cost Per Click
    competition: Optional[float] = None # 0-1 range
    difficulty: Optional[int] = None # 0-100 range
    relevance: Optional[float] = None # 0-1 range
    source: Optional[str] = None # e.g., "Google Ads", "Ahrefs", "SEMrush"
    keyword_trend: Optional[List[float]] = None # New: Trend data from Google Trends
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'KeywordSuggestion':
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class LinkIntersectResult:
    """Result of a link intersect analysis."""
    primary_domain: str
    competitor_domains: List[str]
    common_linking_domains: List[str] = field(default_factory=list)
    analysis_date: datetime = field(default_factory=datetime.now)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'LinkIntersectResult':
        if 'analysis_date' in data and isinstance(data['analysis_date'], str):
            data['analysis_date'] = datetime.fromisoformat(data['analysis_date'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class CompetitiveKeywordAnalysisResult:
    """Result of a competitive keyword analysis."""
    primary_domain: str
    competitor_domains: List[str]
    common_keywords: List[str] = field(default_factory=list)
    keyword_gaps: Dict[str, List[str]] = field(default_factory=dict) # Competitor -> keywords they rank for that primary doesn't
    primary_unique_keywords: List[str] = field(default_factory=list) # Keywords primary ranks for that competitors don't
    analysis_date: datetime = field(default_factory=datetime.now)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'CompetitiveKeywordAnalysisResult':
        if 'analysis_date' in data and isinstance(data['analysis_date'], str):
            data['analysis_date'] = datetime.fromisoformat(data['analysis_date'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class AlertRule:
    """Defines a rule for triggering alerts based on job or metric conditions."""
    id: str

    name: str
    description: Optional[str] = None
    # Changed 'condition' to more structured fields for clarity and DB mapping
    trigger_type: str = Field(..., description="Type of event that triggers the alert (e.g., 'job_status_change', 'metric_threshold', 'anomaly_detected').")
    job_type_filter: Optional[str] = Field(None, description="Optional: Apply rule only to specific job types (e.g., 'backlink_discovery').")
    target_url_pattern: Optional[str] = Field(None, description="Optional: Regex pattern for target URLs to apply the rule to.")
    
    metric_name: Optional[str] = Field(None, description="Optional: Name of the metric to monitor (for 'metric_threshold' trigger_type, e.g., 'seo_score', 'broken_links_count', 'crawl_errors_rate').")
    threshold_value: Optional[Union[int, float]] = Field(None, description="Optional: Threshold value for the metric.")
    comparison_operator: Optional[str] = Field(None, description="Optional: Comparison operator for the metric threshold (e.g., '>', '<', '>=', '<=', '==').")
    
    anomaly_type_filter: Optional[str] = Field(None, description="Optional: Filter for specific anomaly types (for 'anomaly_detected' trigger_type, e.g., 'captcha_spike').")
    
    severity: AlertSeverity = AlertSeverity.WARNING
    channels: List[AlertChannel] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_triggered_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'AlertRule':
        if 'severity' in data and isinstance(data['severity'], str):
            data['severity'] = AlertSeverity(data['severity'])
        if 'channels' in data and isinstance(data['channels'], list):
            data['channels'] = [AlertChannel(c) for c in data['channels']]
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_triggered_at' in data and isinstance(data['last_triggered_at'], str):
            data['last_triggered_at'] = datetime.fromisoformat(data['last_triggered_at'])
        return cls(**data)

@dataclass
class User:
    """Represents a user in the system."""
    id: str
    username: str
    email: str
    hashed_password: str
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        # Exclude hashed_password for security when converting to dict for API responses
        return {k: serialize_model(v) for k, v in self.__dict__.items() if k != 'hashed_password'}

    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class Token:
    """Represents a JWT token."""
    access_token: str
    token_type: str

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'Token':
        return cls(**data)

@dataclass
class TokenData:
    """Represents data extracted from a JWT token."""
    username: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'TokenData':
        return cls(**data)

@dataclass
class DomainHistory:
    """Represents a historical snapshot of a domain's metrics."""
    domain_name: str
    snapshot_date: datetime = field(default_factory=datetime.now)
    authority_score: Optional[float] = None
    trust_score: Optional[float] = None
    spam_score: Optional[float] = None
    total_backlinks: Optional[int] = None
    referring_domains: Optional[int] = None
    # Add other key metrics that should be tracked historically
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'DomainHistory':
        if 'snapshot_date' in data and isinstance(data['snapshot_date'], str):
            data['snapshot_date'] = datetime.fromisoformat(data['snapshot_date'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class LinkProspect:
    """Represents a potential link building opportunity."""
    id: str
    target_domain: str
    prospect_url: str
    status: str = "new" # e.g., "new", "contacted", "replied", "link_acquired", "rejected"
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    notes: Optional[str] = None
    priority: str = "medium" # e.g., "low", "medium", "high"
    discovered_date: datetime = field(default_factory=datetime.now)
    last_contacted: Optional[datetime] = None
    link_acquired_date: Optional[datetime] = None
    # Associated SEO metrics of the prospect domain
    prospect_seo_metrics: SEOMetrics = field(default_factory=SEOMetrics)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        data = {k: serialize_model(v) for k, v in self.__dict__.items()}
        if isinstance(data.get('prospect_seo_metrics'), SEOMetrics):
            data['prospect_seo_metrics'] = data['prospect_seo_metrics'].to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'LinkProspect':
        if 'discovered_date' in data and isinstance(data['discovered_date'], str):
            data['discovered_date'] = datetime.fromisoformat(data['discovered_date'])
        if 'last_contacted' in data and isinstance(data['last_contacted'], str):
            data['last_contacted'] = datetime.fromisoformat(data['last_contacted'])
        if 'link_acquired_date' in data and isinstance(data['link_acquired_date'], str):
            data['link_acquired_date'] = datetime.fromisoformat(data['link_acquired_date'])
        if 'prospect_seo_metrics' in data and isinstance(data['prospect_seo_metrics'], dict):
            data['prospect_seo_metrics'] = SEOMetrics.from_dict(data['prospect_seo_metrics'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class OutreachCampaign:
    """Represents a link building outreach campaign."""
    id: str
    name: str
    target_domains: List[str] = field(default_factory=list)
    status: str = "planning" # e.g., "planning", "active", "completed", "paused"
    created_at: datetime = field(default_factory=datetime.now) # Changed from created_date
    start_date: datetime = field(default_factory=datetime.now)
    end_date: Optional[datetime] = None
    notes: Optional[str] = None
    # Metrics
    total_prospects: int = 0
    contacts_made: int = 0
    replies_received: int = 0
    links_acquired: int = 0
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'OutreachCampaign':
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'start_date' in data and isinstance(data['start_date'], str):
            data['start_date'] = datetime.fromisoformat(data['start_date'])
        if 'end_date' in data and isinstance(data['end_date'], str):
            data['end_date'] = datetime.fromisoformat(data['end_date'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class OutreachEvent:
    """Represents a single event within an outreach campaign."""
    id: str
    campaign_id: str
    prospect_id: str
    event_type: str # e.g., "email_sent", "follow_up", "reply", "link_secured"
    timestamp: datetime = field(default_factory=datetime.now)
    notes: Optional[str] = None
    success: Optional[bool] = None # Whether the event achieved its immediate goal
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'OutreachEvent':
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class ContentGapAnalysisResult:
    """Represents the result of a content gap analysis."""
    target_url: str
    competitor_urls: List[str]
    missing_topics: List[str] = field(default_factory=list)
    missing_keywords: List[str] = field(default_factory=list)
    content_format_gaps: List[str] = field(default_factory=list)
    actionable_insights: List[str] = field(default_factory=list)
    analysis_date: datetime = field(default_factory=datetime.now)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'ContentGapAnalysisResult':
        if 'analysis_date' in data and isinstance(data['analysis_date'], str):
            data['analysis_date'] = datetime.fromisoformat(data['analysis_date'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class ReportJob:
    """Represents a report generation job."""
    id: str
    report_type: str
    target_identifier: str
    format: str
    status: CrawlStatus = CrawlStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now) # Changed from created_date
    completed_at: Optional[datetime] = None
    generated_file_path: Optional[str] = None # Changed from file_path
    error_message: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict) # Added config
    scheduled_at: Optional[datetime] = None # Added scheduled_at
    cron_schedule: Optional[str] = None # Added cron_schedule
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'ReportJob':
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = CrawlStatus(data['status'])
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'completed_at' in data and isinstance(data['completed_at'], str):
            data['completed_at'] = datetime.fromisoformat(data['completed_at'])
        if 'scheduled_at' in data and isinstance(data['scheduled_at'], str):
            data['scheduled_at'] = datetime.fromisoformat(data['scheduled_at'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class DomainIntelligence:
    """Comprehensive intelligence summary for a domain."""
    domain_name: str
    last_updated: datetime = field(default_factory=datetime.now)
    overall_score: Optional[float] = None
    technical_data_summary: Dict[str, Any] = field(default_factory=dict)
    seo_metrics: SEOMetrics = field(default_factory=SEOMetrics) # Nested SEOMetrics
    social_data_summary: Dict[str, Any] = field(default_factory=dict)
    security_data_summary: Dict[str, Any] = field(default_factory=dict)
    historical_data_summary: Dict[str, Any] = field(default_factory=dict)
    content_data_summary: Dict[str, Any] = field(default_factory=dict)
    top_social_platforms: List[str] = field(default_factory=list)
    estimated_traffic_trend: List[float] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        data = {k: serialize_model(v) for k, v in self.__dict__.items()}
        if isinstance(data.get('seo_metrics'), SEOMetrics):
            data['seo_metrics'] = data['seo_metrics'].to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'DomainIntelligence':
        if 'last_updated' in data and isinstance(data['last_updated'], str):
            data['last_updated'] = datetime.fromisoformat(data['last_updated'])
        if 'seo_metrics' in data and isinstance(data['seo_metrics'], dict):
            data['seo_metrics'] = SEOMetrics.from_dict(data['seo_metrics'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)

@dataclass
class SocialMention:
    """Represents a social media mention of a brand or keyword."""
    id: str
    query: str
    platform: str
    mention_url: str
    mention_text: str
    author: Optional[str] = None
    published_date: datetime = field(default_factory=datetime.now)
    sentiment: Optional[str] = None
    engagement_score: Optional[float] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    last_fetched_at: Optional[datetime] = None # New: Timestamp of last fetch/update

    def to_dict(self) -> Dict[str, Any]:
        return {k: serialize_model(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: Dict) -> 'SocialMention':
        if 'published_date' in data and isinstance(data['published_date'], str):
            data['published_date'] = datetime.fromisoformat(data['published_date'])
        if 'last_fetched_at' in data and isinstance(data['last_fetched_at'], str):
            data['last_fetched_at'] = datetime.fromisoformat(data['last_fetched_at'])
        return cls(**data)
