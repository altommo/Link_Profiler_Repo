"""
SQLAlchemy ORM Models for the Link Profiler System
File: Link_Profiler/database/models.py
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.inspection import inspect
from datetime import datetime
import enum

# Base class for declarative models
Base = declarative_base()

# Enum for LinkType
class LinkTypeEnum(enum.Enum):
    FOLLOW = "follow"
    NOFOLLOW = "nofollow"
    SPONSORED = "sponsored"
    UGC = "ugc"
    REDIRECT = "redirect"
    CANONICAL = "canonical"

# Enum for ContentType
class ContentTypeEnum(enum.Enum):
    HTML = "text/html"
    PDF = "application/pdf"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    OTHER = "other"

# Enum for CrawlStatus
class CrawlStatusEnum(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"

# Enum for SpamLevel
class SpamLevelEnum(enum.Enum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    LIKELY_SPAM = "likely_spam"
    CONFIRMED_SPAM = "confirmed_spam"


class DomainORM(Base):
    __tablename__ = 'domains'
    name = Column(String, primary_key=True, index=True)
    authority_score = Column(Float, default=0.0)
    trust_score = Column(Float, default=0.0)
    spam_score = Column(Float, default=0.0)
    age_days = Column(Integer, nullable=True)
    country = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    whois_data = Column(JSONB, default={})
    total_pages = Column(Integer, default=0)
    total_backlinks = Column(Integer, default=0)
    referring_domains = Column(Integer, default=0)
    first_seen = Column(DateTime, nullable=True)
    last_crawled = Column(DateTime, nullable=True)

    # Relationships
    urls = relationship("URLORM", back_populates="domain_rel", cascade="all, delete-orphan")
    backlinks_as_source = relationship("BacklinkORM", foreign_keys="BacklinkORM.source_domain_name", back_populates="source_domain_rel", cascade="all, delete-orphan")
    backlinks_as_target = relationship("BacklinkORM", foreign_keys="BacklinkORM.target_domain_name", back_populates="target_domain_rel", cascade="all, delete-orphan")
    link_profiles = relationship("LinkProfileORM", back_populates="target_domain_rel", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Domain(name='{self.name}', authority_score={self.authority_score})>"


class URLORM(Base):
    __tablename__ = 'urls'
    url = Column(String, primary_key=True, index=True)
    domain_name = Column(String, ForeignKey('domains.name'), nullable=False)
    path = Column(String, nullable=False)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    content_type = Column(String, default=ContentTypeEnum.HTML.value) # Store enum value as string
    content_length = Column(Integer, default=0)
    status_code = Column(Integer, nullable=True)
    redirect_url = Column(String, nullable=True)
    canonical_url = Column(String, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    crawl_status = Column(String, default=CrawlStatusEnum.PENDING.value) # Store enum value as string
    crawl_date = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    domain_rel = relationship("DomainORM", back_populates="urls")
    seo_metrics = relationship("SEOMetricsORM", back_populates="url_rel", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<URL(url='{self.url}', domain='{self.domain_name}')>"


class BacklinkORM(Base):
    __tablename__ = 'backlinks'
    id = Column(String, primary_key=True) # UUID string
    source_url = Column(String, nullable=False)
    target_url = Column(String, nullable=False)
    source_domain_name = Column(String, ForeignKey('domains.name'), nullable=False)
    target_domain_name = Column(String, ForeignKey('domains.name'), nullable=False)
    anchor_text = Column(String, nullable=False)
    link_type = Column(String, default=LinkTypeEnum.FOLLOW.value) # Store enum value as string
    rel_attributes = Column(ARRAY(String), default=[]) # New field for all rel values
    context_text = Column(Text, nullable=False)
    position_on_page = Column(Integer, default=0)
    is_image_link = Column(Boolean, default=False)
    alt_text = Column(String, nullable=True)
    discovered_date = Column(DateTime, default=datetime.now)
    last_seen_date = Column(DateTime, default=datetime.now)
    authority_passed = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    spam_level = Column(String, default=SpamLevelEnum.CLEAN.value) # Store enum value as string
    # New fields for Backlink Data
    http_status = Column(Integer, nullable=True) # HTTP response code when fetching source_url
    crawl_timestamp = Column(DateTime, nullable=True) # UTC timestamp when the page was crawled
    source_domain_metrics = Column(JSONB, default={}) # domain-level data such as estimated domain authority or PageRank

    # Relationships
    source_domain_rel = relationship("DomainORM", foreign_keys=[source_domain_name], back_populates="backlinks_as_source")
    target_domain_rel = relationship("DomainORM", foreign_keys=[target_domain_name], back_populates="backlinks_as_target")

    __table_args__ = (UniqueConstraint('source_url', 'target_url', name='_source_target_uc'),)

    def __repr__(self):
        return f"<Backlink(source='{self.source_url}', target='{self.target_url}')>"


class LinkProfileORM(Base):
    __tablename__ = 'link_profiles'
    target_url = Column(String, primary_key=True, index=True)
    target_domain_name = Column(String, ForeignKey('domains.name'), nullable=False)
    total_backlinks = Column(Integer, default=0)
    unique_domains = Column(Integer, default=0)
    dofollow_links = Column(Integer, default=0)
    nofollow_links = Column(Integer, default=0)
    authority_score = Column(Float, default=0.0)
    trust_score = Column(Float, default=0.0)
    spam_score = Column(Float, default=0.0)
    anchor_text_distribution = Column(JSONB, default={})
    referring_domains = Column(ARRAY(String), default=[]) # Store as array of strings
    analysis_date = Column(DateTime, default=datetime.now)

    # Relationships
    target_domain_rel = relationship("DomainORM", back_populates="link_profiles")

    def __repr__(self):
        return f"<LinkProfile(target_url='{self.target_url}', total_backlinks={self.total_backlinks})>"


class CrawlJobORM(Base):
    __tablename__ = 'crawl_jobs'
    id = Column(String, primary_key=True) # UUID string
    target_url = Column(String, nullable=False)
    job_type = Column(String, nullable=False)
    status = Column(String, default=CrawlStatusEnum.PENDING.value) # Store enum value as string
    priority = Column(Integer, default=5)
    created_date = Column(DateTime, default=datetime.now)
    started_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    progress_percentage = Column(Float, default=0.0)
    urls_discovered = Column(Integer, default=0)
    urls_crawled = Column(Integer, default=0)
    links_found = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    config = Column(JSONB, default={}) # Store CrawlConfig as JSON
    results = Column(JSONB, default={})
    error_log = Column(JSONB, default=[]) # Changed to JSONB to store list of structured errors
    anomalies_detected = Column(ARRAY(String), default=[]) # New: List of detected anomalies for the job

    def __repr__(self):
        return f"<CrawlJob(id='{self.id}', target_url='{self.target_url}', status='{self.status}')>"


class SEOMetricsORM(Base):
    __tablename__ = 'seo_metrics'
    url = Column(String, ForeignKey('urls.url'), primary_key=True) # One-to-one with URL
    # Page-level Metrics
    http_status = Column(Integer, nullable=True) # HTTP response code
    response_time_ms = Column(Float, nullable=True) # Time to first byte and full load
    page_size_bytes = Column(Integer, nullable=True) # Total HTML size
    # SEO Checks
    title_length = Column(Integer, default=0)
    meta_description_length = Column(Integer, default=0) # Renamed from description_length
    h1_count = Column(Integer, default=0)
    h2_count = Column(Integer, default=0)
    internal_links = Column(Integer, default=0)
    external_links = Column(Integer, default=0)
    images_count = Column(Integer, default=0)
    images_without_alt = Column(Integer, default=0)
    has_canonical = Column(Boolean, default=False)
    has_robots_meta = Column(Boolean, default=False)
    has_schema_markup = Column(Boolean, default=False)
    broken_links = Column(ARRAY(String), default=[]) # List of internal/external links returning 4xx/5xx
    # Performance & Best Practices
    performance_score = Column(Float, nullable=True) # 0–100
    mobile_friendly = Column(Boolean, nullable=True) # Boolean or score
    accessibility_score = Column(Float, nullable=True) # 0–100
    audit_timestamp = Column(DateTime, nullable=True) # UTC timestamp of audit execution
    # Existing fields
    seo_score = Column(Float, default=0.0)
    issues = Column(ARRAY(String), default=[]) # Store as array of strings
    # New fields for content quality and completeness
    structured_data_types = Column(ARRAY(String), default=[])
    og_title = Column(String, nullable=True)
    og_description = Column(Text, nullable=True)
    twitter_title = Column(String, nullable=True)
    twitter_description = Column(Text, nullable=True)
    validation_issues = Column(ARRAY(String), default=[]) # Issues found by ContentValidator

    # Relationships
    url_rel = relationship("URLORM", back_populates="seo_metrics")

    def __repr__(self):
        return f"<SEOMetrics(url='{self.url}', seo_score={self.seo_score})>"


class SERPResultORM(Base):
    __tablename__ = 'serp_results'
    id = Column(String, primary_key=True) # UUID string
    keyword = Column(String, nullable=False, index=True)
    position = Column(Integer, nullable=False)
    result_url = Column(String, nullable=False)
    title_text = Column(String, nullable=False)
    snippet_text = Column(Text, nullable=True)
    rich_features = Column(ARRAY(String), default=[]) # Flags or details for featured snippets, local packs, etc.
    page_load_time = Column(Float, nullable=True) # Time to fully render the SERP page
    crawl_timestamp = Column(DateTime, default=datetime.now) # UTC timestamp of when the search was performed

    __table_args__ = (UniqueConstraint('keyword', 'result_url', name='_keyword_result_uc'),)

    def __repr__(self):
        return f"<SERPResult(keyword='{self.keyword}', position={self.position}, url='{self.result_url}')>"


class KeywordSuggestionORM(Base):
    __tablename__ = 'keyword_suggestions'
    id = Column(String, primary_key=True) # UUID string
    seed_keyword = Column(String, nullable=False, index=True)
    suggested_keyword = Column(String, nullable=False, index=True)
    search_volume_monthly = Column(Integer, nullable=True)
    cpc_estimate = Column(Float, nullable=True) # Cost-per-click estimate
    keyword_trend = Column(ARRAY(Float), default=[]) # JSON array of monthly interest values
    competition_level = Column(String, nullable=True) # Low/Medium/High
    data_timestamp = Column(DateTime, default=datetime.now) # UTC when this data was gathered

    __table_args__ = (UniqueConstraint('seed_keyword', 'suggested_keyword', name='_seed_suggested_uc'),)

    def __repr__(self):
        return f"<KeywordSuggestion(seed='{self.seed_keyword}', suggested='{self.suggested_keyword}')>"
