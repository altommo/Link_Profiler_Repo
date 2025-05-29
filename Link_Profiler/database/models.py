"""
SQLAlchemy ORM Models for the Link Profiler System
File: Link_Profiler/database/models.py
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY # For storing dicts and lists/sets
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
    context_text = Column(Text, nullable=False)
    position_on_page = Column(Integer, default=0)
    is_image_link = Column(Boolean, default=False)
    alt_text = Column(String, nullable=True)
    discovered_date = Column(DateTime, default=datetime.now)
    last_seen_date = Column(DateTime, default=datetime.now)
    authority_passed = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    spam_level = Column(String, default=SpamLevelEnum.CLEAN.value) # Store enum value as string

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
    error_log = Column(ARRAY(String), default=[]) # Store as array of strings

    def __repr__(self):
        return f"<CrawlJob(id='{self.id}', target_url='{self.target_url}', status='{self.status}')>"


class SEOMetricsORM(Base):
    __tablename__ = 'seo_metrics'
    url = Column(String, ForeignKey('urls.url'), primary_key=True) # One-to-one with URL
    title_length = Column(Integer, default=0)
    description_length = Column(Integer, default=0)
    h1_count = Column(Integer, default=0)
    h2_count = Column(Integer, default=0)
    internal_links = Column(Integer, default=0)
    external_links = Column(Integer, default=0)
    images_count = Column(Integer, default=0)
    images_without_alt = Column(Integer, default=0)
    page_size_kb = Column(Float, default=0.0)
    load_time_ms = Column(Float, default=0.0)
    has_canonical = Column(Boolean, default=False)
    has_robots_meta = Column(Boolean, default=False)
    has_schema_markup = Column(Boolean, default=False)
    mobile_friendly = Column(Boolean, default=False)
    ssl_enabled = Column(Boolean, default=False)
    seo_score = Column(Float, default=0.0)
    issues = Column(ARRAY(String), default=[]) # Store as array of strings

    # Relationships
    url_rel = relationship("URLORM", back_populates="seo_metrics")

    def __repr__(self):
        return f"<SEOMetrics(url='{self.url}', seo_score={self.seo_score})>"
