"""
Core Models - Data structures for the Link Profiler system
File: core/models.py
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Union
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse
import json


class LinkType(Enum):
    """Types of links we can discover"""
    FOLLOW = "follow"
    NOFOLLOW = "nofollow" 
    SPONSORED = "sponsored"
    UGC = "ugc"
    REDIRECT = "redirect"
    CANONICAL = "canonical"


class ContentType(Enum):
    """Types of content we can analyze"""
    HTML = "text/html"
    PDF = "application/pdf"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    OTHER = "other"


class CrawlStatus(Enum):
    """Status of crawling operations"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


class SpamLevel(Enum):
    """Spam classification levels"""
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    LIKELY_SPAM = "likely_spam"
    CONFIRMED_SPAM = "confirmed_spam"


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
    context_text: str = ""  # Surrounding text
    position_on_page: int = 0
    is_image_link: bool = False
    alt_text: Optional[str] = None
    discovered_date: datetime = field(default_factory=datetime.now)
    last_seen_date: datetime = field(default_factory=datetime.now)
    authority_passed: float = 0.0
    is_active: bool = True
    spam_level: SpamLevel = SpamLevel.CLEAN
    
    def __post_init__(self):
        """Extract domain information from URLs"""
        try:
            self.source_domain = urlparse(self.source_url).netloc.lower()
            self.target_domain = urlparse(self.target_url).netloc.lower()
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
            self.target_domain = urlparse(self.target_url).netloc.lower()
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
    
    def calculate_metrics(self) -> None:
        """Calculate link profile metrics"""
        if not self.backlinks:
            return
            
        self.total_backlinks = len(self.backlinks)
        self.unique_domains = len(self.referring_domains)
        
        # Count link types
        self.dofollow_links = sum(1 for bl in self.backlinks 
                                if bl.link_type == LinkType.FOLLOW)
        self.nofollow_links = self.total_backlinks - self.dofollow_links
        
        # Calculate authority (simplified)
        authority_links = [bl for bl in self.backlinks if bl.passes_authority]
        self.authority_score = min(100.0, len(authority_links) * 2.5)
        
        # Calculate trust score based on clean links
        clean_links = sum(1 for bl in self.backlinks 
                         if bl.spam_level == SpamLevel.CLEAN)
        self.trust_score = (clean_links / self.total_backlinks) * 100 if self.total_backlinks > 0 else 0
        
        # Calculate spam score
        spam_links = sum(1 for bl in self.backlinks 
                        if bl.spam_level in [SpamLevel.LIKELY_SPAM, SpamLevel.CONFIRMED_SPAM])
        self.spam_score = (spam_links / self.total_backlinks) * 100 if self.total_backlinks > 0 else 0

    @classmethod
    def from_dict(cls, data: Dict) -> 'LinkProfile':
        """Create a LinkProfile instance from a dictionary."""
        if 'analysis_date' in data and isinstance(data['analysis_date'], str):
            data['analysis_date'] = datetime.fromisoformat(data['analysis_date'])
        if 'referring_domains' in data and isinstance(data['referring_domains'], list):
            data['referring_domains'] = set(data['referring_domains'])
        if 'backlinks' in data and isinstance(data['backlinks'], list):
            data['backlinks'] = [Backlink.from_dict(bl_data) for bl_data in data['backlinks']]
        
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass
class CrawlJob:
    """Represents a crawling job"""
    id: str
    target_url: str
    job_type: str  # 'backlinks', 'seo_audit', 'competitor_analysis'
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
    config: Dict = field(default_factory=dict)
    results: Dict = field(default_factory=dict)
    error_log: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration"""
        if self.started_date and self.completed_date:
            return (self.completed_date - self.started_date).total_seconds()
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if job is completed"""
        return self.status in [CrawlStatus.COMPLETED, CrawlStatus.FAILED]
    
    def add_error(self, error_message: str) -> None:
        """Add an error to the job log"""
        self.error_log.append(f"{datetime.now().isoformat()}: {error_message}")
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
        
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


@dataclass
class CrawlConfig:
    """Configuration for crawling operations"""
    max_depth: int = 3
    max_pages: int = 1000
    delay_seconds: float = 1.0
    timeout_seconds: int = 30
    user_agent: str = "LinkProfiler/1.0"
    respect_robots_txt: bool = True
    follow_redirects: bool = True
    extract_images: bool = True
    extract_pdfs: bool = False
    max_file_size_mb: int = 10
    allowed_domains: Set[str] = field(default_factory=set)
    blocked_domains: Set[str] = field(default_factory=set)
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    def is_domain_allowed(self, domain: str) -> bool:
        """Check if domain is allowed for crawling"""
        if self.blocked_domains and domain in self.blocked_domains:
            return False
        if self.allowed_domains and domain not in self.allowed_domains:
            return False
        return True

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlConfig':
        """Create a CrawlConfig instance from a dictionary."""
        # Handle sets which are serialized as lists
        if 'allowed_domains' in data and isinstance(data['allowed_domains'], list):
            data['allowed_domains'] = set(data['allowed_domains'])
        if 'blocked_domains' in data and isinstance(data['blocked_domains'], list):
            data['blocked_domains'] = set(data['blocked_domains'])
        
        # Filter out any keys not in the dataclass constructor
        # This prevents errors if the dict contains extra serialization metadata
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}

        return cls(**filtered_data)


@dataclass 
class SEOMetrics:
    """SEO metrics for a URL or domain"""
    url: str
    title_length: int = 0
    description_length: int = 0
    h1_count: int = 0
    h2_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    images_count: int = 0
    images_without_alt: int = 0
    page_size_kb: float = 0.0
    load_time_ms: float = 0.0
    has_canonical: bool = False
    has_robots_meta: bool = False
    has_schema_markup: bool = False
    mobile_friendly: bool = False
    ssl_enabled: bool = False
    seo_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    
    def calculate_seo_score(self) -> float:
        """Calculate overall SEO score"""
        score = 100.0
        
        # Title optimization
        if self.title_length == 0:
            score -= 15
        elif self.title_length > 60:
            score -= 5
            
        # Description optimization  
        if self.description_length == 0:
            score -= 10
        elif self.description_length > 160:
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
        if not self.ssl_enabled:
            score -= 10
        if not self.mobile_friendly:
            score -= 15
            
        # Performance
        if self.load_time_ms > 3000:
            score -= 10
        elif self.load_time_ms > 1000:
            score -= 5
            
        self.seo_score = max(0.0, score)
        return self.seo_score

    @classmethod
    def from_dict(cls, data: Dict) -> 'SEOMetrics':
        """Create a SEOMetrics instance from a dictionary."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


# Utility functions for model operations
def serialize_model(obj) -> Dict:
    """Serialize dataclass to dictionary"""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name, field_def in obj.__dataclass_fields__.items():
            value = getattr(obj, field_name)
            if isinstance(value, datetime):
                result[field_name] = value.isoformat()
            elif isinstance(value, Enum):
                result[field_name] = value.value
            elif isinstance(value, set):
                result[field_name] = list(value)
            elif hasattr(value, '__dataclass_fields__'):
                result[field_name] = serialize_model(value)
            elif isinstance(value, list) and value and hasattr(value[0], '__dataclass_fields__'):
                result[field_name] = [serialize_model(item) for item in value]
            else:
                result[field_name] = value
        return result
    return obj


def create_link_profile_from_backlinks(target_url: str, backlinks: List[Backlink]) -> LinkProfile:
    """Create a LinkProfile from a list of backlinks"""
    profile = LinkProfile(target_url=target_url)
    
    for backlink in backlinks:
        profile.add_backlink(backlink)
    
    profile.calculate_metrics()
    return profile
