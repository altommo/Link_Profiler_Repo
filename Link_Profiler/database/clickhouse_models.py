from sqlalchemy import Column, String, DateTime, Float, Integer, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_clickhouse import MergeTree, AggregatingMergeTree
from datetime import datetime, timedelta

Base = declarative_base()

# Define data retention in years for TTL
DATA_RETENTION_YEARS = 1 # Default to 1 year, can be configured

class BacklinkAnalyticalORM(Base):
    __tablename__ = 'backlinks_analytical'
    __table_args__ = (
        MergeTree(
            partition_by='toYYYYMM(timestamp)',
            order_by='(timestamp, target_url_domain, source_url_domain)',
            ttl=f"timestamp + INTERVAL {DATA_RETENTION_YEARS} YEAR"
        ),
        {'schema': 'default'} # Specify the schema if not default
    )

    id = Column(String, primary_key=True) # UUID from source system
    timestamp = Column(DateTime, default=datetime.utcnow)
    source_url = Column(String)
    target_url = Column(String)
    source_url_domain = Column(String)
    target_url_domain = Column(String)
    anchor_text = Column(String)
    link_type = Column(String)
    nofollow = Column(Integer) # 0 or 1
    ugc = Column(Integer) # 0 or 1
    sponsored = Column(Integer) # 0 or 1
    http_status = Column(Integer)
    spam_level = Column(String)
    source_page_authority = Column(Float)
    source_domain_authority = Column(Float)
    user_id = Column(String)
    organization_id = Column(String)

class SEOAnalyticalORM(Base):
    __tablename__ = 'seo_metrics_analytical'
    __table_args__ = (
        MergeTree(
            partition_by='toYYYYMM(audit_timestamp)',
            order_by='(audit_timestamp, url_domain, url)',
            ttl=f"audit_timestamp + INTERVAL {DATA_RETENTION_YEARS} YEAR"
        ),
        {'schema': 'default'}
    )

    id = Column(String, primary_key=True)
    audit_timestamp = Column(DateTime, default=datetime.utcnow)
    url = Column(String)
    url_domain = Column(String)
    domain_authority = Column(Float)
    page_authority = Column(Float)
    trust_flow = Column(Float)
    citation_flow = Column(Float)
    organic_keywords = Column(Integer)
    organic_traffic = Column(Integer)
    referring_domains = Column(Integer)
    spam_score = Column(Float)
    http_status = Column(Integer)
    response_time_ms = Column(Float)
    page_size_bytes = Column(Integer)
    seo_score = Column(Float)
    user_id = Column(String)
    organization_id = Column(String)
    # Store issues and structured_data_types as JSON strings or Array(String)
    issues = Column(JSON) # Or ARRAY(String) if you prefer
    structured_data_types = Column(JSON) # Or ARRAY(String)

class SERPAnalyticalORM(Base):
    __tablename__ = 'serp_results_analytical'
    __table_args__ = (
        MergeTree(
            partition_by='toYYYYMM(timestamp)',
            order_by='(timestamp, keyword, domain)',
            ttl=f"timestamp + INTERVAL {DATA_RETENTION_YEARS} YEAR"
        ),
        {'schema': 'default'}
    )

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    keyword = Column(String)
    rank = Column(Integer)
    url = Column(String)
    domain = Column(String)
    title = Column(String)
    snippet = Column(Text)
    position_type = Column(String)
    user_id = Column(String)
    organization_id = Column(String)

class KeywordSuggestionAnalyticalORM(Base):
    __tablename__ = 'keyword_suggestions_analytical'
    __table_args__ = (
        MergeTree(
            partition_by='toYYYYMM(data_timestamp)',
            order_by='(data_timestamp, keyword, seed_keyword)',
            ttl=f"data_timestamp + INTERVAL {DATA_RETENTION_YEARS} YEAR"
        ),
        {'schema': 'default'}
    )

    id = Column(String, primary_key=True)
    data_timestamp = Column(DateTime, default=datetime.utcnow)
    seed_keyword = Column(String)
    keyword = Column(String)
    search_volume = Column(Integer)
    cpc = Column(Float)
    competition = Column(Float)
    difficulty = Column(Integer)
    relevance = Column(Float)
    source = Column(String)
    keyword_trend = Column(JSON) # Store as JSON array
    user_id = Column(String)
    organization_id = Column(String)

class GSCBacklinkAnalyticalORM(Base):
    __tablename__ = 'gsc_backlinks_analytical'
    __table_args__ = (
        MergeTree(
            partition_by='toYYYYMM(fetch_date)',
            order_by='(fetch_date, domain, source_url, target_url)',
            ttl=f"fetch_date + INTERVAL {DATA_RETENTION_YEARS} YEAR"
        ),
        {'schema': 'default'}
    )

    id = Column(String, primary_key=True)
    fetch_date = Column(DateTime, default=datetime.utcnow)
    domain = Column(String)
    source_url = Column(String)
    target_url = Column(String)
    anchor_text = Column(String)
    user_id = Column(String)
    organization_id = Column(String)

class KeywordTrendAnalyticalORM(Base):
    __tablename__ = 'keyword_trends_analytical'
    __table_args__ = (
        MergeTree(
            partition_by='toYYYYMM(date)',
            order_by='(date, keyword)',
            ttl=f"date + INTERVAL {DATA_RETENTION_YEARS} YEAR"
        ),
        {'schema': 'default'}
    )

    id = Column(String, primary_key=True)
    keyword = Column(String)
    date = Column(DateTime)
    trend_index = Column(Float)
    source = Column(String)
    user_id = Column(String)
    organization_id = Column(String)
