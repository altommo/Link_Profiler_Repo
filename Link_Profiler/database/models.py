from sqlalchemy import Column, String, Boolean, DateTime, Float, Text
from sqlalchemy.dialects.postgresql import ARRAY # For ARRAY type
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime # Import datetime
import uuid # Import uuid for default values if needed

# Assuming these enums are defined elsewhere and need to be imported
# If they are defined in this file, ensure they are defined before use.
from Link_Profiler.core.models import AlertSeverity as AlertSeverityEnum, AlertChannel as AlertChannelEnum # Corrected import for enums
from Link_Profiler.core.models import LinkType as LinkTypeEnum, ContentType as ContentTypeEnum, CrawlStatus as CrawlStatusEnum, SpamLevel as SpamLevelEnum # Import other enums

Base = declarative_base()

class AlertRuleORM(Base):
    __tablename__ = 'alert_rules'
    id = Column(String, primary_key=True) # UUID string
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    trigger_type = Column(String, nullable=False) # e.g., "job_status_change", "metric_threshold", "anomaly_detected"
    job_type_filter = Column(String, nullable=True) # e.g., "backlink_discovery"
    target_url_pattern = Column(String, nullable=True) # Regex pattern for target URLs

    metric_name = Column(String, nullable=True) # e.g., "seo_score", "broken_links_count"
    threshold_value = Column(Float, nullable=True)
    comparison_operator = Column(String, nullable=True) # e.g., ">", "<", ">=", "<=", "=="

    anomaly_type_filter = Column(String, nullable=True) # e.g., "captcha_spike", "crawl_rate_drop"

    severity = Column(String, default=AlertSeverityEnum.WARNING.value)
    notification_channels = Column(ARRAY(String), default=[AlertChannelEnum.DASHBOARD.value])
    notification_recipients = Column(ARRAY(String), default=[])

    created_at = Column(DateTime, default=datetime.now)
    last_triggered_at = Column(DateTime, nullable=True)
    last_fetched_at = Column(DateTime, default=datetime.utcnow) # This line is present and correct

# Placeholder ORM definitions for other models used in database.py
# These would typically be in separate files or defined here if they are simple.
# For the purpose of fixing the import errors, we'll add minimal definitions.

class DomainORM(Base):
    __tablename__ = 'domains'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    authority_score = Column(Float)
    trust_score = Column(Float)
    spam_score = Column(String) # Stored as string from enum value
    registered_date = Column(DateTime)
    expiration_date = Column(DateTime)
    registrar = Column(String)
    is_registered = Column(Boolean)
    is_parked = Column(Boolean)
    is_dead = Column(Boolean)
    whois_raw = Column(Text)
    dns_records = Column(JSON) # Assuming JSON type for dict
    ip_address = Column(String)
    country = Column(String)
    seo_metrics = Column(JSON) # Assuming JSON type for dict
    last_checked = Column(DateTime)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class URLORM(Base):
    __tablename__ = 'urls'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, unique=True, nullable=False)
    content_type = Column(String) # Stored as string from enum value
    # Add other URL fields as needed

class BacklinkORM(Base):
    __tablename__ = 'backlinks'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_url = Column(String, nullable=False)
    target_url = Column(String, nullable=False)
    source_domain_name = Column(String)
    target_domain_name = Column(String)
    anchor_text = Column(String)
    link_type = Column(String) # Stored as string from enum value
    nofollow = Column(Boolean)
    ugc = Column(Boolean)
    sponsored = Column(Boolean)
    first_seen = Column(DateTime)
    last_seen = Column(DateTime)
    source_page_authority = Column(Float)
    source_domain_authority = Column(Float)
    rel_attributes = Column(ARRAY(String))
    context_text = Column(Text)
    position_on_page = Column(String)
    is_image_link = Column(Boolean)
    alt_text = Column(String)
    authority_passed = Column(Float)
    is_active = Column(Boolean)
    spam_level = Column(String) # Stored as string from enum value
    http_status = Column(Integer)
    crawl_timestamp = Column(DateTime)
    source_domain_metrics = Column(JSON)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class LinkProfileORM(Base):
    __tablename__ = 'link_profiles'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    target_url = Column(String, unique=True, nullable=False)
    total_backlinks = Column(Integer)
    unique_referring_domains = Column(Integer)
    dofollow_backlinks = Column(Integer)
    nofollow_backlinks = Column(Integer)
    ugc_backlinks = Column(Integer)
    sponsored_backlinks = Column(Integer)
    internal_backlinks = Column(Integer)
    external_backlinks = Column(Integer)
    broken_backlinks = Column(Integer)
    top_anchor_texts = Column(JSON)
    top_referring_domains = Column(JSON)
    last_updated = Column(DateTime)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class CrawlJobORM(Base):
    __tablename__ = 'crawl_jobs'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    target_url = Column(String, nullable=False)
    job_type = Column(String)
    status = Column(String) # Stored as string from enum value
    created_at = Column(DateTime)
    started_date = Column(DateTime)
    completed_date = Column(DateTime)
    progress_percentage = Column(Float)
    urls_crawled = Column(Integer)
    links_found = Column(Integer)
    errors = Column(JSON) # Stored as JSON
    priority = Column(Integer)
    scheduled_at = Column(DateTime)
    cron_schedule = Column(String)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)
    config = Column(JSON) # Store config as JSON

class SEOMetricsORM(Base):
    __tablename__ = 'seo_metrics'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String, unique=True, nullable=False)
    domain_authority = Column(Float)
    page_authority = Column(Float)
    trust_flow = Column(Float)
    citation_flow = Column(Float)
    organic_keywords = Column(Integer)
    organic_traffic = Column(Integer)
    referring_domains = Column(Integer)
    spam_score = Column(Float)
    moz_rank = Column(Float)
    ahrefs_rank = Column(Integer)
    semrush_rank = Column(Integer)
    majestic_trust_flow = Column(Float)
    majestic_citation_flow = Column(Float)
    http_status = Column(Integer)
    response_time_ms = Column(Float)
    page_size_bytes = Column(Integer)
    title_length = Column(Integer)
    meta_description_length = Column(Integer)
    h1_count = Column(Integer)
    h2_count = Column(Integer)
    internal_links = Column(Integer)
    external_links = Column(Integer)
    images_count = Column(Integer)
    images_without_alt = Column(Integer)
    has_canonical = Column(Boolean)
    has_robots_meta = Column(Boolean)
    has_schema_markup = Column(Boolean)
    broken_links = Column(ARRAY(String))
    performance_score = Column(Float)
    mobile_friendly = Column(Boolean)
    accessibility_score = Column(Float)
    audit_timestamp = Column(DateTime)
    seo_score = Column(Float)
    issues = Column(ARRAY(String))
    structured_data_types = Column(ARRAY(String))
    og_title = Column(String)
    og_description = Column(String)
    twitter_title = Column(String)
    twitter_description = Column(String)
    validation_issues = Column(ARRAY(String))
    ocr_text = Column(Text)
    nlp_entities = Column(ARRAY(String))
    nlp_sentiment = Column(String)
    nlp_topics = Column(ARRAY(String))
    video_transcription = Column(Text)
    video_topics = Column(ARRAY(String))
    ai_content_classification = Column(String)
    ai_content_score = Column(Float)
    ai_suggestions = Column(ARRAY(String))
    ai_semantic_keywords = Column(ARRAY(String))
    ai_readability_score = Column(Float)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class SERPResultORM(Base):
    __tablename__ = 'serp_results'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    keyword = Column(String, nullable=False)
    rank = Column(Integer, nullable=False)
    url = Column(String, nullable=False)
    title = Column(String)
    snippet = Column(Text)
    domain = Column(String)
    position_type = Column(String)
    timestamp = Column(DateTime)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class KeywordSuggestionORM(Base):
    __tablename__ = 'keyword_suggestions'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    seed_keyword = Column(String, nullable=False)
    keyword = Column(String, nullable=False)
    search_volume = Column(Integer)
    cpc = Column(Float)
    competition = Column(Float)
    difficulty = Column(Integer)
    relevance = Column(Float)
    source = Column(String)
    keyword_trend = Column(ARRAY(Float))
    data_timestamp = Column(DateTime, default=datetime.utcnow) # Renamed from last_fetched_at to avoid conflict with ORM
    last_fetched_at = Column(DateTime, default=datetime.utcnow) # Added for consistency

class UserORM(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    role = Column(String, default="user")
    organization_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    last_updated = Column(DateTime, default=datetime.utcnow)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class ContentGapAnalysisResultORM(Base):
    __tablename__ = 'content_gap_analysis_results'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    target_url = Column(String, nullable=False)
    competitor_urls = Column(ARRAY(String))
    missing_topics = Column(ARRAY(String))
    missing_keywords = Column(ARRAY(String))
    content_format_gaps = Column(ARRAY(String))
    actionable_insights = Column(ARRAY(String))
    analysis_date = Column(DateTime, default=datetime.now)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class DomainHistoryORM(Base):
    __tablename__ = 'domain_history'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    domain_name = Column(String, nullable=False)
    snapshot_date = Column(DateTime, nullable=False)
    authority_score = Column(Float)
    trust_score = Column(Float)
    spam_score = Column(Float)
    total_backlinks = Column(Integer)
    referring_domains = Column(Integer)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class LinkProspectORM(Base):
    __tablename__ = 'link_prospects'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    target_domain = Column(String, nullable=False)
    prospect_url = Column(String, nullable=False)
    status = Column(String)
    contact_email = Column(String)
    contact_name = Column(String)
    notes = Column(Text)
    priority = Column(String)
    discovered_date = Column(DateTime)
    last_contacted = Column(DateTime)
    link_acquired_date = Column(DateTime)
    prospect_seo_metrics = Column(JSON)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class OutreachCampaignORM(Base):
    __tablename__ = 'outreach_campaigns'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    target_domain = Column(String, nullable=False)
    status = Column(String)
    created_at = Column(DateTime)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    notes = Column(Text)
    total_prospects = Column(Integer)
    contacts_made = Column(Integer)
    replies_received = Column(Integer)
    links_acquired = Column(Integer)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class OutreachEventORM(Base):
    __tablename__ = 'outreach_events'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, nullable=False)
    prospect_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    timestamp = Column(DateTime)
    notes = Column(Text)
    success = Column(Boolean)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class ReportJobORM(Base):
    __tablename__ = 'report_jobs'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_type = Column(String, nullable=False)
    target_identifier = Column(String, nullable=False)
    format = Column(String, nullable=False)
    status = Column(String)
    created_at = Column(DateTime)
    completed_at = Column(DateTime)
    generated_file_path = Column(String)
    error_message = Column(Text)
    config = Column(JSON)
    scheduled_at = Column(DateTime)
    cron_schedule = Column(String)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class DomainIntelligenceORM(Base):
    __tablename__ = 'domain_intelligence'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    domain_name = Column(String, unique=True, nullable=False)
    value_score = Column(Float)
    is_valuable = Column(Boolean)
    reasons = Column(ARRAY(String))
    details = Column(JSON)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class SocialMentionORM(Base):
    __tablename__ = 'social_mentions'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    query = Column(String, nullable=False)
    platform = Column(String)
    mention_url = Column(String)
    mention_text = Column(Text)
    author = Column(String)
    published_date = Column(DateTime)
    sentiment = Column(String)
    engagement_score = Column(Float)
    raw_data = Column(JSON)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)

class SatellitePerformanceLogORM(Base):
    __tablename__ = 'satellite_performance_logs'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    satellite_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    cpu_utilization_percent = Column(Float)
    memory_utilization_percent = Column(Float)
    network_io_mbps = Column(Float)
    pages_crawled = Column(Integer)
    links_extracted = Column(Integer)
    crawl_speed_pages_per_minute = Column(Float)
    success_rate_percentage = Column(Float)
    avg_response_time_ms = Column(Float)
    errors_logged = Column(Integer)
    current_job_id = Column(String)
    current_job_type = Column(String)
    current_job_progress = Column(Float)
    last_fetched_at = Column(DateTime, default=datetime.utcnow)
